from loguru import logger
from pyzeebe import ZeebeWorker


def register(worker: ZeebeWorker):

    @worker.task(task_type="archive-invoice")
    async def handle(invoiceId: str, customerName: str = "", totalAmount: float = 0.0, notiz: str = ""):
        logger.info(f"[Archive Worker] Archiviere Rechnung: {invoiceId} | Kunde: {customerName} | Betrag: {totalAmount}")
        if notiz:
            logger.info(f"[Archive Worker] Notiz: {notiz}")
        return {"archived": True}
