"""Conversión automática a euros con tipos del BCE (api.frankfurter.dev, sin clave)."""
import re
import time
from urllib.parse import urlparse

import requests

RATES_URLS = (
    "https://api.frankfurter.dev/v1/latest?base=EUR",
    "https://api.frankfurter.app/latest?from=EUR",
)
_cache = {"rates": None, "at": 0.0}
TTL = 6 * 3600

# Símbolos compuestos primero: "US$" antes que "$"
SYMBOLS = [
    ("US$", "USD"), ("CA$", "CAD"), ("C$", "CAD"), ("AU$", "AUD"), ("A$", "AUD"),
    ("MX$", "MXN"), ("R$", "BRL"), ("HK$", "HKD"), ("NZ$", "NZD"), ("S$", "SGD"),
    ("zł", "PLN"), ("Kč", "CZK"), ("€", "EUR"), ("£", "GBP"), ("¥", "JPY"),
    ("₩", "KRW"), ("₹", "INR"), ("₺", "TRY"), ("₪", "ILS"), ("$", "USD"),
]
# "$" a secas según el dominio de la tienda
DOLLAR_BY_TLD = {".ca": "CAD", ".com.au": "AUD", ".au": "AUD", ".com.mx": "MXN",
                 ".mx": "MXN", ".co.nz": "NZD", ".sg": "SGD", ".com.hk": "HKD"}
ISO = re.compile(r"\b([A-Z]{3})\b")
NOTE_PREFIX = "Precio original:"


def parse_amount(text):
    """'1.299,99' / '1,299.99' / '1.299' / '29,99' -> float (misma lógica que app.js)."""
    s = re.sub(r"[^\d.,]", "", text or "").rstrip(".,")
    if not s:
        return None
    comma, dot = s.rfind(","), s.rfind(".")
    if comma >= 0 and dot >= 0:
        s = s.replace(".", "").replace(",", ".") if comma > dot else s.replace(",", "")
    else:
        sep = "," if comma >= 0 else "."
        parts = s.split(sep)
        thousands = len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3)
        s = "".join(parts) if thousands else ".".join(parts)
    try:
        return float(s)
    except ValueError:
        return None


def detect(price, url=None):
    """Devuelve (importe, código ISO) o (importe, None) si no se reconoce la moneda."""
    if not price:
        return None, None
    amount = parse_amount(price)
    m = ISO.search(price.upper())
    if m and m.group(1) in _known_codes():
        return amount, m.group(1)
    for sym, code in SYMBOLS:
        if sym in price:
            if sym == "$" and url:
                host = urlparse(url).hostname or ""
                for tld, c in DOLLAR_BY_TLD.items():
                    if host.endswith(tld):
                        return amount, c
            return amount, code
    return amount, None


def _known_codes():
    base = {"EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "MXN", "BRL", "PLN",
            "CZK", "SEK", "NOK", "DKK", "KRW", "INR", "TRY", "ILS", "HKD", "NZD",
            "SGD", "CNY", "HUF", "RON", "ZAR"}
    return base | set((_cache["rates"] or {}).keys())


def rates():
    """Tipos EUR->X, cacheados 6 h. None si no hay conexión."""
    if _cache["rates"] and time.time() - _cache["at"] < TTL:
        return _cache["rates"]
    for u in RATES_URLS:
        try:
            r = requests.get(u, timeout=6)
            r.raise_for_status()
            _cache["rates"] = r.json()["rates"]
            _cache["at"] = time.time()
            return _cache["rates"]
        except Exception:
            continue
    return _cache["rates"]  # el último conocido, aunque esté caducado


def format_eur(value):
    s = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def to_euros(price, url=None):
    """Si el precio está en otra moneda lo devuelve en euros; si no, igual."""
    amount, code = detect(price, url)
    if amount is not None and code == "EUR" and "EUR" in price.upper():
        return format_eur(amount)  # "29,95 EUR" -> "29,95 €"
    if amount is None or code in (None, "EUR"):
        return price
    table = rates()
    if not table or code not in table:
        return price
    return format_eur(amount / table[code])


def strip_note(notes):
    """Quita la anotación "Precio original: …" que añadían versiones anteriores."""
    if not notes or NOTE_PREFIX not in notes:
        return notes
    return re.sub(rf"\s*·?\s*{NOTE_PREFIX}[^·]*", "", notes).strip(" ·") or None
