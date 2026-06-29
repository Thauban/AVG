# Worker-Einstiegspunkt – verbindet sich mit Camunda SaaS und wartet auf Jobs.
# Muss laufen, solange der Prozess aktiv ist.
# Ausführen: python camunda/main.py
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from pyzeebe import ZeebeWorker, create_camunda_cloud_channel

from camunda.config import (
    CAMUNDA_CLIENT_ID,
    CAMUNDA_CLIENT_SECRET,
    CAMUNDA_CLUSTER_ID,
    CAMUNDA_REGION,
)
from camunda.workers import ai_extract_worker, archive_worker, grpc_worker, payment_worker


async def main():
    logger.info("Verbinde mit Camunda SaaS...")

    channel = create_camunda_cloud_channel(
        client_id=CAMUNDA_CLIENT_ID,
        client_secret=CAMUNDA_CLIENT_SECRET,
        cluster_id=CAMUNDA_CLUSTER_ID,
        region=CAMUNDA_REGION,
    )

    worker = ZeebeWorker(channel)

    ai_extract_worker.register(worker)
    grpc_worker.register(worker)
    payment_worker.register(worker)
    archive_worker.register(worker)

    logger.success("Alle Worker registriert. Warte auf Jobs von Camunda...")
    await worker.work()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker gestoppt.")
