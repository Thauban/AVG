# AVG Rechnungs- und Zahlungssystem (Sprint 1)

Hier ist unser Projekt für den ersten Sprint. Wir haben ein System gebaut, das Rechnungen über gRPC speichert und Zahlungen über RabbitMQ verarbeitet.

## Projektstruktur
- `server/`: Der gRPC Server (speichert die Rechnungen).
- `service/`: Das Zahlungssystem (unser RabbitMQ Worker).
- `client/`: Ein Test-Client, um alles auszuprobieren.
- `shared/`: Die gRPC Definitionen (.proto Datei).
- `compose/`: Docker Einstellungen für RabbitMQ.

## Voraussetzungen
- Python 3
- Docker (für RabbitMQ)

## Wie man es startet

### 1. RabbitMQ starten
Zuerst müssen wir die Infrastruktur mit Docker starten:
```bash
cd compose
docker-compose up -d
```
Danach ist das RabbitMQ Dashboard unter `http://127.0.0.1:15672` erreichbar (User: `admin`, Pass: `avg123`).

### 2. Abhängigkeiten installieren (einmalig)
```bash
pip install -r requirements.txt
```

### 3. Komponenten starten (in verschiedenen Terminals)

**Terminal 1 (Server):**
```bash
python3 server/main.py
```

**Terminal 2 (Zahlungssystem):**
```bash
python3 service/payment_system.py
```

**Terminal 3 (Client Test):**
```bash
python3 client/client.py
```

## Was wir gemacht haben
- Wir nutzen **gRPC** für die Kommunikation zwischen Client und Server (schnell und sicher).
- Für die Zahlungen nutzen wir **RabbitMQ**, damit der Prozess asynchron läuft.
- Alles ist in Docker verpackt, damit es überall gleich läuft.
