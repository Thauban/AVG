# AVG – Automatisiertes Rechnungs- und Zahlungssystem (Gruppe 2)

Digitaler Purchase-to-Pay Prozess auf Basis von **Camunda 8 SaaS**, **Python**, **gRPC** und **RabbitMQ**.
Rechnungen werden digital erfasst, fachlich und compliance-seitig geprüft und abschließend per Zahlungsauftrag verarbeitet.

---

## Projektstruktur

```
AVG/
├── camunda/              # Camunda-Schicht (Workflow-Orchestrierung)
│   ├── main.py           # Startet alle Zeebe Worker
│   ├── start_process.py  # Startet neue Prozessinstanz
│   ├── send_correction.py# Sendet Korrektur-Nachricht an wartenden Prozess
│   ├── config.py         # Liest .env Variablen
│   ├── compliance_check.dmn    # DMN-Entscheidungstabelle (Compliance-Schwellwerte)
│   ├── G2_Invoice-ERP-Automation.bpmn  # BPMN-Prozessmodell
│   └── workers/
│       ├── grpc_worker.py      # Task: register-or-update-invoice-grpc
│       ├── payment_worker.py   # Task: payment-execution
│       └── archive_worker.py   # Task: archive-invoice
├── server/               # gRPC Server (speichert Rechnungen im RAM)
├── client/               # Test-Client für gRPC
├── service/              # RabbitMQ Payment-Consumer
├── shared/               # .proto Definitionen (invoice.proto)
├── compose/              # Docker Compose für RabbitMQ
└── docs/                 # Dokumentation und Diagramme
```

---

## Architektur

```
Camunda 8 SaaS (BPMN + DMN)
        │
        │  Zeebe Jobs
        ▼
  Python Worker (pyzeebe)
   ├── gRPC Worker       → speichert Rechnungsmetadaten
   ├── Payment Worker    → sendet Zahlungsauftrag an RabbitMQ
   └── Archive Worker    → archiviert abgeschlossene Rechnungen
        │
        ├──▶ gRPC Server (localhost:50051)
        └──▶ RabbitMQ    (localhost:5672)
```

**Prozessablauf:**
1. Rechnung wird erfasst und im gRPC-Server gespeichert
2. Sachbearbeiter prüft und entscheidet (freigeben / ablehnen / Korrektur anfordern)
3. DMN-Tabelle prüft automatisch ob Compliance-Check nötig ist (nach Betrag & Währung)
4. Bei Bedarf: manueller Compliance-Check
5. ERP-Buchung und finale Freigabe
6. Zahlungsauftrag wird über RabbitMQ gesendet
7. Rechnung wird archiviert

---

## Voraussetzungen

- Python 3.10+
- Docker (für RabbitMQ)
- Camunda 8 SaaS Zugangsdaten (Cluster-ID, Client-ID, Client-Secret)
- `.env` Datei im Projektroot (siehe unten)

---

## Einrichtung

### 1. Umgebungsvariablen konfigurieren

Lege eine `.env` Datei im Projektroot an:

```env
# Camunda SaaS
CAMUNDA_CLUSTER_ID=<cluster-id>
CAMUNDA_REGION=bru-2
CAMUNDA_CLIENT_ID=<client-id>
CAMUNDA_CLIENT_SECRET=<client-secret>

# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASS=<passwort>
RABBITMQ_QUEUE=payment_queue

# gRPC
GRPC_SERVER=localhost:50051
```

> Die `.env` Datei wird nicht ins Git committed (steht in `.gitignore`).

### 2. Virtuelle Umgebung einrichten (einmalig)

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Proto-Dateien generieren (einmalig)

Die generierten gRPC-Dateien sind nicht im Git — sie müssen lokal erstellt werden:

```bash
python -m grpc_tools.protoc -I shared --python_out=client --grpc_python_out=client shared/invoice.proto
python -m grpc_tools.protoc -I shared --python_out=server --grpc_python_out=server shared/invoice.proto
```

> Nach jeder Änderung an `shared/invoice.proto` muss dieser Schritt wiederholt werden.

---

## Starten (in verschiedenen Terminals)

