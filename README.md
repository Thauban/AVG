# AVG - Rechnungs- und Zahlungssystem

Dieses System demonstriert die Zusammenarbeit verschiedener Services mittels **gRPC** und **RabbitMQ** Message Broker gemäß den Anforderungen.

## Voraussetzungen

1. Python installieren.
2. Abhängigkeiten installieren:
   ```cmd
   pip install -r requirements.txt
   ```
3. **RabbitMQ** Server muss laufen (Knotenpunkt für das Zahlungssystem). Starten Sie dies idealerweise über Docker:
   ```cmd
   docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
   ```

## Starten der Komponenten

Bitte in **drei separaten Terminals** starten (in dieser Reihenfolge):

### 1. gRPC Rechnungs-Server
Speichert die Metadaten zu eingehenden Rechnungen.
```cmd
cd server
python server.py
```

### 2. Zahlungssystem (RabbitMQ Worker)
Lauscht auf eingehende Zahlungsaufträge in der Warteschlange.
```cmd
cd payment_worker
python payment_system.py
```

### 3. Client
Simuliert das Senden einer Rechnung und anschließendes Veranlassen der Zahlung.
```cmd
cd client
python client.py
```
