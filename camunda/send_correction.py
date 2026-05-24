# Sendet eine Korrektur-Nachricht an eine wartende Prozessinstanz.
# Ausführen: python camunda/send_correction.py <invoiceId>
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from pyzeebe import ZeebeClient, create_camunda_cloud_channel

from camunda.config import (
    CAMUNDA_CLIENT_ID,
    CAMUNDA_CLIENT_SECRET,
    CAMUNDA_CLUSTER_ID,
    CAMUNDA_REGION,
)

async def main():
    if len(sys.argv) < 2:
        logger.error("Verwendung: python send_correction.py <invoiceId>")
        sys.exit(1)
    invoice_id = sys.argv[1]

    channel = create_camunda_cloud_channel(
        client_id=CAMUNDA_CLIENT_ID,
        client_secret=CAMUNDA_CLIENT_SECRET,
        cluster_id=CAMUNDA_CLUSTER_ID,
        region=CAMUNDA_REGION,
    )

    client = ZeebeClient(channel)

    await client.publish_message(
        name="Correction received",
        correlation_key=invoice_id,
        variables={"correctionProvided": True},
    )

    logger.success(f"Korrektur-Nachricht für Rechnung '{invoice_id}' gesendet.")
    await channel.close()


if __name__ == "__main__":
    asyncio.run(main())
