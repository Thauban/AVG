# AVG - Automatisierte Verarbeitung von Eingangsrechnungen

Dieses Repository enthält unsere Gesamtanwendung aus dem Projekt
"Digitalisierung eines Geschäftsprozesses". Wir haben einen
Purchase-to-Pay-Prozess mit Camunda umgesetzt.

Zum Einsatz kommen Python, gRPC, PostgreSQL, RabbitMQ, Camunda 8, n8n, Gemini
und UiPath. Das UiPath-Projekt wird außerhalb dieses Runtime-Repositories in
UiPath verwaltet.

## Ablauf

```text
E-Mail / Portal / EDI
        |
        v
n8n/Gemini extrahiert Rechnungsdaten
        |
        v
Menschliche Kontrolle in Camunda
        |
        v
gRPC speichert Rechnung und Positionen in PostgreSQL
        |
        v
DMN entscheidet über Compliance-Prüfung
        |
        v
Fachliche Prüfung und Freigabe
        |
        v
ERP-/UiPath-Schritt
        |
        v
RabbitMQ übergibt den Zahlungsauftrag
        |
        v
Archivierung
```

In der aktuell deployten Prozessversion 58 folgt auf die gRPC-Speicherung
direkt die DMN-Entscheidung. Die frühere doppelte Eingabe von Betrag und IBAN
wurde entfernt.

## Projektstruktur

```text
AVG/
├── camunda/                 BPMN, DMN, Prozessstart und Zeebe Worker
├── client/                  Test-Client für gRPC und RabbitMQ
├── compose/                 PostgreSQL, RabbitMQ, pgAdmin und n8n
├── docs/                    Schemas, Prompt und technische Dokumentation
├── invoices/                Lokaler PDF-Austauschordner für n8n
├── n8n/                     Importierbare Workflows
├── rpa/                     RPA-Testrechnung
├── server/                  gRPC-Server und PostgreSQL-Repository
├── service/                 RabbitMQ Payment-Consumer
└── shared/invoice.proto     gRPC-Schnittstelle
```

## Voraussetzungen

- Python 3.10 oder neuer
- Docker Desktop
- Camunda 8 SaaS Cluster
- n8n und ein Gemini-Zugang für die PDF-Extraktion
- optional UiPath für den RPA-Teil

## Einrichtung

### Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Die generierten gRPC-Dateien sind nicht im Repository und müssen bei einer
frischen Installation erzeugt werden:

```powershell
.\.venv\Scripts\python.exe -m grpc_tools.protoc -I shared --python_out=client --grpc_python_out=client shared/invoice.proto
.\.venv\Scripts\python.exe -m grpc_tools.protoc -I shared --python_out=server --grpc_python_out=server shared/invoice.proto
```

### Konfiguration

Im Projektroot wird eine lokale `.env` benötigt:

```env
CAMUNDA_CLUSTER_ID=<cluster-id>
CAMUNDA_REGION=bru-2
CAMUNDA_CLIENT_ID=<client-id>
CAMUNDA_CLIENT_SECRET=<client-secret>

DATABASE_URL=postgresql://sachbearbeiter:<passwort>@localhost:5432/rechnung

RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=<benutzer>
RABBITMQ_PASS=<passwort>
RABBITMQ_QUEUE=payment_queue

GRPC_SERVER=localhost:50051
```

Die `.env` wird nicht committed. Die einmalige PostgreSQL-Einrichtung mit
Volumes und TLS ist in
[`compose/postgres/ReadMe.md`](compose/postgres/ReadMe.md) beschrieben.

## Anwendung starten

Alle Befehle werden im Projektroot ausgeführt.

### 1. Docker-Dienste

```powershell
docker compose -f compose\compose.yml up -d
docker compose -f compose\compose.yml ps
```

Falls die Container lokal bereits vorhanden und nur gestoppt sind:

```powershell
docker start postgres avg-mq n8n
```

### 2. Camunda-Worker

```powershell
.\.venv\Scripts\python.exe camunda\main.py
```

### 3. Payment-Consumer