> Alle Befehle vom **Projektroot** (`AVG/`) ausführen.

### Terminal 1 – RabbitMQ starten
```bash
cd compose
docker-compose up -d
```
RabbitMQ Dashboard: `http://127.0.0.1:15672` (User: `admin`, Pass: siehe `.env`)

### Terminal 2 – gRPC Server starten
```bash
python server/main.py
```

### Terminal 3 – Camunda Worker starten
Verbindet sich mit Camunda SaaS und wartet auf eingehende Jobs:
```bash
python camunda/main.py
```

### Terminal 4 – Prozess starten
Startet eine neue Prozessinstanz in Camunda:
```bash
python camunda/start_process.py
```
Die Invoice-ID und der Operate-Link erscheinen in den Logs.

---

## Prozess in der Camunda Tasklist bearbeiten

Die Aufgaben erscheinen automatisch in der **Camunda Tasklist**.
Folgende manuelle Tasks sind im Prozess enthalten:

| Formular | Beschreibung |
|---|---|
| Erfassung der Rechnungsdaten | Rechnungsdaten inkl. Währung eingeben |
| Rechnung vorprüfen | Erste Prüfung durch Sachbearbeiter |
| Rechnung fachlich prüfen | Entscheidung: freigeben / ablehnen / Korrektur |
| Compliance-Check manuell | Manuelle Compliance-Prüfung (nur bei Bedarf) |
| ERP-Buchung manuell | Buchung im ERP-System bestätigen |
| Rechnung final freigeben | Abschließende Freigabe |

---

## Korrektur senden (falls nötig)

Wenn ein Sachbearbeiter „Korrektur anfordern" auswählt, wartet der Prozess auf eine Korrektur-Nachricht.
Die Invoice-ID steht in den Logs von `start_process.py`.

```bash
python camunda/send_correction.py <invoiceId>
```

---

## AI-Extraktion mit n8n

Der Prozess kann Rechnungsdaten aus PDFs über einen n8n-Workflow übernehmen. n8n läuft lokal in Docker und erzeugt ein JSON mit Metadaten und Rechnungspositionen. Dieses JSON kann direkt als Camunda-Prozessvariablen verwendet werden:

```bash
cd compose/n8n
docker compose up -d

python camunda/start_process.py --json n8n/extracted_invoice.example.json --pdf-name beispielrechnung.pdf
```

Details zum JSON-Format und Ablauf stehen in `docs/ai_invoice_extraction.md`.

---

## DMN – Compliance-Schwellwerte

Die Compliance-Prüfung läuft automatisch per DMN-Tabelle (`compliance_check.dmn`).
Rechnungen über den folgenden Schwellwerten werden zur manuellen Compliance-Prüfung weitergeleitet:

| Währung | Schwellwert |
|---|---|
| EUR | > 10.000 |
| CHF | > 10.800 |
| GBP | > 8.700 |
| USD | > 11.000 |

---

## Datenbank prüfen

Verbindung zur PostgreSQL-Datenbank:
```bash
docker exec -it postgres psql -U sachbearbeiter -d rechnung
```

Nützliche SQL-Abfragen:

```sql
-- Alle gespeicherten Rechnungen anzeigen
SELECT invoice_id, customer_name, kundennummer, zahlungsziel, total_amount, currency
FROM rechnung.rechnung;

-- Rechnungsposten einer bestimmten Rechnung anzeigen
SELECT * FROM rechnung.rechnungsposition
WHERE invoice_id = 'INV-...';

-- Rechnungen mit allen Positionen zusammen
SELECT r.invoice_id, r.customer_name, r.total_amount,
       p.beschreibung, p.menge, p.einheit, p.brutto
FROM rechnung.rechnung r
JOIN rechnung.rechnungsposition p ON r.invoice_id = p.invoice_id;
```

Mit `\q` die psql-Shell verlassen.

---

## Bekannte Einschränkungen

- Der `archive_worker.py` archiviert Rechnungen als JSON-Dateien in `archive/invoices/` (lokal, nicht im Git).
- Der Prozessstart erfolgt aktuell manuell per CLI (`start_process.py`), nicht automatisch per E-Mail.
