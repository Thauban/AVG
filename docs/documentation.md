# Projekt Doku - AVG Zahlungssystem

Moin, hier ist die Übersicht, wie unser Code zusammenhängt.
Der Code ist leicht verständlich, aber mit dieser Dokumentation versteht es .

## Was haben wir?

### 1. Der gRPC Server (`/server`)

Das ist das Herzstück. Hier werden die Rechnungsdaten (Metadaten) gespeichert.

- Benutzt gRPC (schneller als REST).
- Hat ne einfache In-Memory "Datenbank" (reicht für's Erste) -> später Erweiterbar mit richtiger Datenbank im Repository.
- Läuft standardmäßig auf Port `50051`.

Zudem sind Methoden hinzugefügt, um bereits gespeicherte Daten auch abzurufen.
Das ganze ist nach der Multiple-Layer-Architecture aufgebaut. (router-logic-repository)

### 2. Der RabbitMQ Container (`/compose`)

Hier senden wir alle Zahlungsaufträge hin.

- Läuft in Docker (mit dem Management UI auf `15672`).
- Zugangsdaten kommen aus der `.env`.
- Nutzung der `payment_queue`.

### 3. Der Payment Worker (`/service`)

Das ist das Modul, welches die Transaktionen, welche in Auftrag gegeben wurden, auch ausführt.

- lauscht an RabbitMQ und wartet auf neue Nachrichten.
- Wenn was kommt, simuliert er die Zahlung (mit `time.sleep`, als ob er echt was tun würde).
- Holt sich seine Config (User/Passwort für MQ) direkt aus der `.env`.

### 4. Der Client (`/client`)

Der Client simuliert einen kompletten Ablauf: Rechnungen werden per gRPC
gespeichert und abgefragt, eine Rechnung wird gelöscht, danach wird die
Rechnungsliste erneut angezeigt. Für die verbleibenden Rechnungen werden
Zahlungsaufträge an RabbitMQ gesendet.

### 5. Docs

Das Sequenzdiagramm wurde mit unterstützung von Google Anti-gravity erstellt.
Das Diagramm hilft dabei, den Systemablauf zwischen Client, gRPC-Server, RabbitMQ und dem Payment Worker besser zu verstehen.

---

## Wie kriegt man das zum Laufen? [alles in separaten Tabs]

1. **Docker starten:**
   Pfadwechsel in `/compose` und führe `docker compose up -d` aus. Dann läuft RabbitMQ.
2. **Server starten:**
   `python server/server.py` (vorher `pip install -r requirements.txt` machen!).
   (kann auch über Dockerfile gemacht werden)
3. **Worker starten:**
   `python service/payment_system.py`. Der sollte ausgeben, dass er auf Nachrichten wartet.
4. **Testen:**
   unter `/client` die client.py ausführen.

## Wichtig: .env Datei

Ohne die `.env` im Hauptverzeichnis geht gar nichts. Da müssen `RABBITMQ_USER` und `RABBITMQ_PASS` drinstehen, sonst kann der Worker sich nicht einloggen.

**Dateien, die automatisch generiert werden:**
Die `*_pb2.py` BITTE NICHT ANFASSEN!
Sie werden aus der `.proto` Datei in `/shared` generiert.
Wenn die API geändert wird, muss den Befehl für den gRPC-Compiler nochmal ausgeführt werden.

Viel Erfolg beim Ausprobieren!

### Anmerkung zu KI

Teile des Codes wurden unter Hilfe von KI-Modellen, wie Gemini, Codex oder Claude, erstellt.
Diese wurden für unseren Code angepasst und es wurde nur Code verwendet, von dem wir wissen, was und wie er funktioniert.
