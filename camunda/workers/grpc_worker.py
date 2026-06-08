import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../client"))

import grpc
from loguru import logger
from pyzeebe import ZeebeWorker

import invoice_pb2
import invoice_pb2_grpc
from camunda.config import GRPC_SERVER

# Bewertet eine Rechnung fachlich nach einfachen, nachvollziehbaren Risikoregeln.
# Das Ergebnis stoppt den Prozess nicht automatisch, sondern wird als Prozessvariable an Camunda zurueckgegeben.
def calculate_risk_score(total_amount: float, iban: str = "", currency: str = "EUR", customer_name: str = ""):
    score = 0
    reasons = []

    currency_clean = (currency or "").upper().strip()
    iban_clean = (iban or "").replace(" ", "").upper()
    customer_clean = (customer_name or "").strip()

    allowed_currencies = {"EUR", "CHF", "GBP", "USD"}

    # Betraege werden nach Hoehe bewertet: je hoeher oder unplausibler, desto hoeher das Risiko.
    if total_amount <= 0:
        score += 80
        reasons.append("Betrag ist 0 oder negativ")
    elif total_amount >= 50000:
        score += 80
        reasons.append("Sehr hoher Betrag ab 50.000")
    elif total_amount >= 10000:
        score += 50
        reasons.append("Betrag ueber 10.000")
    elif total_amount >= 5000:
        score += 25
        reasons.append("Betrag ueber 5.000")

    # Waehrungen ausserhalb der erlaubten Liste werden als fachliche Auffaelligkeit markiert.
    if not currency_clean:
        score += 40
        reasons.append("Waehrung fehlt")
    elif currency_clean not in allowed_currencies:
        score += 40
        reasons.append(f"Nicht unterstuetzte Waehrung: {currency_clean}")

    # Die IBAN wird nur auf Plausibilitaet geprueft, nicht mit einer echten Bankvalidierung.
    if not iban_clean:
        score += 50
        reasons.append("IBAN fehlt")
    elif len(iban_clean) < 15:
        score += 40
        reasons.append("IBAN zu kurz")
    elif not iban_clean[:2].isalpha() or not iban_clean[2:4].isdigit():
        score += 40
        reasons.append("IBAN Format ungueltig")
    elif not iban_clean.startswith("DE"):
        score += 20
        reasons.append("Auslands-IBAN")

    # Platzhalter-Kundennamen helfen dabei, Test- oder Dummy-Daten in der Demo sichtbar zu machen.
    if not customer_clean:
        score += 30
        reasons.append("Kundenname fehlt")
    elif any(word in customer_clean.lower() for word in ["test", "dummy", "unknown", "unbekannt"]):
        score += 20
        reasons.append("Auffaelliger Kundenname")

    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 30:
        level = "MEDIUM"
    else:
        level = "LOW"

    if not reasons:
        reasons.append("Keine Auffaelligkeiten")

    return score, level, reasons


# Prueft Pflichtdaten, ohne die der Prozess nicht sinnvoll weiterlaufen darf.
# Bei Fehlern wird eine Exception geworfen; Camunda erzeugt daraus einen Incident am Service Task.
def validate_required_invoice_data(total_amount: float, iban: str = "", currency: str = "EUR"):
    currency_clean = (currency or "").upper().strip()
    iban_clean = (iban or "").replace(" ", "").upper()
    allowed_currencies = {"EUR", "CHF", "GBP", "USD"}

    if total_amount <= 0:
        raise Exception("Validierungsfehler: Betrag muss groesser als 0 sein.")

    if not currency_clean:
        raise Exception("Validierungsfehler: Waehrung fehlt. Erlaubt sind EUR, CHF, GBP und USD.")

    if currency_clean not in allowed_currencies:
        raise Exception(f"Validierungsfehler: Waehrung '{currency_clean}' wird nicht unterstuetzt.")

    if not iban_clean:
        raise Exception("Validierungsfehler: IBAN fehlt.")

    if len(iban_clean) < 15:
        raise Exception("Validierungsfehler: IBAN ist zu kurz.")

    if not iban_clean[:2].isalpha() or not iban_clean[2:4].isdigit():
        raise Exception("Validierungsfehler: IBAN-Format ist ungueltig.")


