import sys
import os
# Wird verwendet, um server/main.py als eigenen lokalen Python-Prozess zu starten.
import subprocess
# Verhindert, dass mehrere Camunda-Jobs gleichzeitig mehrere gRPC-Server starten.
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../client"))

import grpc
from loguru import logger
from pyzeebe import ZeebeWorker

import invoice_pb2
import invoice_pb2_grpc
from camunda.config import GRPC_SERVER


# Ein einzelner Speicherversuch darf höchstens acht Sekunden blockieren.
GRPC_CALL_TIMEOUT_SECONDS = 8
# Nach dem automatischen Start warten wir höchstens 20 Sekunden auf den Server.
GRPC_START_TIMEOUT_SECONDS = 20
# Der Lock schützt den Prüf- und Startbereich vor parallelen Worker-Aufrufen.
_grpc_start_lock = threading.Lock()


def _grpc_channel_ready(timeout_seconds):
    """Prüft innerhalb der Wartezeit, ob der konfigurierte gRPC-Endpunkt bereit ist."""
    # Der Channel verwendet genau den Endpunkt aus GRPC_SERVER in der .env-Datei.
    channel = grpc.insecure_channel(GRPC_SERVER)
    try:
        # channel_ready_future wird erst erfolgreich, wenn eine Verbindung möglich ist.
        grpc.channel_ready_future(channel).result(timeout=timeout_seconds)
        return True
    except grpc.FutureTimeoutError:
        # Ein Timeout bedeutet hier nur "noch nicht erreichbar" und nicht Programmabbruch.
        return False
    finally:
        # Der reine Prüf-Channel wird unabhängig vom Ergebnis wieder geschlossen.
        channel.close()


def _is_local_grpc_server():
    """Erlaubt den Autostart ausschließlich für den lokalen Projektserver auf Port 50051."""
    # rpartition trennt beispielsweise "localhost:50051" in Host, Doppelpunkt und Port.
    host, separator, port = GRPC_SERVER.rpartition(":")
    # Entfernte Server dürfen niemals als lokaler Python-Prozess gestartet werden.
    return separator and host.lower() in {"localhost", "127.0.0.1"} and port == "50051"


def _start_local_grpc_server():
    """Startet den lokalen gRPC-Server einmalig und wartet auf Bereitschaft."""
    # Die Schutzprüfung verhindert einen Autostart bei einer externen gRPC-Konfiguration.
    if not _is_local_grpc_server():
        raise RuntimeError(
            f"Automatischer Start ist nur fuer localhost:50051 moeglich; konfiguriert ist {GRPC_SERVER}."
        )

    # Innerhalb dieses Blocks darf immer nur ein Job gleichzeitig prüfen und starten.
    with _grpc_start_lock:
        # Vielleicht hat ein paralleler Job den Server inzwischen gestartet.
        if _grpc_channel_ready(timeout_seconds=1):
            return

        # Der Projektroot wird relativ zu dieser Worker-Datei bestimmt.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        # Dies ist das bereits vorhandene Startskript des gRPC-Servers.
        server_script = os.path.join(project_root, "server", "main.py")

        logger.warning("[gRPC Worker] Server ist nicht erreichbar. Starte ihn automatisch ...")
        # sys.executable verwendet dieselbe Python-Umgebung wie der Camunda-Worker.
        # Projektroot und Umgebungsvariablen werden an den neuen Prozess weitergegeben.
        process = subprocess.Popen(
            [sys.executable, server_script],
            cwd=project_root,
            env=os.environ.copy(),
        )

        # Der gestartete Server benötigt zunächst seine PostgreSQL-Verbindung und den Port.
        if _grpc_channel_ready(timeout_seconds=GRPC_START_TIMEOUT_SECONDS):
            logger.success("[gRPC Worker] gRPC-Server wurde automatisch gestartet.")
            return

        # poll liefert None, wenn der gestartete Prozess nach dem Timeout noch läuft.
        exit_code = process.poll()
        if exit_code is None:
            # Ein laufender, aber nicht erreichbarer Kindprozess wird sauber beendet.
            process.terminate()
            try:
                # Nach terminate erhält der Prozess kurz Zeit zum kontrollierten Beenden.
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # Nur wenn das nicht genügt, wird der von uns gestartete Prozess beendet.
                process.kill()
            raise RuntimeError(
                f"gRPC-Server wurde gestartet, war aber nach {GRPC_START_TIMEOUT_SECONDS} Sekunden nicht bereit."
            )
        # Ein bereits beendeter Prozess liefert seinen Exit-Code zur Fehlerdiagnose.
        raise RuntimeError(f"Automatischer Start des gRPC-Servers fehlgeschlagen (Exit-Code {exit_code}).")


