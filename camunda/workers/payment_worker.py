import json
import re

import pika
from loguru import logger
from pyzeebe import ZeebeWorker

from camunda.config import RABBITMQ_HOST, RABBITMQ_PASS, RABBITMQ_PORT, RABBITMQ_QUEUE, RABBITMQ_USER


def register(worker: ZeebeWorker):

    @worker.task(task_type="payment-execution")
    async def handle(invoiceId: str, totalAmount: float, iban: str, currency: str = "EUR", rechnungstyp: str = "sonstiges"):
        if not invoiceId:
            raise Exception("Pflichtfeld fehlt: invoiceId ist leer.")

        if not iban:
            raise Exception("Pflichtfeld fehlt: IBAN ist leer.")

        iban_clean = iban.replace(" ", "").upper()
        if not re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$', iban_clean):
            raise Exception(f"Ungültige IBAN: '{iban}'. Format: DE89370400440532013000")

        if totalAmount <= 0:
            raise Exception(f"Ungültiger Betrag: {totalAmount}. Betrag muss größer als 0 sein.")

        logger.info(f"[Payment Worker] Veranlasse Zahlung für: {invoiceId} | Typ: {rechnungstyp} | Währung: {currency}")

        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials)
            )
            channel = connection.channel()
            # Queue muss existieren. Durable muss mit dem übereinstimmen, was in RabbitMQ bereits definiert ist.
            channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"RabbitMQ Connection Error: {e}")
            raise Exception(f"RabbitMQ nicht erreichbar unter {RABBITMQ_HOST}:{RABBITMQ_PORT}. Details: {e}")
        except Exception as e:
            logger.error(f"RabbitMQ Error: {e}")
            raise Exception(f"Fehler bei RabbitMQ Operation: {e}")

        message = {
            "invoice_id": invoiceId,
            "amount": totalAmount,
            "iban": iban,
            "currency": currency,
            "rechnungstyp": rechnungstyp,
        }

        channel.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=json.dumps(message),
        )
        connection.close()

        logger.success(f"[Payment Worker] Zahlungsauftrag für {invoiceId} gesendet.")
        return {"paymentTriggered": True}
