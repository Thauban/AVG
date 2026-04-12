import datetime
from loguru import logger 

class InvoiceLogic:
    def __init__(self, repository):
        self.repo = repository

    def validate_and_create(self, invoice_id, customer_name, total_amount, issue_date):
        # Ist die Rechnung gültig? (kein negativer Betrag)
        if total_amount < 0:
            return None, "Betrag darf nicht negativ sein!"
        
        # Falls kein Datum mitgegeben wurde, generieren wir eins.
        date_to_save = issue_date if issue_date else str(datetime.date.today())

        # Wir bauen das Dictionary, wie unser RequestObjekt
        invoice_object = {
            "invoice_id": invoice_id,
            "customer_name": customer_name,
            "total_amount": total_amount,
            "issue_date": date_to_save
        }

        # Wir übergeben das Dictionary an das Repo, zum speichern
        new_id = self.repo.add_object(invoice_object)
        
        return new_id, "Erfolgreich in Schichten gespeichert."
    def get_invoice_by_id(self, invoice_id):
        """Rechnung anhand der ID abrufen."""
        logger.debug(f"[Logic] Suche nach Rechnung mit ID: {invoice_id}...")

        # Rufe die Methode "get_object" mit der gewollten ID auf
        invoice = self.repo.get_object(invoice_id)
        return invoice, "Rechnung gefunden." if invoice else "Rechnung nicht gefunden."

    def get_all_invoices(self):
        """Alle Rechnungen abrufen."""
        logger.debug("[Logic] Alle Rechnungen abrufen...")
        return self.repo.list_objects(), "Alle Rechnungen"

    def delete_invoice(self, invoice_id):
        """Rechnung anhand der ID löschen."""
        logger.debug(f"[Logic] Lösche Rechnung mit ID: {invoice_id}...")
        # Rufe die Methode "delete_object" mit der Gewünschten ID auf und gebe den Status zurück
        success = self.repo.delete_object(invoice_id)
        return success, "Rechnung gelöscht." if success else "Rechnung nicht gefunden."