def _save_metadata(request):
    """Sendet eine vorbereitete Rechnung mit einem festen Timeout an den gRPC-Server."""
    # Für jeden Speicherversuch wird ein eigener, anschließend geschlossener Channel verwendet.
    with grpc.insecure_channel(GRPC_SERVER) as channel:
        # Der generierte Stub stellt die SaveMetadata-Methode aus invoice.proto bereit.
        stub = invoice_pb2_grpc.InvoiceServiceStub(channel)
        # Das Timeout verhindert, dass ein Camunda-Job unbegrenzt auf gRPC wartet.
        return stub.SaveMetadata(request, timeout=GRPC_CALL_TIMEOUT_SECONDS)


def _to_float(value, default=0.0):
    # n8n/AI liefert Zahlen je nach Modell manchmal als Text.
    # Der Worker rechnet Positionen und Gesamtbeträge deshalb defensiv um.
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_positions(line_items):
    # Aus den extrahierten lineItems werden gRPC-Positionen gebaut,
    # damit neben Metadaten auch Rechnungspositionen gespeichert werden.
    positions = []
    for item in line_items or []:
        if not isinstance(item, dict):
            continue

        beschreibung = item.get("beschreibung") or item.get("description") or ""
        menge = _to_float(item.get("menge") or item.get("quantity"), 0.0)
        einzelpreis = _to_float(item.get("einzelpreis") or item.get("unitPrice") or item.get("price"), 0.0)
        steuer_prozent = _to_float(
            item.get("steuer_prozent") or item.get("steuerProzent") or item.get("taxRate") or item.get("vatRate"),
            19.0,
        )
        einheit = item.get("einheit") or item.get("unit") or "Stk."
        netto = _to_float(item.get("netto") or item.get("netAmount"))
        steuer = _to_float(item.get("steuer") or item.get("steuer_betrag") or item.get("taxAmount"))
        brutto = _to_float(item.get("brutto") or item.get("grossAmount"))

        if not beschreibung or menge <= 0:
            # Unvollständige AI-Positionen werden ignoriert. So erzeugt ein
            # einzelner schlechter Positionsvorschlag keinen Prozessabbruch.
            continue

        # Falls die AI nur Menge und Einzelpreis liefert, berechnen wir Netto,
        # Steuer und Brutto nachvollziehbar nach.
        if netto <= 0 and einzelpreis > 0:
            netto = round(menge * einzelpreis, 2)
        if steuer <= 0 and netto > 0:
            steuer = round(netto * (steuer_prozent / 100), 2)
        if brutto <= 0 and netto > 0:
            brutto = round(netto + steuer, 2)

        positions.append(
            invoice_pb2.Position(
                beschreibung=beschreibung,
                menge=menge,
                einheit=einheit,
                einzelpreis=einzelpreis,
                steuer_prozent=steuer_prozent,
                netto=netto,
                steuer=steuer,
                brutto=brutto,
            )
        )
    return positions


