# Camunda – Invoice ERP Automation (Gruppe 2)

Automatisierter Purchase-to-Pay Prozess auf Basis von **Camunda 8**, **Python**, **gRPC** und **RabbitMQ**.  
Rechnungen werden digital erfasst, fachlich geprüft, compliance-geprüft und abschließend per Zahlungsauftrag verarbeitet.

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
3. DMN-Tabelle prüft ob Compliance-Check nötig ist (abhängig von Betrag und Währung)
4. Bei Bedarf: manueller Compliance-Check
5. ERP-Buchung und finale Freigabe
6. Zahlungsauftrag wird über RabbitMQ gesendet
7. Rechnung wird archiviert

---

## Dateien

```
camunda/
├── main.py                        # Startet alle Camunda Worker
├── start_process.py               # Startet eine neue Prozessinstanz
├── send_correction.py             # Sendet Korrektur-Nachricht
├── config.py                      # Konfiguration (liest .env)
├── compliance_check.dmn           # DMN-Entscheidungstabelle
├── G2_Invoice-ERP-Automation.bpmn # BPMN-Prozessmodell
└── workers/
    ├── grpc_worker.py             # Worker: Rechnung speichern (gRPC)
    ├── payment_worker.py          # Worker: Zahlung auslösen (RabbitMQ)
    └── archive_worker.py          # Worker: Rechnung archivieren
```

---

## Voraussetzungen

- Python 3.10+
- Docker (für RabbitMQ)
- Virtuelle Umgebung aktiviert (`source .venv/bin/activate`)
- `.env` Datei im Projektroot mit allen Zugangsdaten (siehe Haupt-README)

---

## Starten

> Alle Befehle vom **Projektroot** (`AVG/`) ausführen, nicht aus dem `camunda/` Ordner.

### Schritt 1 – Camunda Worker starten

Verbindet sich mit Camunda SaaS und wartet auf eingehende Jobs:

```bash
python camunda/main.py
```

### Schritt 2 – Prozess starten

Startet eine neue Prozessinstanz in Camunda mit automatisch generierter Invoice-ID:

```bash
python camunda/start_process.py
```

Die Invoice-ID und der Operate-Link erscheinen in den Logs.

### Schritt 3 – Prozess in der Tasklist bearbeiten

Die Aufgaben erscheinen automatisch in der **Camunda Tasklist**.  
Folgende Formulare sind im Prozess enthalten:

| Formular | Beschreibung |
|---|---|
| Erfassung der Rechnungsdaten | Rechnungsdaten inkl. Währung eingeben |
| Rechnung vorprüfen | Erste Prüfung durch Sachbearbeiter |
| Rechnung fachlich prüfen | Entscheidung: freigeben / ablehnen / Korrektur |
| Compliance-Check manuell | Manuelle Compliance-Prüfung (nur bei Bedarf) |
| ERP-Buchung manuell | Buchung im ERP-System bestätigen |
| Rechnung final freigeben | Abschließende Freigabe |

### Schritt 4 – Korrektur senden (falls nötig)

Wenn ein Sachbearbeiter „Korrektur anfordern" auswählt, wartet der Prozess auf eine Korrektur-Nachricht.  
Die Invoice-ID steht in den Logs von `start_process.py`.

```bash
python camunda/send_correction.py <invoiceId>
```

---

## DMN – Compliance-Schwellwerte

Die Compliance-Prüfung berücksichtigt Betrag **und** Währung.  
Rechnungen über den folgenden Schwellwerten werden automatisch zur manuellen Compliance-Prüfung weitergeleitet:

| Währung | Schwellwert |
|---|---|
| EUR | > 10.000 |
| CHF | > 10.800 |
| GBP | > 8.700 |
| USD | > 11.000 |

---

## Umgebungsvariablen (.env)

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
