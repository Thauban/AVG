# n8n AI-Workflow

Der Workflow extrahiert Rechnungsdaten aus einer PDF und stellt die Daten danach einem Menschen zur Kontrolle bereit. In unserem Projekt übernimmt n8n die Extraktion, Camunda bleibt die Prozess-Orchestrierung.

## Start

```bash
cd compose/n8n
docker compose up -d
```

n8n ist danach unter `http://localhost:5678/` erreichbar.

## Empfohlener Workflow in n8n

1. `Manual Trigger` oder `Webhook` für den PDF-Upload anlegen.
2. PDF-Datei an einen LLM-Node übergeben, z.B. `Google Gemini - Analyze Document`.
3. Das Modell auf das JSON-Format aus `docs/n8n_invoice_extraction_schema.json` festlegen. Den passenden Prompt findest du in `docs/n8n_gemini_invoice_prompt.md`.
4. Ergebnis in n8n prüfen und bei Bedarf korrigieren.
5. JSON lokal speichern oder per HTTP Request an Camunda übergeben:

```bash
.\.venv\Scripts\python.exe camunda\http_start_server.py
```

Der n8n HTTP Request Node sendet danach an:

```text
http://host.docker.internal:8088/start-invoice-process
```

## Ablauf

Zum Testen reicht zuerst das Beispiel oder der Import-Workflow:

```bash
python camunda/start_process.py --json n8n/extracted_invoice.example.json --pdf-name beispielrechnung.pdf
```

Danach erscheinen die extrahierten Felder als Prozessvariablen in Camunda. Die bestehende User Task zur Rechnungsdatenerfassung dient als menschliche Kontrollstelle. Nach Freigabe speichert der gRPC-Worker die Metadaten und Rechnungspositionen in PostgreSQL.

Für den integrierten Ablauf:

1. `camunda/http_start_server.py` starten.
2. In n8n `n8n/invoice_ai_to_camunda_workflow.json` importieren.
3. Workflow ausführen.
4. Der HTTP Request Node startet den Camunda-Prozess automatisch.
