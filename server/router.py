"Router-Schicht unseres Servers"
import invoice_pb2
import invoice_pb2_grpc
from loguru import logger

class InvoiceRouter(invoice_pb2_grpc.InvoiceServiceServicer):
    def __init__(self, logic):
        # Wir speichern die Instanz der Logik-Schicht
        self.logic = logic

    def SaveMetadata(self, request, context):
        """
        Diese Methode wird aufgerufen, wenn ein gRPC-Request reinkommt.
        """
        logger.debug(f"[Router] Empfange gRPC-Request für Kunde: {request.customer_name}")

        # wir extrahieren die Daten aus dem Request-Objekt
        c_id = request.invoice_id
        name = request.customer_name
        amount = request.total_amount
        date = request.issue_date

        # Weitergabe an Die Logik-Schicht
        new_id, message = self.logic.validate_and_create(
            invoice_id=c_id,
            customer_name=name,
            total_amount=amount,
            issue_date=date
        )

        # Wir bauen das gRPC-Antwort-Objekt (InvoiceResponse) zusammen
        if new_id:
            return invoice_pb2.InvoiceResponse( # ty: ignore
                success=True,
                message=f"Server-Logik meldet: {message} (Interne ID: {new_id})"
            )
        else:
            # Falls kein neues Objekt erstellt wurde, geben wir eine Fehlermeldung zurück!
            return invoice_pb2.InvoiceResponse( # ty: ignore
                success=False,
                message=f"Abgelehnt: {message}"
            )

    def GetInvoice(self, request, context):
        """Entgegennahme eines gRPC-Requests zum Abrufen einer Rechnung anhand der ID."""
        logger.info(f"[Router] Empfange gRPC-Request zum Abrufen der Rechnung mit ID: {request.invoice_id}")

        invoice_data, message = self.logic.get_invoice_by_id(request.invoice_id)

        if invoice_data:
            return invoice_pb2.GetInvoiceResponse( # ty: ignore
                success=True,
                message=message,
                invoice_id=invoice_data["invoice_id"],
                customer_name=invoice_data["customer_name"],
                total_amount=invoice_data["total_amount"],
                issue_date=invoice_data["issue_date"]
            )
        else:
            return invoice_pb2.GetInvoiceResponse( # ty: ignore
                success=False,
                message=message
            )

    def ListInvoices(self, request, context):
        """Entgegennahme eines gRPC-Requests zum Abrufen aller Rechnungen."""
        logger.info("[Router] Empfange gRPC-Request zum Abrufen aller Rechnungen")

        invoices, message = self.logic.get_all_invoices()

        invoice_list = []
        for obj in invoices:
            invoice_list.append(
                invoice_pb2.InvoiceData( # ty: ignore
                    invoice_id=obj["invoice_id"],
                    customer_name=obj["customer_name"],
                    total_amount=obj["total_amount"],
                    issue_date=obj["issue_date"]
                )
            )

        return invoice_pb2.ListInvoicesResponse( # ty: ignore
            success=True,
            message=message,
            invoices=invoice_list
        )
    
    def DeleteInvoice(self, request, context):
        """Entgegennahme eines gRPC-Requests zum Löschen einer Rechnung anhand der ID."""
        logger.info(f"[Router] Empfange gRPC-Request zum Löschen der Rechnung mit ID: {request.invoice_id}")

        success, message = self.logic.delete_invoice(request.invoice_id)

        return invoice_pb2.InvoiceResponse( # ty: ignore
            success=success,
            message=message
        )