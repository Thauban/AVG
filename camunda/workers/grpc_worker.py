import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../client"))

import grpc
from loguru import logger
from pyzeebe import ZeebeWorker

import invoice_pb2
import invoice_pb2_grpc
from camunda.config import GRPC_SERVER


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

        try:
            with grpc.insecure_channel(GRPC_SERVER) as channel:
                stub = invoice_pb2_grpc.InvoiceServiceStub(channel)
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
                response = stub.SaveMetadata(request)
        except grpc.RpcError as e:
            raise Exception(f"gRPC Server nicht erreichbar: {e.details()}")

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
