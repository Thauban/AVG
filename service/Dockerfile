# Basis Image mit Python 3.11
FROM python:3.11-slim

# Arbeitsverzeichnis in Container festlegen
WORKDIR /app

# Abhängigkeiten kopieren und installieren
# Wir kopieren nur die requirements.txt um Cache optimal zu nutzen
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Service Code in den Container kopieren
COPY service/ .

# Worker ausführen beim Start des Containers
CMD ["python", "payment_system.py"]
