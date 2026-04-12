class InvoiceRepository:
    def __init__(self):
        # MockDB als Dictionary (ID -> Objekt)
        self.data = {}

    def add_object(self, obj):
        """Neue Rechnung in MockDB speichern und ID zurückgeben."""
        data_id = obj["invoice_id"]
        self.data[data_id] = obj
        return data_id

    def get_object(self, data_id):
        """Objekt mit gesuchter ID zurückgeben."""
        return self.data.get(data_id)

    def list_objects(self):
        """Liste der gespeicherten Objekte zurückgeben."""
        return list(self.data.values())

    def delete_object(self, data_id):
        """Objekt mit gegebener ID löschen."""
        if data_id in self.data:
            del self.data[data_id]
            return True
        return False
