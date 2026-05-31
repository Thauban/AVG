# Startet eine neue Prozessinstanz in Camunda.
# Ausführen: python camunda/start_process.py
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from pyzeebe import ZeebeClient, create_camunda_cloud_channel

from camunda.config import (
    CAMUNDA_CLIENT_ID,
    CAMUNDA_CLIENT_SECRET,
    CAMUNDA_CLUSTER_ID,
    CAMUNDA_REGION,
)

PROCESS_ID = "Process_Soll_P2P_Sprint3_Improved"

now           = datetime.now()
timestamp     = now.strftime("%Y%m%d-%H%M%S")
invoice_id    = sys.argv[1] if len(sys.argv) > 1 else f"INV-{timestamp}"
total_amount  = float(sys.argv[2]) if len(sys.argv) > 2 else 4500.00
currency      = sys.argv[3] if len(sys.argv) > 3 else "EUR"
customer_name = sys.argv[4] if len(sys.argv) > 4 else "Max Mustermann GmbH"
iban          = sys.argv[5] if len(sys.argv) > 5 else "DE89370400440532013000"
input_channel = sys.argv[6] if len(sys.argv) > 6 else "mail"

TEST_INVOICE = {
    "invoiceId": invoice_id,
    "customerName": customer_name,
    "totalAmount": total_amount,
    "issueDate": now.strftime("%Y-%m-%d"),
    "iban": iban,
    "currency": currency,
    "inputChannel": input_channel,
}


async def main():
    channel = create_camunda_cloud_channel(
        client_id=CAMUNDA_CLIENT_ID,
        client_secret=CAMUNDA_CLIENT_SECRET,
        cluster_id=CAMUNDA_CLUSTER_ID,
        region=CAMUNDA_REGION,
    )

    client = ZeebeClient(channel)

    logger.info(f"Starte Prozess '{PROCESS_ID}' mit Rechnung: {TEST_INVOICE['invoiceId']}")

    instance = await client.run_process(
        bpmn_process_id=PROCESS_ID,
        variables=TEST_INVOICE,
    )

    logger.success(f"Prozess gestartet! Instanz-ID: {instance.process_instance_key}")
    logger.info("Öffne Operate um den Prozess zu verfolgen:")
    logger.info(f"https://bru-2.operate.camunda.io/{CAMUNDA_CLUSTER_ID}")

    await channel.close()


if __name__ == "__main__":
    asyncio.run(main())
