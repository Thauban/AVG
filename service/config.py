"Zentrale Konfiguration für das Zahlungssystem"
import os
from pathlib import Path
from dotenv import load_dotenv

# Ermittle das Verzeichnis des Projekts (eine Ebene über dem Service-Ordner)
BASE_DIR = Path(__file__).resolve().parent.parent
DOTENV_PATH = BASE_DIR / ".env"

# Lade Umgebungsvariablen aus .env Datei
if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH)
else:
    # Fallback, falls .env woanders liegt oder bereits geladen wurde
    load_dotenv()

# RabbitMQ-Verbindungseinstellungen
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))

# Zugangsdaten (kommen nun ausschließlich aus .env oder Umgebungsvariablen)
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")

# Name der Warteschlange
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "payment_queue")

# Logging-Level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
