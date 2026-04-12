"""
Konfigurationsdatei des Clients.

Hier werden die Verbindungsdaten fuer den gRPC-Server und RabbitMQ
sowie die Standardwaehrung fuer Zahlungsnachrichten zentral verwaltet.
"""

import os

GRPC_SERVER = os.getenv("GRPC_SERVER", "localhost:50051")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "avg123")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "payment_queue")

DEFAULT_CURRENCY = "EUR"