# Bewertet die Rechnung nach einfachen Risikoregeln.
# Die Regeln sind bewusst nachvollziehbar gehalten, damit das Ergebnis
# im Prozess leicht erklärt werden kann.
def calculate_risk_score(total_amount: float, iban: str = "", currency: str = "EUR", customer_name: str = ""):
    score = 0
    reasons = []

    currency_clean = (currency or "").upper().strip()
    iban_clean = (iban or "").replace(" ", "").upper()
    customer_clean = (customer_name or "").strip()

    allowed_currencies = {"EUR", "CHF", "GBP", "USD"}

    # Betrag prüfen: sehr hohe oder ungültige Beträge erhöhen das Risiko.
    if total_amount <= 0:
        score += 80
        reasons.append("Betrag ist 0 oder negativ")
    elif total_amount >= 50000:
        score += 80
        reasons.append("Sehr hoher Betrag ab 50.000")
    elif total_amount >= 10000:
        score += 50
        reasons.append("Betrag über 10.000")
    elif total_amount >= 5000:
        score += 25
        reasons.append("Betrag über 5.000")

    # Währung prüfen: nur definierte Währungen werden akzeptiert.
    if not currency_clean:
        score += 40
        reasons.append("Währung fehlt")
    elif currency_clean not in allowed_currencies:
        score += 40
        reasons.append(f"Nicht unterstützte Währung: {currency_clean}")

    # IBAN prüfen: hier findet eine Plausibilitätsprüfung statt,
    # keine vollständige Bankvalidierung.
    if not iban_clean:
        score += 50
        reasons.append("IBAN fehlt")
    elif len(iban_clean) < 15:
        score += 40
        reasons.append("IBAN zu kurz")
    elif not iban_clean[:2].isalpha() or not iban_clean[2:4].isdigit():
        score += 40
        reasons.append("IBAN Format ungültig")
    elif not iban_clean.startswith("DE"):
        score += 20
        reasons.append("Auslands-IBAN")

    # Kundennamen prüfen: Platzhalter wie Test oder Dummy gelten als auffällig.
    if not customer_clean:
        score += 30
        reasons.append("Kundenname fehlt")
    elif any(word in customer_clean.lower() for word in ["test", "dummy", "unknown", "unbekannt"]):
        score += 20
        reasons.append("Auffälliger Kundenname")

    # Aus dem berechneten Score wird eine verständliche Risikostufe gebildet.
    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 30:
        level = "MEDIUM"
    else:
        level = "LOW"
    # Falls keine Regel angeschlagen hat, gilt die Rechnung als unauffällig.
    if not reasons:
        reasons.append("Keine Auffälligkeiten")

    # Rückgabe an Camunda:
    # Diese Werte sind später in Operate als Prozessvariablen sichtbar.
    return score, level, reasons


def validate_required_invoice_data(total_amount: float, iban: str = "", currency: str = "EUR"):
    currency_clean = (currency or "").upper().strip()
    iban_clean = (iban or "").replace(" ", "").upper()
    allowed_currencies = {"EUR", "CHF", "GBP", "USD"}

    if total_amount <= 0:
        raise Exception("Validierungsfehler: Betrag muss größer als 0 sein.")

    if not currency_clean:
        raise Exception("Validierungsfehler: Währung fehlt. Erlaubt sind EUR, CHF, GBP und USD.")

    if currency_clean not in allowed_currencies:
        raise Exception(f"Validierungsfehler: Währung '{currency_clean}' wird nicht unterstützt.")

    if not iban_clean:
        raise Exception("Validierungsfehler: IBAN fehlt.")

    if len(iban_clean) < 15:
        raise Exception("Validierungsfehler: IBAN ist zu kurz.")

    if not iban_clean[:2].isalpha() or not iban_clean[2:4].isdigit():
        raise Exception("Validierungsfehler: IBAN-Format ist ungültig.")


