"""Extracción de título, imagen y precio de una URL de producto.

Orden de preferencia:
  1. Metadatos Open Graph / product:* / twitter:*
  2. JSON-LD de schema.org (tipo Product)
  3. Selectores específicos (Amazon) y microdatos itemprop
  4. Fallback genérico (<title>, primera imagen grande)
"""
import json
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import currency

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£", "JPY": "¥"}


def _meta(soup, *names):
    """Devuelve el content del primer <meta property|name=...> encontrado."""
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find(
            "meta", attrs={"name": name}
        )
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _iter_jsonld(soup):
    """Itera todos los objetos JSON-LD, aplanando listas y @graph."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = [data]
        while stack:
            obj = stack.pop()
            if isinstance(obj, list):
                stack.extend(obj)
            elif isinstance(obj, dict):
                if "@graph" in obj:
                    stack.append(obj["@graph"])
                yield obj


def _jsonld_product(soup):
    """Primer Product del JSON-LD. Si es un ProductGroup (producto con variantes,
    como en Zara), toma nombre e imagen del grupo y el precio de la 1.ª variante."""
    for obj in _iter_jsonld(soup):
        types = obj.get("@type")
        types = types if isinstance(types, list) else [types]
        if "ProductGroup" in types:
            variants = obj.get("hasVariant")
            variants = variants if isinstance(variants, list) else [variants]
            first = next((v for v in variants if isinstance(v, dict)), {})
            return {**first, **{k: obj[k] for k in ("name", "image") if obj.get(k)},
                    "offers": first.get("offers") or obj.get("offers")}
        if "Product" in types:
            return obj
    return None


def _format_price(amount, currency):
    if amount in (None, ""):
        return None
    amount = str(amount).strip()
    symbol = CURRENCY_SYMBOLS.get((currency or "").upper(), currency or "")
    # Si ya lleva símbolo (p.ej. "29,99 €"), se deja tal cual
    if re.search(r"[€$£¥]", amount):
        return amount
    return f"{amount} {symbol}".strip()


def _price_from_offers(offers):
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    if not isinstance(offers, dict):
        return None
    amount = offers.get("price") or offers.get("lowPrice")
    if amount is None and isinstance(offers.get("priceSpecification"), dict):
        amount = offers["priceSpecification"].get("price")
    return _format_price(amount, offers.get("priceCurrency"))


def _image_from_jsonld(image):
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")
    return image


def _amazon(soup):
    """Selectores específicos de Amazon (no usa og:price)."""
    title = soup.select_one("#productTitle")
    img = soup.select_one("#landingImage, #imgBlkFront")
    image = None
    if img:
        # data-a-dynamic-image es un JSON {url: [w, h]}; nos quedamos con la mayor
        dyn = img.get("data-a-dynamic-image")
        if dyn:
            try:
                sizes = json.loads(dyn)
                image = max(sizes, key=lambda u: sizes[u][0] * sizes[u][1])
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        image = image or img.get("data-old-hires") or img.get("src")
    price = soup.select_one(
        "#corePrice_feature_div .a-offscreen, "
        "#corePriceDisplay_desktop_feature_div .a-offscreen, "
        ".priceToPay .a-offscreen, #priceblock_ourprice, #priceblock_dealprice"
    )
    return (
        title.get_text(strip=True) if title else None,
        image,
        price.get_text(strip=True) if price else None,
    )


def sentence_case(text):
    """'CHIA EAR CUFF PLATA' / 'Camisa De Lino' -> 'Chia ear cuff plata' / 'Camisa de lino'."""
    if not text:
        return text
    text = " ".join(text.split()).lower()
    for i, ch in enumerate(text):
        if ch.isalpha():
            return text[:i] + ch.upper() + text[i + 1:]
        if ch.isdigit():
            return text  # "2 pack camisetas": si empieza por número, todo en minúscula
    return text


def strip_shop_name(title, url):
    """'Billy librería … - IKEA' -> 'Billy librería …' si el sufijo es el nombre de la web."""
    host = (urlparse(url).hostname or "").lower().split(".")
    brand = next((p for p in host if p not in ("www", "www2", "shop", "es", "com", "co", "uk")), "")
    if brand and title:
        # Tolera símbolos entre letras: dominio "hm" ↔ "H&M"
        name = r"\W?".join(map(re.escape, brand))
        title = re.sub(rf"\s*[-|–·]\s*{name}(\s+\w+)?\s*$", "", title, flags=re.I)
    return title


def _jsonld_strike(product):
    """Precio tachado declarado en JSON-LD (priceType StrikethroughPrice / ListPrice)."""
    offers = product.get("offers")
    offers = offers if isinstance(offers, list) else [offers]
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        specs = offer.get("priceSpecification")
        specs = specs if isinstance(specs, list) else [specs]
        for spec in specs:
            if isinstance(spec, dict) and re.search(
                r"Strikethrough|ListPrice|MSRP", str(spec.get("priceType", "")), re.I
            ):
                return _format_price(spec.get("price"),
                                     spec.get("priceCurrency") or offer.get("priceCurrency"))
    return None


# Precio anterior en tiendas genéricas: clases habituales y etiquetas de tachado
STRIKE_SELECTORS = (
    ".basisPrice .a-offscreen, span.a-price.a-text-price[data-a-strike='true'] .a-offscreen, "
    "#listPrice, .a-text-strike, "
    "[class*='compare-at'], [class*='compare_at'], [class*='was-price'], [class*='wasPrice'], "
    "[class*='original-price'], [class*='originalPrice'], [class*='price--old'], "
    "[class*='old-price'], [class*='oldPrice'], [class*='price-old'], [class*='regular-price'], "
    "[class*='price--compare'], [class*='strikethrough'], [class*='crossed'], "
    "del, s"
)


def _original_price(soup, product, price):
    """Precio antes de la rebaja, si la página lo muestra. None si no está rebajado.

    Solo se acepta si es mayor que el precio actual y como mucho 5 veces él,
    para no confundir un "antes" con otro número cualquiera de la página.
    """
    current = currency.parse_amount(price)
    if not current:
        return None

    def plausible(text):
        value = currency.parse_amount(text)
        return text if value and current < value <= current * 5 else None

    candidates = [
        _meta(soup, "og:price:standard_amount", "product:original_price:amount"),
        _jsonld_strike(product) if product else None,
    ]
    for c in candidates:
        if c and plausible(c):
            return _format_price(c, _meta(soup, "og:price:currency", "product:price:currency"))
    for tag in soup.select(STRIKE_SELECTORS)[:40]:
        text = tag.get_text(" ", strip=True)
        # Solo textos cortos que parecen un precio (con cifra y símbolo o código)
        if 0 < len(text) <= 24 and re.search(r"\d", text) and re.search(r"[€$£¥]|[A-Z]{3}", text):
            if plausible(text):
                return text
    return None


def scrape(url, timeout=12):
    """Devuelve dict con title, image, price y original_price (precio antes de rebaja).

    Primero una lectura rápida; si la tienda la bloquea o no trae precio, se
    reintenta con el navegador oculto de la app (ver browser.py).
    Lanza excepción si no se puede leer de ninguna forma.
    """
    import browser

    fast, error = None, None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        # Bytes, no resp.text: así BeautifulSoup lee el <meta charset> de la página
        # en vez de fiarse de requests (que asume Latin-1 si la cabecera no lo dice)
        fast = parse(resp.content, resp.url)
        if fast["price"]:
            return fast
    except Exception as exc:
        error = exc

    rendered = browser.fetch(url)
    if rendered:
        slow = parse(rendered[0].encode("utf-8"), rendered[1])
        if slow["price"] or not fast:
            return slow
    if fast:
        return fast
    raise error or RuntimeError("No se pudo leer la página")


def parse(html, final_url):
    soup = BeautifulSoup(html, "html.parser")
    url = final_url

    # 1. Open Graph y variantes
    title = _meta(soup, "og:title", "twitter:title")
    image = _meta(soup, "og:image", "og:image:url", "og:image:secure_url", "twitter:image")
    cur_code = _meta(soup, "og:price:currency", "product:price:currency")
    price = _format_price(_meta(soup, "og:price:amount", "product:price:amount"), cur_code)
    # Catálogos tipo Facebook/Shopify: price = normal, sale_price = rebajado
    sale = _format_price(_meta(soup, "product:sale_price:amount", "og:sale_price:amount"),
                         _meta(soup, "product:sale_price:currency") or cur_code)
    meta_original = None
    if sale and price and currency.parse_amount(sale) and \
            currency.parse_amount(sale) < (currency.parse_amount(price) or 0):
        price, meta_original = sale, price

    # 2. JSON-LD Product
    product = _jsonld_product(soup)
    if product:
        title = title or product.get("name")
        image = image or _image_from_jsonld(product.get("image"))
        price = price or _price_from_offers(product.get("offers"))

    # 3. Amazon + microdatos
    if "amazon." in final_url:
        a_title, a_image, a_price = _amazon(soup)
        title = a_title or title  # og:title de Amazon suele ser genérico
        image = a_image or image
        price = a_price or price
    if not price:
        tag = soup.find(attrs={"itemprop": "price"})
        if tag:
            cur = soup.find(attrs={"itemprop": "priceCurrency"})
            price = _format_price(
                tag.get("content") or tag.get_text(strip=True),
                cur.get("content") if cur else None,
            )

    # 4. Fallback genérico
    if not title and soup.title:
        title = soup.title.get_text(strip=True)
    if not image:
        img = soup.find("img", src=re.compile(r"\.(jpe?g|png|webp)", re.I))
        image = img["src"] if img else None

    if image:
        image = urljoin(final_url, image)

    return {
        "title": sentence_case(strip_shop_name(title, url))[:300] if title else url,
        "image": image,
        "price": price,
        "original_price": meta_original or _original_price(soup, product, price),
    }