```powershell
.\.venv\Scripts\python.exe service\payment_system.py
```

### 4. gRPC-Server

```powershell
.\.venv\Scripts\python.exe server\main.py
```

Der manuelle Start ist optional. Wenn `localhost:50051` beim gRPC-Task nicht
erreichbar ist, startet der Camunda-Worker `server/main.py` selbst, wartet auf
den Port und wiederholt den Speichervorgang. Beide Fälle wurden getestet:
vorher gestarteter Server und automatischer Start.

### 5. n8n-Camunda-Bridge

Nur nötig, wenn n8n den Prozess starten soll:

```powershell
.\.venv\Scripts\python.exe camunda\http_start_server.py
Invoke-RestMethod http://localhost:8088/health
```

## Prozess testen

Direkter Test:

```powershell
.\.venv\Scripts\python.exe camunda\start_process.py
```

Test mit Beispiel-JSON:

```powershell
.\.venv\Scripts\python.exe camunda\start_process.py --json n8n\extracted_invoice.example.json --pdf-name beispielrechnung.pdf
```

Integrierter n8n-Test:

1. n8n unter `http://localhost:5678` öffnen.
2. `n8n/invoice_ai_to_camunda_workflow.json` importieren.
3. Die HTTP-Bridge starten.
4. Den Workflow ausführen.

Die Workflows für E-Mail-Eingang und PDF-Extraktion liegen im Ordner `n8n/`.
Nach dem Import müssen die E-Mail- und Gemini-Credentials in n8n ausgewählt
werden. Der Webhook-Workflow muss im Production Mode aktiv sein.

## Datenbank prüfen

```powershell
docker exec -it postgres psql -U sachbearbeiter -d rechnung
```

```sql
SELECT invoice_id, customer_name, kundennummer, zahlungsziel,
       total_amount, currency, issue_date
FROM rechnung.rechnung;

SELECT invoice_id, pos_nummer, beschreibung, menge, einheit,
       einzelpreis, steuer_prozent, netto, steuer_betrag, brutto
FROM rechnung.rechnungsposition
WHERE invoice_id = 'INV-...';
```

Beenden mit `\q`.

## Zugangsdaten

Reale Zugangsdaten gehören nicht in dieses Repository:

- Camunda E-Mail-Connector: `{{secrets.INVOICE_EMAIL_USERNAME}}` und
  `{{secrets.INVOICE_EMAIL_PASSWORD}}` als Connector Secrets anlegen.
- n8n: E-Mail- und Gemini-Zugänge nach dem Import im Credential Store
  konfigurieren.
- `.env`, Datenbankpasswort, Zertifikate und private Schlüssel lokal halten.
- Ein bereits veröffentlichtes Passwort muss unabhängig von der Entfernung aus
  Git beim jeweiligen Anbieter geändert werden.

## Einsatz von KI

Gemini ist als fachlicher Bestandteil der PDF-Extraktion in n8n integriert.
Darüber hinaus wurden KI-Werkzeuge bei der Entwicklung und Dokumentation unterstützend
verwendet, unter anderem OpenAI Codex und Google Antigravity. Vorschläge wurden
von uns geprüft, angepasst und durch eigene Testläufe validiert. Die fachlichen
Entscheidungen und die Verantwortung für den abgegebenen Stand liegen bei der
Projektgruppe.

## Hinweise

- Der Payment-Consumer simuliert eine Banktransaktion.
- Das lokale JSON-Archiv ersetzt kein produktives Dokumentenmanagementsystem.
- Das UiPath-Projekt wird außerhalb dieses Repositories verwaltet.
- Nach Änderungen im Web Modeler sollte die aktuelle BPMN-Datei exportiert und
  unter `camunda/` aktualisiert werden.

Weitere Details:

- [`camunda/README.md`](camunda/README.md)
- [`n8n/README.md`](n8n/README.md)
- [`docs/ai_invoice_extraction.md`](docs/ai_invoice_extraction.md)
- [`docs/sequence_diagram.puml`](docs/sequence_diagram.puml)
