import json
from datetime import date
from pathlib import Path
from typing import Any


def _first(data: dict[str, Any], *keys: str, default: Any = "") -> Any:
    # AI-Outputs sind nicht immer gleich benannt: Gemini, n8n oder Beispiel-JSON
    # können z.B. "invoiceId", "invoice_id" oder "rechnungsnummer" liefern.
    # Diese Hilfsfunktion nimmt den ersten vorhandenen Wert aus einer Alias-Liste.
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def _to_float(value: Any, default: float = 0.0) -> float:
    # Beträge aus Rechnungen können als Zahl oder als Text kommen.
    # Beispiele: 1428, "1428.00", "1.428,00". Für Camunda/gRPC brauchen wir float.
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return float(value)

    # Deutsche und englische Zahlformate werden auf Python-freundliche
    # Schreibweise normalisiert.
    normalized = str(value).strip().replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    else:
        normalized = normalized.replace(",", ".")

    try:
        return float(normalized)
    except ValueError:
        return default


def _normalize_line_item(item: dict[str, Any]) -> dict[str, Any]:
    # Rechnungspositionen werden zusammen mit den Metadaten aus der PDF übernommen.
    # Auch hier akzeptieren wir deutsche und englische Feldnamen.
    netto = _to_float(_first(item, "netto", "netAmount", "amountNet", default=0.0))
    steuer = _to_float(_first(item, "steuer", "steuer_betrag", "taxAmount", default=0.0))
    brutto = _to_float(_first(item, "brutto", "grossAmount", "amountGross", default=0.0))

    return {
        "beschreibung": _first(item, "beschreibung", "description", "name", default="Position"),
        "menge": _to_float(_first(item, "menge", "quantity", default=1.0), 1.0),
        "einheit": _first(item, "einheit", "unit", default="Stk."),
        "einzelpreis": _to_float(_first(item, "einzelpreis", "unitPrice", "price", default=0.0)),
        "steuer_prozent": _to_float(_first(item, "steuer_prozent", "taxRate", "vatRate", default=19.0), 19.0),
        "netto": netto,
        "steuer": steuer,
        "brutto": brutto,
    }


def normalize_ai_invoice_payload(payload: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mappt ein n8n/LLM-Extraktionsergebnis auf Camunda-Prozessvariablen."""
    defaults = defaults or {}

    # n8n kann entweder ein verschachteltes Objekt {"invoice": {...}} liefern
    # oder die Rechnungsfelder direkt auf oberster Ebene. Beides wird unterstützt.
    invoice = payload.get("invoice") or payload.get("rechnung") or payload

    # Die AI kann Positionslisten unterschiedlich nennen. Wir vereinheitlichen
    # sie auf "lineItems", weil dieser Name an Camunda weitergegeben wird.
    raw_items = (
        invoice.get("lineItems")
        or invoice.get("positionen")
        or invoice.get("items")
        or invoice.get("rechnungspositionen")
        or []
    )
    line_items = [_normalize_line_item(item) for item in raw_items if isinstance(item, dict)]
    first_item = line_items[0] if line_items else {}

    # Ab hier entsteht der stabile Vertrag zu Camunda: Diese Variablennamen
    # werden im BPMN-Prozess und in den Workern erwartet.
    camunda_payload = {
        "invoiceId": _first(
            invoice,
            "invoiceId",
            "invoice_id",
            "invoiceNumber",
            "rechnungsnummer",
            default=defaults.get("invoiceId", ""),
        ),
        "customerName": _first(
            invoice,
            "customerName",
            "customer_name",
            "supplierName",
            "vendorName",
            "lieferant",
            "kunde",
            default=defaults.get("customerName", "Unbekannter Lieferant"),
        ),
        "totalAmount": _to_float(
            _first(invoice, "totalAmount", "total_amount", "invoiceTotal", "grossTotal", "gesamtbetrag", default=defaults.get("totalAmount", 0.0))
        ),
        "issueDate": _first(invoice, "issueDate", "issue_date", "invoiceDate", "rechnungsdatum", default=defaults.get("issueDate", str(date.today()))),
        "iban": _first(invoice, "iban", "IBAN", default=defaults.get("iban", "")),
        "currency": str(_first(invoice, "currency", "waehrung", "währung", default=defaults.get("currency", "EUR"))).upper(),
        "kundennummer": _first(invoice, "kundennummer", "customerNumber", "customer_id", default=defaults.get("kundennummer", "")),
        "zahlungsziel": _first(invoice, "zahlungsziel", "paymentTerms", "dueDate", default=defaults.get("zahlungsziel", "")),
        "rechnungstyp": _first(invoice, "rechnungstyp", "invoiceType", "type", default=defaults.get("rechnungstyp", "sonstiges")),
        "lineItems": line_items,
        "positionen": line_items,
        "rechnungsposten": line_items,
        "inputChannel": defaults.get("inputChannel", "ai"),
        "aiExtracted": True,
        "extractionConfidence": _to_float(_first(payload, "confidence", "extractionConfidence", default=0.0)),
        "sourcePdf": _first(payload, "sourcePdf", "fileName", "filename", default=defaults.get("sourcePdf", "")),
    }

    if first_item:
        # Manche Camunda-Formulare lesen Positionswerte als einzelne Variablen.
        # Die vollständige Liste bleibt in lineItems erhalten; diese Felder
        # befüllen zusätzlich einfache Formularfelder für die erste Position.
        camunda_payload.update(
            {
                "beschreibung": first_item["beschreibung"],
                "menge": first_item["menge"],
                "einheit": first_item["einheit"],
                "einzelpreis": first_item["einzelpreis"],
                "steuer_prozent": first_item["steuer_prozent"],
                "netto": first_item["netto"],
                "steuer": first_item["steuer"],
                "brutto": first_item["brutto"],
                "betrag": first_item["brutto"],
            }
        )

    return camunda_payload


def load_ai_invoice_payload(path: str | Path, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    # Wird für den lokalen CLI-Start genutzt: statt n8n direkt aufzurufen, kann eine
    # gespeicherte JSON-Datei mit AI-Ergebnis geladen werden.
    with Path(path).open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return normalize_ai_invoice_payload(payload, defaults)