def register(worker: ZeebeWorker):

    @worker.task(task_type="register-or-update-invoice-grpc")
    async def handle(
        invoiceId: str,
        customerName: str,
        totalAmount: float,
        issueDate: str,
        iban: str = "",
        currency: str = "EUR",
        kundennummer: str = "",
        zahlungsziel: str = "",
        lineItems: list | None = None,
        positionen: list | None = None,
        aiExtracted: bool = False,
        extractionConfidence: float = 0.0,
    ):
        if not invoiceId or not customerName:
            raise Exception("Pflichtfelder fehlen: invoiceId oder customerName ist leer.")

        grpc_positionen = _build_positions(lineItems or positionen)

        if grpc_positionen:
            # Wenn Positionen vorhanden sind, ist deren Summe die zuverlässigere
            # Quelle für den Gesamtbetrag als ein eventuell leerer Formularwert.
            totalAmount = round(sum(p.brutto for p in grpc_positionen), 2)

        # Risiko und Pflichtfeldvalidierung laufen nach der Positionsberechnung,
        # damit AI-Daten und manuelle Korrekturen gleich behandelt werden.
        risk_score, risk_level, risk_reasons = calculate_risk_score(totalAmount, iban, currency, customerName)
        validate_required_invoice_data(totalAmount, iban, currency)

        logger.info(f"[gRPC Worker] Speichere Rechnung: {invoiceId} | IBAN: {iban} | Währung: {currency}")
        if aiExtracted:
            # In den Logs wird sichtbar, dass die Daten aus der n8n-Extraktion kamen.
            logger.info("[gRPC Worker] AI-Extraktion erkannt | Confidence: {}", extractionConfidence)

        # Alle validierten Camunda-Prozessvariablen werden in die gRPC-Nachricht übertragen.
        request = invoice_pb2.InvoiceRequest(
            invoice_id=invoiceId,
            customer_name=customerName,
            total_amount=totalAmount,
            issue_date=issueDate,
            iban=iban,
            currency=currency,
            kundennummer=kundennummer,
            zahlungsziel=zahlungsziel,
        )
        # Übergabe der von n8n/Gemini extrahierten Rechnungspositionen
        # an den bestehenden gRPC-Server.
        request.positionen.extend(grpc_positionen)

        # Im Normalfall wird die Rechnung sofort an einen bereits laufenden Server gesendet.
        try:
            response = _save_metadata(request)
        except grpc.RpcError as first_error:
            # Nur UNAVAILABLE bedeutet, dass ein lokaler Serverstart sinnvoll ist.
            # Fachliche und andere technische gRPC-Fehler werden direkt an Camunda gemeldet.
            if first_error.code() != grpc.StatusCode.UNAVAILABLE:
                raise Exception(f"gRPC Fehler: {first_error.details()}") from first_error

            # Bei UNAVAILABLE startet der Worker den Server und wiederholt denselben Request.
            try:
                _start_local_grpc_server()
                response = _save_metadata(request)
            except (grpc.RpcError, RuntimeError) as retry_error:
                # gRPC- und lokale Startfehler werden in eine verständliche Meldung vereinheitlicht.
                details = retry_error.details() if isinstance(retry_error, grpc.RpcError) else str(retry_error)
                # Die Exception lässt den Camunda-Job fehlschlagen, falls auch der Retry scheitert.
                raise Exception(f"gRPC Server nicht erreichbar: {details}") from retry_error

        if not response.success:
            raise Exception(f"gRPC Fehler: {response.message}")

        if risk_level == "LOW":
            logger.success("[OK] Rechnung {} gespeichert | Risiko: LOW | Kein Fehler gefunden", invoiceId)
        else:
            logger.warning(
                "[PRÜFUNG] Rechnung {} gespeichert | Risiko: {} ({}) | Fehler: {}",
                invoiceId,
                risk_level,
                risk_score,
                "; ".join(risk_reasons),
            )

        # Rückgabe an Camunda:
        # Diese Werte sind später in Operate als Prozessvariablen sichtbar.
        return {
            "grpcSaved": True,
            "totalAmount": totalAmount,
            "riskScore": risk_score,
            "riskLevel": risk_level,
            "riskReasons": risk_reasons,
            "requiresAttention": risk_level in {"HIGH", "CRITICAL"},
        }
