"""
Lokaler Client zum Testen des Rechnungs- und Zahlungssystems.

Der Client fuehrt einen kompletten Beispielablauf aus:
1. Mehrere Rechnungsdaten per gRPC an den Server senden
2. Gespeicherte Rechnungen abrufen
3. Eine Rechnung loeschen und die Loeschung pruefen
4. Rechnungslisten vor und nach dem Loeschen anzeigen
5. Zahlungsauftraege fuer verbleibende Rechnungen an RabbitMQ senden

Damit dient die Datei als Test- und Demonstrationsclient fuer die
Kommunikation mit dem gRPC-Server und dem RabbitMQ-Broker.

Hinweis: Umlaute wurden im Code bewusst als ae/oe/ue geschrieben
"""

import json
import time

import grpc
import pika
from loguru import logger

import invoice_pb2
import invoice_pb2_grpc
from config import (
    DEFAULT_CURRENCY,
    GRPC_SERVER,
    RABBITMQ_HOST,
    RABBITMQ_PASS,
    RABBITMQ_PORT,
    RABBITMQ_QUEUE,
    RABBITMQ_USER,
)

def build_invoices():
    """Erzeugt drei Beispielrechnungen fuer den Testlauf des Clients.

    Die Rechnungen dienen dazu, verschiedene Faelle im Server zu pruefen:
    Speichern, Abrufen, Loeschen und das Anzeigen mehrerer Eintraege in
    einer Rechnungsliste.
    """

    return [
        invoice_pb2.InvoiceRequest(
            invoice_id="INV-2024-001",
            customer_name="Max Mustermann",
            total_amount=149.99,
            issue_date="2024-04-07",
        ),
        invoice_pb2.InvoiceRequest(
            invoice_id="INV-2024-002",
            customer_name="Erika Musterfrau",
            total_amount=89.50,
            issue_date="2024-04-08",
        ),
        invoice_pb2.InvoiceRequest(
            invoice_id="INV-2024-003",
            customer_name="Hans Beispiel",
            total_amount=219.00,
            issue_date="2024-04-09",
        ),
    ]


def save_invoice(stub, invoice_data):
    """Speichert eine Rechnung ueber die gRPC-Methode `SaveMetadata`.

    Die Funktion sendet die Rechnungsdaten an den Server und protokolliert,
    ob die Speicherung erfolgreich war und welche Rueckmeldung der Server
    geliefert hat.
    """

    logger.info("Sende Rechnungsdaten für ID '{}' an den gRPC-Server...", invoice_data.invoice_id)
    response = stub.SaveMetadata(invoice_data)
    logger.success("Rechnung '{}' erfolgreich gespeichert.", invoice_data.invoice_id)
    logger.info("Server-Antwort: {}", response.message)


def get_invoice(stub, invoice_id):
    """Ruft eine Rechnung ueber ihre ID vom gRPC-Server ab.

    Die Funktion prueft, ob eine gespeicherte Rechnung anhand ihrer
    Rechnungs-ID wiedergefunden werden kann, und protokolliert die
    zurueckgegebenen Rechnungsdaten.
    """

    logger.info("Versuche Rechnung mit ID '{}' abzurufen...", invoice_id)
    request = invoice_pb2.InvoiceLookupRequest(invoice_id=invoice_id)
    response = stub.GetInvoice(request)

    if response.success:
        logger.success("Rechnung gefunden.")
        logger.info(
            "Details: Kunde: {}, Betrag: {}, Datum: {}",
            response.customer_name,
            response.total_amount,
            response.issue_date,
        )
    else:
        logger.warning("Rechnung mit ID '{}' wurde nicht gefunden.", invoice_id)
        logger.info("Server-Antwort: {}", response.message)


def delete_invoice(stub, invoice_id):
    """Loescht eine Rechnung ueber den gRPC-Server und prueft das Ergebnis.

    Wird die Rechnung erfolgreich geloescht, folgt eine Verifikation durch
    einen erneuten Abruf. Bei nicht vorhandenen Rechnungen wird nur der
    Fehlerfall protokolliert.
    """

    logger.warning("Lösche Rechnung mit ID '{}'...", invoice_id)
    request = invoice_pb2.InvoiceLookupRequest(invoice_id=invoice_id)
    response = stub.DeleteInvoice(request)

    if response.success:
        logger.success("Rechnung '{}' erfolgreich gelöscht.", invoice_id)
        logger.info("Server-Antwort: {}", response.message)

        logger.info("Prüfe, ob die gelöschte Rechnung nicht mehr abrufbar ist...")
        check_response = stub.GetInvoice(request)

        if not check_response.success:
            logger.success("Verifikation erfolgreich: Rechnung ist nicht mehr auffindbar.")
        else:
            logger.warning("Verifikation fehlgeschlagen: Rechnung ist noch vorhanden.")
    else:
        logger.error("Löschen fehlgeschlagen: {}", response.message)


