import base64
import json
import urllib.request

import requests as _requests
from loguru import logger
from pyzeebe import ZeebeWorker

from camunda.config import (
    CAMUNDA_CLIENT_ID,
    CAMUNDA_CLIENT_SECRET,
    CAMUNDA_CLUSTER_ID,
    CAMUNDA_REGION,
)

N8N_WEBHOOK_URL = "http://localhost:5678/webhook/ai-extract"
CAMUNDA_AUTH_URL = "https://login.cloud.camunda.io/oauth/token"
# REST API: {region}.zeebe.camunda.io/{cluster-id} — NICHT {cluster-id}.{region}.zeebe.camunda.io (gRPC!)
CAMUNDA_REST_BASE = f"https://{CAMUNDA_REGION}.zeebe.camunda.io/{CAMUNDA_CLUSTER_ID}"


def _get_oauth_token() -> str:
    resp = _requests.post(
        CAMUNDA_AUTH_URL,
        json={
            "grant_type": "client_credentials",
            "client_id": CAMUNDA_CLIENT_ID,
            "client_secret": CAMUNDA_CLIENT_SECRET,
            "audience": "zeebe.camunda.io",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _download_camunda_document(document_id: str, store_id: str, content_hash: str) -> bytes:
    token = _get_oauth_token()
    url = (
        f"{CAMUNDA_REST_BASE}/v2/documents/{document_id}"
        f"?storeId={store_id}&contentHash={content_hash}"
    )
    logger.debug("Lade Dokument von REST-API: {}", url)
    resp = _requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if not resp.ok:
        raise Exception(
            f"Dokument Download Fehler {resp.status_code} für {document_id}: {resp.text[:300]}"
        )
    return resp.content


def _get_pdf_from_email(email_data: dict) -> tuple[str, str]:
    attachments = email_data.get("attachments") or []
    for attachment in attachments:
        if attachment.get("documentId"):
            metadata = attachment.get("metadata") or {}
            content_type = (metadata.get("contentType") or "").upper()
            name = metadata.get("fileName") or "rechnung.pdf"
            if "PDF" in content_type or name.lower().endswith(".pdf"):
                doc_bytes = _download_camunda_document(
                    attachment["documentId"],
                    attachment.get("storeId", "gcp"),
                    attachment.get("contentHash", ""),
                )
                return base64.b64encode(doc_bytes).decode("utf-8"), name
        else:
            content_type = (attachment.get("contentType") or "").lower()
            name = attachment.get("name") or "rechnung.pdf"
            if "pdf" in content_type or name.lower().endswith(".pdf"):
                return attachment.get("content", ""), name

    if attachments:
        first = attachments[0]
        if first.get("documentId"):
            metadata = first.get("metadata") or {}
            doc_bytes = _download_camunda_document(
                first["documentId"],
                first.get("storeId", "gcp"),
                first.get("contentHash", ""),
            )
            return base64.b64encode(doc_bytes).decode("utf-8"), metadata.get("fileName", "rechnung.pdf")
        return first.get("content", ""), first.get("name", "rechnung.pdf")

    return "", "rechnung.pdf"


def _call_n8n(pdf_base64: str, pdf_name: str, email_from: str, email_subject: str) -> dict:
    payload = json.dumps({
        "pdfContent": pdf_base64,
        "pdfName": pdf_name,
        "emailFrom": email_from,
        "emailSubject": email_subject,
    }).encode("utf-8")
    resp = _requests.post(
        N8N_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    raw = resp.text
    if not resp.ok:
        raise Exception(f"n8n Webhook Fehler {resp.status_code}: {raw[:500]}")
    if not raw.strip():
        raise Exception(
            f"n8n Webhook antwortete leer (Status {resp.status_code}). "
            "Stelle sicher, dass der Workflow in n8n AKTIV ist (Production Mode)."
        )
    try:
        return resp.json()
    except Exception:
        raise Exception(f"n8n Antwort ist kein gültiges JSON: {raw[:300]}")


def register(worker: ZeebeWorker):

    @worker.task(task_type="ai-extract-invoice")
    async def handle(emailData: dict = None, **kwargs):
        if not emailData:
            if kwargs.get("invoiceId") or kwargs.get("aiExtracted"):
                logger.info("AI Extraktion übersprungen — Daten bereits vorhanden (invoiceId={})", kwargs.get("invoiceId"))
                return {}
            raise Exception("emailData fehlt — Email Start Event hat keine Daten geliefert.")

        pdf_base64, pdf_name = _get_pdf_from_email(emailData)
        if not pdf_base64:
            raise Exception(
                f"Kein PDF-Anhang in der Mail gefunden. Anhänge: {emailData.get('attachments')}"
            )

        email_from = (
            emailData.get("fromAddress")
            or emailData.get("from")
            or emailData.get("sender")
            or ""
        )
        email_subject = emailData.get("subject") or ""

        logger.info("AI Extraktion gestartet | PDF: {} | Von: {}", pdf_name, email_from)

        n8n_response = _call_n8n(pdf_base64, pdf_name, email_from, email_subject)

        from camunda.ai_invoice_payload import normalize_ai_invoice_payload
        variables = normalize_ai_invoice_payload(
            n8n_response,
            defaults={"inputChannel": "mail", "sourcePdf": pdf_name},
        )

        logger.success(
            "AI Extraktion abgeschlossen | Rechnung: {} | Kunde: {} | Betrag: {}",
            variables.get("invoiceId"),
            variables.get("customerName"),
            variables.get("totalAmount"),
        )
        return variables
