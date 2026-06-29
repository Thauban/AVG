r"""Lokale HTTP-Schnittstelle für n8n.

Start:
  .\.venv\Scripts\python.exe camunda\http_start_server.py

n8n kann danach per HTTP POST an http://127.0.0.1:8088/start-invoice-process
ein extrahiertes Rechnungs-JSON senden. Der Server normalisiert die Daten und
startet damit den Camunda-Prozess.
"""
import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from pyzeebe import ZeebeClient, create_camunda_cloud_channel

from camunda.ai_invoice_payload import normalize_ai_invoice_payload
from camunda.config import (
    CAMUNDA_CLIENT_ID,
    CAMUNDA_CLIENT_SECRET,
    CAMUNDA_CLUSTER_ID,
    CAMUNDA_REGION,
)


PROCESS_ID = "Process_Soll_P2P_Sprint3_Improved"
HOST = "127.0.0.1"
PORT = 8088


async def start_camunda_process_with_email(email_payload: dict):
    variables = {
        "inputChannel": "ai",
        "emailData": email_payload,
    }
    channel = create_camunda_cloud_channel(
        client_id=CAMUNDA_CLIENT_ID,
        client_secret=CAMUNDA_CLIENT_SECRET,
        cluster_id=CAMUNDA_CLUSTER_ID,
        region=CAMUNDA_REGION,
    )
    try:
        client = ZeebeClient(channel)
        instance = await client.run_process(
            bpmn_process_id=PROCESS_ID,
            variables=variables,
        )
        return {
            "success": True,
            "processInstanceKey": instance.process_instance_key,
        }
    finally:
        await channel.close()


async def start_camunda_process(payload):
    # n8n sendet den AI-Output als JSON. Vor dem Prozessstart wird dieses JSON
    # auf die Camunda-Variablen normalisiert, damit BPMN und Worker stabile
    # Feldnamen bekommen.
    variables = normalize_ai_invoice_payload(payload, defaults={"inputChannel": "ai"})

    # Die Bridge nutzt dieselben Camunda-SaaS-Zugangsdaten wie die Worker.
    # Dadurch kann n8n lokal bleiben und muss keine Camunda-SDK-Logik kennen.
    channel = create_camunda_cloud_channel(
        client_id=CAMUNDA_CLIENT_ID,
        client_secret=CAMUNDA_CLIENT_SECRET,
        cluster_id=CAMUNDA_CLUSTER_ID,
        region=CAMUNDA_REGION,
    )
    try:
        client = ZeebeClient(channel)
        # Hier passiert der eigentliche Durchstich von n8n nach Camunda:
        # Der BPMN-Prozess wird mit den extrahierten Rechnungsdaten gestartet.
        instance = await client.run_process(
            bpmn_process_id=PROCESS_ID,
            variables=variables,
        )
        return {
            "success": True,
            "processInstanceKey": instance.process_instance_key,
            "invoiceId": variables["invoiceId"],
            "variables": variables,
        }
    finally:
        await channel.close()


class CamundaStartHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        # Einheitliche JSON-Antwort für n8n. n8n zeigt diese Antwort im
        # HTTP-Request-Node an, inklusive processInstanceKey.
        response = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self):
        # Einfacher Health-Check, damit vor dem Ablauf geprüft werden kann,
        # ob die Bridge läuft.
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "camunda-http-start-server"})
            return
        self._send_json(404, {"success": False, "message": "Unbekannter Pfad"})

    def do_POST(self):
        # n8n ruft genau diesen Endpoint auf. Andere POST-Pfade werden
        # bewusst abgelehnt, damit die Bridge klein und nachvollziehbar bleibt.
        if self.path == "/start-with-email-data":
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(body) if body else {}
                result = asyncio.run(start_camunda_process_with_email(payload))
                logger.success("Camunda-Prozess mit E-Mail-Daten gestartet | Instanz: {}", result["processInstanceKey"])
                self._send_json(200, result)
            except Exception as error:
                logger.exception("Fehler beim Starten mit E-Mail-Daten")
                self._send_json(500, {"success": False, "message": str(error)})
            return

        if self.path != "/start-invoice-process":
            self._send_json(404, {"success": False, "message": "Unbekannter Pfad"})
            return

        try:
            # Request-Body aus n8n lesen und als JSON interpretieren.
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body) if body else {}
            result = asyncio.run(start_camunda_process(payload))
            logger.success(
                "Camunda-Prozess per n8n gestartet | Rechnung: {} | Instanz: {}",
                result["invoiceId"],
                result["processInstanceKey"],
            )
            self._send_json(200, result)
        except Exception as error:
            logger.exception("Fehler beim Starten des Camunda-Prozesses")
            self._send_json(500, {"success": False, "message": str(error)})

    def log_message(self, format, *args):
        logger.debug("{} - {}", self.client_address[0], format % args)


def main():
    server = ThreadingHTTPServer((HOST, PORT), CamundaStartHandler)
    logger.info("n8n-Camunda-Bridge läuft auf http://{}:{}", HOST, PORT)
    logger.info("Endpoint: POST /start-invoice-process")
    server.serve_forever()


if __name__ == "__main__":
    main()
