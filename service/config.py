"Zentrale Konfiguration für das Zahlungssystem"
import os

# RabbitMQ-Verbindungseinstellungen
# Wir nutzen Umgebungsvariablen, damit es in Docker und Lokal funktioniert.
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))

# Standard-Zugangsdaten (admin/avg123)
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "avg123")

# Name der Warteschlange
RABBITMQ_QUEUE = "payment_queue"

# Logging-Level (INFO, DEBUG, ERROR)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