def list_invoices(stub):
    """Fordert die aktuelle Liste aller gespeicherten Rechnungen vom Server an.

    Neben der Protokollierung der Rueckgabe liefert die Funktion die Liste
    der Rechnungen zurueck, damit nachfolgende Verarbeitungsschritte auf
    den verbleibenden Eintraegen arbeiten koennen.
    """

    logger.info("Fordere Liste aller Rechnungen vom Server an...")
    request = invoice_pb2.EmptyLookup()
    response = stub.ListInvoices(request)

    if response.success:
        logger.success("Rechnungsliste erfolgreich abgerufen.")
        logger.info("Server-Antwort: {}", response.message)

        for inv in response.invoices:
            logger.info(
                "Rechnung -> ID: {}, Kunde: {}, Betrag: {} EUR, Datum: {}",
                inv.invoice_id,
                inv.customer_name,
                inv.total_amount,
                inv.issue_date,
            )

        return response.invoices
    else:
        logger.warning("Fehler beim Abrufen der Liste: {}", response.message)
        return []



def publish_payment(invoice_data):
    """Sendet einen Zahlungsauftrag fuer eine Rechnung an RabbitMQ.

    An RabbitMQ werden nur die fuer den Zahlungsprozess relevanten Daten
    uebermittelt: Rechnungs-ID, Betrag und Waehrung. Die Uebertragung
    erfolgt asynchron ueber die konfigurierte Queue.
    """

    logger.info(
        "Sende Zahlungsauftrag für Rechnung '{}' an RabbitMQ...",
        invoice_data.invoice_id,
    )

    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
    )

    connection = None

    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_QUEUE)

        payment_message = {
            "invoice_id": invoice_data.invoice_id,
            "amount": invoice_data.total_amount,
            "currency": DEFAULT_CURRENCY,
        }

        channel.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=json.dumps(payment_message),
        )

        logger.success("Zahlungsauftrag erfolgreich an RabbitMQ gesendet.")
        logger.info("Gesendete Zahlungsdaten: {}", payment_message)

    finally:
        if connection is not None and connection.is_open:
            connection.close()


def run():
    """Steuert den kompletten Testablauf des Clients.

    Der Ablauf umfasst das Erzeugen mehrerer Beispielrechnungen, deren
    Verarbeitung ueber gRPC sowie das anschliessende Senden von
    Zahlungsauftraegen fuer die nach dem Loeschvorgang verbleibenden
    Rechnungen an RabbitMQ.
    """

    logger.info("Starte Client-Testlauf für das Rechnungs- und Zahlungssystem.")

    try:
        with grpc.insecure_channel(GRPC_SERVER) as channel:
            stub = invoice_pb2_grpc.InvoiceServiceStub(channel)

            invoices = build_invoices()

            first_invoice = invoices[0]
            second_invoice = invoices[1]
            third_invoice = invoices[2]

            # Alle drei Rechnungen speichern
            save_invoice(stub, first_invoice)
            save_invoice(stub, second_invoice)
            save_invoice(stub, third_invoice)

            # Alle drei Rechnungen abrufen
            get_invoice(stub, first_invoice.invoice_id)
            get_invoice(stub, second_invoice.invoice_id)
            get_invoice(stub, third_invoice.invoice_id)

            # Erste Liste: hier sollten 3 Rechnungen vorhanden sein
            list_invoices(stub)

            # Eine existierende Rechnung loeschen
            delete_invoice(stub, first_invoice.invoice_id)

            # Zweite Liste: hier sollten nur noch 2 Rechnungen vorhanden sein
            remaining_invoices = list_invoices(stub)

            # Optionaler Fehlerfall: nicht existierende Rechnung loeschen
            delete_invoice(stub, "INV-9999")


    except grpc.RpcError as error:
        logger.error("gRPC Fehler: {}", error.details())
        return

    try:
        for invoice_data in remaining_invoices:
            publish_payment(invoice_data)
    except pika.exceptions.AMQPConnectionError:
        logger.error("RabbitMQ Fehler: Verbindung fehlgeschlagen. Läuft der RabbitMQ-Server?")
        return

    logger.success("Client-Testlauf abgeschlossen.")



if __name__ == "__main__":
    time.sleep(1)
    run()
