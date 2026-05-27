import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../client"))

import grpc
from loguru import logger
from pyzeebe import ZeebeWorker

import invoice_pb2
import invoice_pb2_grpc
from camunda.config import GRPC_SERVER


def register(worker: ZeebeWorker):

    @worker.task(task_type="register-or-update-invoice-grpc")
    async def handle(invoiceId: str, customerName: str, totalAmount: float, issueDate: str, iban: str = "", currency: str = "EUR"):
        if not invoiceId or not customerName:
            raise Exception("Pflichtfelder fehlen: invoiceId oder customerName ist leer.")

        if totalAmount < 0:
            raise Exception(f"Ungültiger Betrag: {totalAmount}. Betrag darf nicht negativ sein.")

        logger.info(f"[gRPC Worker] Speichere Rechnung: {invoiceId} | IBAN: {iban} | Währung: {currency}")

        try:
            with grpc.insecure_channel(GRPC_SERVER) as channel:
                stub = invoice_pb2_grpc.InvoiceServiceStub(channel)
                request = invoice_pb2.InvoiceRequest(
                    invoice_id=invoiceId,
                    customer_name=customerName,
                    total_amount=totalAmount,
                    issue_date=issueDate,
                    iban=iban,
                    currency=currency,
                )
                response = stub.SaveMetadata(request)
        except grpc.RpcError as e:
            raise Exception(f"gRPC Server nicht erreichbar: {e.details()}")

        if not response.success:
            raise Exception(f"gRPC Fehler: {response.message}")

        logger.success(f"[gRPC Worker] Rechnung {invoiceId} gespeichert.")
        return {"grpcSaved": True}
