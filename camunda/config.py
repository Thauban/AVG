import os
from dotenv import load_dotenv

load_dotenv()

CAMUNDA_CLUSTER_ID    = os.getenv("CAMUNDA_CLUSTER_ID")
CAMUNDA_REGION        = os.getenv("CAMUNDA_REGION", "bru-2")
CAMUNDA_CLIENT_ID     = os.getenv("CAMUNDA_CLIENT_ID")
CAMUNDA_CLIENT_SECRET = os.getenv("CAMUNDA_CLIENT_SECRET")

GRPC_SERVER    = os.getenv("GRPC_SERVER", "localhost:50051")
RABBITMQ_HOST  = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT  = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER  = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS  = os.getenv("RABBITMQ_PASS")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "payment_queue")
