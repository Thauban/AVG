"""Startet eine neue Prozessinstanz in Camunda.

Ausführen:
  python camunda/start_process.py
  python camunda/start_process.py INV-1 1200 EUR "Muster GmbH" DE89370400440532013000 mail
  python camunda/start_process.py --json n8n/extracted_invoice.example.json
"""
import argparse
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from pyzeebe import ZeebeClient, create_camunda_cloud_channel

from camunda.config import (
    CAMUNDA_CLIENT_ID,
    CAMUNDA_CLIENT_SECRET,
    CAMUNDA_CLUSTER_ID,
    CAMUNDA_REGION,
)
from camunda.ai_invoice_payload import load_ai_invoice_payload

PROCESS_ID = "Process_Soll_P2P_Sprint3_Improved"


def build_process_variables():
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")

    parser = argparse.ArgumentParser(description="Startet den Camunda-Rechnungsprozess.")
    parser.add_argument("invoice_id", nargs="?", default=f"INV-{timestamp}")
    parser.add_argument("total_amount", nargs="?", type=float, default=0.0)
    parser.add_argument("currency", nargs="?", default="EUR")
    parser.add_argument("customer_name", nargs="?", default="Max Mustermann GmbH")
    parser.add_argument("iban", nargs="?", default="DE89370400440532013000")
    parser.add_argument("input_channel", nargs="?", default="mail")
    parser.add_argument("--json", dest="ai_json", help="JSON-Datei mit n8n/AI-Extraktionsergebnis.")
    parser.add_argument("--pdf-name", default="", help="Name der extrahierten Rechnungs-PDF.")
    args = parser.parse_args()

    defaults = {
        "invoiceId": args.invoice_id,
        "customerName": args.customer_name,
        "totalAmount": args.total_amount,
        "issueDate": now.strftime("%Y-%m-%d"),
        "iban": args.iban,
        "currency": args.currency,
        "inputChannel": args.input_channel,
        "sourcePdf": args.pdf_name,
        "kundennummer": "KD-001",
        "zahlungsziel": "14 Tage netto",
        "rechnungstyp": "lieferung",
        "positionen": [
            {
                "beschreibung": "Laptop Dell XPS 15",
                "menge": 2,
                "einheit": "Stk.",
                "einzelpreis": 1200.00,
                "steuerProzent": 19,
            },
            {
                "beschreibung": "Maus Logitech MX",
                "menge": 5,
                "einheit": "Stk.",
                "einzelpreis": 80.00,
                "steuerProzent": 19,
            },
        ],
    }

    if args.ai_json:
        variables = load_ai_invoice_payload(args.ai_json, defaults)
        if not variables["invoiceId"]:
            variables["invoiceId"] = f"INV-{timestamp}"
        return variables

    return defaults


async def main():
    channel = create_camunda_cloud_channel(
        client_id=CAMUNDA_CLIENT_ID,
        client_secret=CAMUNDA_CLIENT_SECRET,
        cluster_id=CAMUNDA_CLUSTER_ID,
        region=CAMUNDA_REGION,
    )

    client = ZeebeClient(channel)
    process_variables = build_process_variables()

    logger.info(f"Starte Prozess '{PROCESS_ID}' mit Rechnung: {process_variables['invoiceId']}")
    if process_variables.get("aiExtracted"):
        logger.info("AI-Extraktion geladen: {}", process_variables.get("sourcePdf") or "JSON-Payload")

    instance = await client.run_process(
        bpmn_process_id=PROCESS_ID,
        variables=process_variables,
    )

    logger.success(f"Prozess gestartet! Instanz-ID: {instance.process_instance_key}")
    logger.info("Öffne Operate um den Prozess zu verfolgen:")
    logger.info(f"https://bru-2.operate.camunda.io/{CAMUNDA_CLUSTER_ID}")

    await channel.close()


if __name__ == "__main__":
    asyncio.run(main())
