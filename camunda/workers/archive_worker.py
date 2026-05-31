import json
from datetime import datetime
from pathlib import Path

from loguru import logger
from pyzeebe import ZeebeWorker


ARCHIVE_DIR = Path("archive/invoices")


def register(worker: ZeebeWorker):

    @worker.task(task_type="archive-invoice")
    async def handle(invoiceId: str, customerName: str = "", totalAmount: float = 0.0, notiz: str = ""):
        # Der Ordner wird zur Laufzeit erstellt und ist per .gitignore vom Commit ausgeschlossen.
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        # Archivdaten als einfache JSON-Struktur fuer Demo und Nachvollziehbarkeit.
        archive_data = {
            "invoiceId": invoiceId,
            "customerName": customerName,
            "totalAmount": totalAmount,
            "notiz": notiz,
            "archivedAt": datetime.now().isoformat(timespec="seconds"),
            "status": "archived",
        }

        archive_file = ARCHIVE_DIR / f"{invoiceId}.json"

        # In einem echten System waere hier z.B. ein DMS, ERP-Archiv oder Cloud-Speicher angebunden.
        with archive_file.open("w", encoding="utf-8") as file:
            json.dump(archive_data, file, indent=2, ensure_ascii=False)

        logger.success(
            "[ARCHIV] Rechnung {} archiviert | Datei: {}",
            invoiceId,
            archive_file,
        )

        # Rueckgabe an Camunda: Der Dateipfad ist spaeter in Operate als Prozessvariable sichtbar.
        return {
            "archived": True,
            "archiveFile": str(archive_file),
        }
