class InvoiceRepository:
    def __init__(self):
        self.data = {}
        self.next_id = 1

    def add_object(self, obj):
        data_id = obj["invoice_id"]
        self.data[data_id] = obj
        return data_id

    def get_object(self, data_id):
        return self.data.get(data_id)

    def list_objects(self):
        return list(self.data.values())

    def delete_object(self, data_id):
        if data_id in self.data:
            del self.data[data_id]
            return True
        return False
        