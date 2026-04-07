# Systemarchitektur: Rechnungs- und Zahlungssystem

Dieses Dokument beschreibt die Architektur und Funktionsweise des Systems, das für die Verarbeitung von Rechnungen und Zahlungsaufträgen entwickelt wurde.

## Komponenten

Das System besteht gemäß den Anforderungen aus folgenden separat lauffähigen Komponenten:

### 1. gRPC Service (Rechnungs-Storage)
**Verzeichnis:** `server/`
- Nimmt über gRPC Strukturdaten (Metadaten) von Rechnungen entgegen.
- Definiert wird die Schnittstelle in `shared/invoice.proto`, die Methoden wie `SaveMetadata` bereitstellt.
- Dem Code-Prinzip "schlicht und einfach" folgend, werden die Rechnungsdaten hier temporär in einer Liste im Arbeitsspeicher (`INVOICE_DB`) abgelegt.
- Nach erfolgreichem Speichern wird dem Client der Erfolg bestätigt.

### 2. Zahlungssystem (Message Broker Consumer)
**Verzeichnis:** `payment_worker/`
- Ein eigenständiger Worker-Prozess, der unabhängig vom gRPC-Server läuft.
- Er verbindet sich mit einem **RabbitMQ** Message Broker.
- Er lauscht auf der Warteschlange (Queue) `payment_queue`.
- Eingehende Zahlungsaufträge werden asynchron entgegengenommen, zur Simulation verarbeitet (`time.sleep(2)`) und danach im Broker als erledigt markiert (Acknowledge).

### 3. Client (Orchestrator)
**Verzeichnis:** `client/`
- Dient als Ausgangspunkt für die Datenverarbeitung.
- Der Client erzeugt fiktive Rechnungsdaten und speichert diese **synchron** beim gRPC-Server ab.
- Unmittelbar danach erzeugt der Client einen asynchronen Zahlungsauftrag (JSON) und schickt diesen über **RabbitMQ** in die `payment_queue`. An diesem Punkt ist die Arbeit des Clients beendet – das Zahlungssystem bearbeitet den Auftrag im Hintergrund weiter.

## Kommunikation

In diesem Projekt werden bewusst zwei unterschiedliche Kommunikations-Paradigmen kombiniert:
- **Synchron (gRPC):** Speicherung der Rechnung. Der Client wartet, bis der Server die Speicherung bestätigt.
- **Asynchron (RabbitMQ):** Veranlassung der Zahlung. Der Client feuert die Nachricht lediglich ab ("Fire and Forget"). Der Zahlungsworker kann den Job auch sehr viel später abarbeiten, falls das Backend ausgelastet sein sollte. Dies entspricht gängigen industriellen Best-Practices.
