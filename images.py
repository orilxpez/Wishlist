"""Caché local de imágenes: descarga una vez, reduce a 800 px y guarda en WebP."""
import io
import os
import uuid

import requests
from PIL import Image

from scraper import HEADERS

MAX_WIDTH = 800
MAX_BYTES = 15 * 1024 * 1024
LOCAL_PREFIX = "/img/"


def is_local(image):
    return bool(image) and image.startswith(LOCAL_PREFIX)


def localize(image_url, img_dir, referer=None):
    """Descarga image_url y devuelve '/img/<archivo>.webp'.

    Si algo falla (bloqueo, formato raro, sin red) devuelve la URL original,
    así el producto se guarda igualmente y la imagen se sigue viendo en remoto.
    """
    if not image_url or not image_url.startswith(("http://", "https://")):
        return image_url
    try:
        headers = dict(HEADERS, Accept="image/avif,image/webp,image/*,*/*;q=0.8")
        if referer:
            headers["Referer"] = referer  # algunas tiendas bloquean sin Referer
        resp = requests.get(image_url, headers=headers, timeout=10, stream=True)
        resp.raise_for_status()
        data = resp.raw.read(MAX_BYTES + 1, decode_content=True)
        if len(data) > MAX_BYTES:
            return image_url

        img = Image.open(io.BytesIO(data))
        img.load()
        # Transparencias (PNG) sobre blanco, como se ven en la tienda
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.getchannel("A"))
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        if img.width > MAX_WIDTH:
            img = img.resize((MAX_WIDTH, round(img.height * MAX_WIDTH / img.width)), Image.LANCZOS)

        name = f"{uuid.uuid4().hex}.webp"
        img.save(os.path.join(img_dir, name), "WEBP", quality=82, method=6)
        return LOCAL_PREFIX + name
    except Exception:
        return image_url


def remove(image, img_dir):
    """Borra el archivo local de una imagen (si lo es)."""
    if is_local(image):
        path = os.path.join(img_dir, os.path.basename(image))
        try:
            os.remove(path)
        except OSError:
            pass
