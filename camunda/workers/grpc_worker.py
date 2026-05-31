import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../client"))

import grpc
from loguru import logger
from pyzeebe import ZeebeWorker

import invoice_pb2
import invoice_pb2_grpc
from camunda.config import GRPC_SERVER

def calculate_risk_score(total_amount: float, iban: str = "", currency: str = "EUR", customer_name: str = ""):
    score = 0
    reasons = []

    currency_clean = (currency or "").upper().strip()
    iban_clean = (iban or "").replace(" ", "").upper()
    customer_clean = (customer_name or "").strip()

    allowed_currencies = {"EUR", "CHF", "GBP", "USD"}

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

    if not currency_clean:
        score += 40
        reasons.append("Waehrung fehlt")
    elif currency_clean not in allowed_currencies:
        score += 40
        reasons.append(f"Nicht unterstuetzte Waehrung: {currency_clean}")

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


def register(worker: ZeebeWorker):

    @worker.task(task_type="register-or-update-invoice-grpc")
    async def handle(invoiceId: str, customerName: str, totalAmount: float, issueDate: str, iban: str = "", currency: str = "EUR"):
        if not invoiceId or not customerName:
            raise Exception("Pflichtfelder fehlen: invoiceId oder customerName ist leer.")

        currency_display = currency or "fehlt"
        iban_display = iban or "fehlt"
        customer_display = customerName or "fehlt"

        risk_score, risk_level, risk_reasons = calculate_risk_score(totalAmount, iban, currency, customerName)
        risk_text = "; ".join(risk_reasons)

        validate_required_invoice_data(totalAmount, iban, currency)

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

        return {
            "grpcSaved": True,
            "riskScore": risk_score,
            "riskLevel": risk_level,
            "riskReasons": risk_reasons,
            "requiresAttention": risk_level in {"HIGH", "CRITICAL"},       
         }
