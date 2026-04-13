"Zahlungssystem: Konsumiert Zahlungsaufträge von RabbitMQ"
import pika
import json
import time
import sys
from loguru import logger
from config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_QUEUE, RABBITMQ_USER, RABBITMQ_PASS

def callback(ch, method, properties, body):
    """
    Diese Funktion wird aufgerufen, wenn eine neue Nachricht in der Queue ankommt.
    """
    try:
        # 1. Daten extrahieren (JSON parsen)
        payment_data = json.loads(body)
        
        invoice_id = payment_data.get('invoice_id')
        amount = payment_data.get('amount')
        currency = payment_data.get('currency')

        logger.info(f"[Worker] Neuer Auftrag: Rechnung {invoice_id} ({amount} {currency})")
        
        # 2. Verarbeitung simulieren
        # Hier könnte später eine echte Bank-API angebunden werden.
        logger.debug(f"[Worker] Verarbeite Zahlung für {invoice_id}...")
        time.sleep(2) # Wir tun so als ob wir arbeiten
        
        logger.info(f"[Worker] Zahlung für {invoice_id} erfolgreich abgeschlossen!")
        
        # 3. Bestätigung (Acknowledge)
        # Damit RabbitMQ weiß, dass die Nachricht sicher verarbeitet wurde
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"[Worker] Fehler bei der Verarbeitung: {e}")

def main():
    """Hauptfunktion zum Starten des Workers"""
    try:
        # Zugangsdaten für RabbitMQ vorbereiten
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        
        # Verbindung aufbauen
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=RABBITMQ_HOST, 
            port=RABBITMQ_PORT, 
            credentials=credentials
        ))
        channel = connection.channel()

        # Sicherstellen, dass die payment_queue existiert
        channel.queue_declare(queue=RABBITMQ_QUEUE)

        # Nur eine Nachricht nach der anderen bearbeiten also keine neue Nachricht bevor ack
        channel.basic_qos(prefetch_count=1)
        
        # Konsumierung starten
        channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

        logger.info(f'[*] Zahlungssystem gestartet. Warte in der Schlange "{RABBITMQ_QUEUE}"...')
        channel.start_consuming()

    except pika.exceptions.ProbableAuthenticationError:
        logger.error(f"[Worker] Login fehlgeschlagen! User '{RABBITMQ_USER}' ist ungültig oder Passwort falsch.")
        sys.exit(1)
    except pika.exceptions.AMQPConnectionError:
        logger.error(f"[Worker] RabbitMQ unter {RABBITMQ_HOST}:{RABBITMQ_PORT} nicht erreichbar! Läuft der Docker-Container?")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[Worker] Unerwarteter Fehler: {e}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info('[Worker] Beende Zahlungssystem (Strg+C)...')
        sys.exit(0)
