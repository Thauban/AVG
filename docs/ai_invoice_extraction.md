# AI Agent für Rechnungsextraktion

## Anforderungen

- AI Agent/Workflow zur Extraktion von Rechnungsdaten aus PDF-Dateien.
- Extraktion von Metadaten und Rechnungspositionen.
- Menschliche Kontrolle des Ergebnisses und Korrekturmöglichkeit.
- Anpassung des Workflows, damit die extrahierten Daten im Prozess genutzt werden.
- Praesentation der Gesamtanwendung und Dokumentation.
- Pro Person eine 2-seitige Zusammenfassung des Gelernten.

## Umsetzung im Projekt

- n8n wird als AI-Workflow-Schicht in Docker betrieben.
- n8n extrahiert die PDF-Daten mit einem LLM-Node, z.B. Google Gemini Analyze Document.
- Das Ergebnis wird als JSON gemäß `docs/n8n_invoice_extraction_schema.json` ausgegeben.
- `camunda/start_process.py --json <datei>` normalisiert das JSON und startet den Camunda-Prozess mit vorbefüllten Variablen.
- `camunda/http_start_server.py` bietet zusätzlich eine lokale HTTP-Schnittstelle, damit n8n den Camunda-Prozess automatisch starten kann.
- Die bestehende Camunda User Task `Rechnungsdaten manuell erfassen` bleibt die menschliche Kontrollstelle.
- Der Zeebe Worker `register-or-update-invoice-grpc` speichert Metadaten, Kundennummer, Zahlungsziel und Positionen über gRPC in PostgreSQL.
- Bei Korrekturen mit gleicher `invoiceId` wird die Rechnung aktualisiert und die Positionen werden ersetzt.

## Ablauf

1. PostgreSQL, RabbitMQ, gRPC-Server und Camunda-Worker starten.
2. n8n starten:

```bash
cd compose/n8n
docker compose up -d
```

3. In n8n eine PDF analysieren oder das Beispielpayload verwenden:

```bash
python camunda/start_process.py --json n8n/extracted_invoice.example.json --pdf-name beispielrechnung.pdf
```

4. Für den integrierten Ablauf alternativ die n8n-Camunda-Bridge starten:

```bash
.\.venv\Scripts\python.exe camunda\http_start_server.py
```

Dann in n8n `n8n/invoice_ai_to_camunda_workflow.json` importieren und ausführen.

5. In Camunda Tasklist die vorbefüllten Rechnungsdaten kontrollieren.
6. Prozess freigeben und in PostgreSQL prüfen, ob Rechnung und Position gespeichert wurden.

```sql
SELECT invoice_id, customer_name, kundennummer, zahlungsziel, total_amount, currency
FROM rechnung.rechnung;

SELECT invoice_id, pos_nummer, beschreibung, menge, brutto
FROM rechnung.rechnungsposition
WHERE invoice_id = 'INV-AI-2026-001';
```