def _build_positionen(raw):
    positionen = []
    for r in raw:
        beschreibung = r.get("beschreibung", "")
        menge = float(r.get("menge", 0) or 0)
        einzelpreis = float(r.get("einzelpreis", 0) or 0)
        steuer_prozent = float(r.get("steuerProzent", 19) or 19)
        einheit = r.get("einheit", "Stk.") or "Stk."

        if not beschreibung or menge <= 0 or einzelpreis <= 0:
            continue

        netto = round(menge * einzelpreis, 2)
        steuer = round(netto * (steuer_prozent / 100), 2)
        brutto = round(netto + steuer, 2)

        positionen.append(invoice_pb2.Position(
            beschreibung=beschreibung,
            menge=menge,
            einheit=einheit,
            einzelpreis=einzelpreis,
            steuer_prozent=steuer_prozent,
            netto=netto,
            steuer=steuer,
            brutto=brutto,
        ))
    return positionen


def register(worker: ZeebeWorker):

    @worker.task(task_type="register-or-update-invoice-grpc")
    async def handle(invoiceId: str, customerName: str, totalAmount: float, issueDate: str,
                     iban: str = "", currency: str = "EUR",
                     positionen: list = [], kundennummer: str = "", zahlungsziel: str = ""):
        if not invoiceId or not customerName:
            raise Exception("Pflichtfelder fehlen: invoiceId oder customerName ist leer.")

        currency_display = currency or "fehlt"
        iban_display = iban or "fehlt"
        customer_display = customerName or "fehlt"

        grpc_positionen = _build_positionen(positionen)

        # Gesamtbetrag aus Positionen berechnen falls vorhanden
        if grpc_positionen:
            totalAmount = round(sum(p.brutto for p in grpc_positionen), 2)

        # Risiko erst nach der Betragsberechnung bewerten, damit ein initialer Formularwert 0 nicht fälschlich auffällig wird.
        risk_score, risk_level, risk_reasons = calculate_risk_score(totalAmount, iban, currency, customerName)
        risk_text = "; ".join(risk_reasons)

        # Harte Validierung nach Berechnung, damit der korrekte Betrag geprüft wird.
        validate_required_invoice_data(totalAmount, iban, currency)

        try:
            # Uebergibt die Rechnungsmetadaten an den lokalen gRPC-Server.
            with grpc.insecure_channel(GRPC_SERVER) as channel:
                stub = invoice_pb2_grpc.InvoiceServiceStub(channel)
                request = invoice_pb2.InvoiceRequest(
                    invoice_id=invoiceId,
                    customer_name=customerName,
                    total_amount=totalAmount,
                    issue_date=issueDate,
                    iban=iban,
                    currency=currency,
                    positionen=grpc_positionen,
                    kundennummer=kundennummer,
                    zahlungsziel=zahlungsziel,
                )
                response = stub.SaveMetadata(request)
        except grpc.RpcError as e:
            raise Exception(f"gRPC Server nicht erreichbar: {e.details()}")

        if not response.success:
            raise Exception(f"gRPC Fehler: {response.message}")

        if risk_level == "LOW":
            logger.success(
                "[OK] Rechnung {} gespeichert | Risiko: LOW | Kein Fehler gefunden",
                invoiceId,
            )
        else:
            logger.warning(
                "[PRUEFUNG] Rechnung {} gespeichert | Risiko: {} ({}) | Fehler: {} | Daten: Betrag={:.2f}, Waehrung={}, IBAN={}, Kunde={}",
                invoiceId,
                risk_level,
                risk_score,
                risk_text,
                totalAmount,
                currency_display,
                iban_display,
                customer_display,
            )

        # Diese Werte erscheinen in Operate als Camunda-Prozessvariablen.
        return {
            "grpcSaved": True,
            "totalAmount": totalAmount,
            "riskScore": risk_score,
            "riskLevel": risk_level,
            "riskReasons": risk_reasons,
            "requiresAttention": risk_level in {"HIGH", "CRITICAL"},
        }
