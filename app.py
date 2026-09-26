"""Wishlist: Flask + SQLite, envuelto en una ventana nativa con pywebview."""
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta

from flask import Flask, g, jsonify, render_template, request, send_from_directory

import browser
import currency
import images
from scraper import scrape, sentence_case, strip_shop_name


def resource_path(rel):
    """Ruta a recursos empaquetados (funciona en desarrollo y dentro del .exe)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# La BD va en %APPDATA%: la carpeta temporal de PyInstaller se borra al cerrar.
DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "WishlistApp")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "wishlist.db")
IMG_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(IMG_DIR, exist_ok=True)

app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)
# Sin caché para HTML/CSS/JS: el navegador de la app es persistente y, si no,
# podría seguir usando una versión antigua de la interfaz tras actualizarla.
# (Las imágenes de /img sí se cachean: sus nombres son únicos.)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def no_cache_pages(resp):
    if not request.path.startswith("/img/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp

SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT NOT NULL,
    title      TEXT NOT NULL,
    image      TEXT,
    price      TEXT,
    notes      TEXT,
    folder_id  INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        # Columnas añadidas en versiones posteriores (seguimiento de precios)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(items)")}
        if "ref_price" not in cols:
            conn.execute("ALTER TABLE items ADD COLUMN ref_price TEXT")   # precio original
        if "checked_at" not in cols:
            conn.execute("ALTER TABLE items ADD COLUMN checked_at TEXT")  # última comprobación

        # Migraciones de datos de un solo uso (versión guardada en la propia BD)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            # Títulos en formato frase: solo la primera letra en mayúscula
            for iid, title, url in conn.execute("SELECT id, title, url FROM items").fetchall():
                new = sentence_case(strip_shop_name(title, url))
                if new != title:
                    conn.execute("UPDATE items SET title = ? WHERE id = ?", (new, iid))
            conn.execute("PRAGMA user_version = 1")


def migrate_existing():
    """Tareas de fondo al arrancar: migraciones y después la comprobación de precios."""
    check_state["running"] = True  # la interfaz sigue vigilando desde el primer momento
    try:
        localize_existing()
        convert_existing()
        browser.wait_available()  # para poder usar el navegador oculto con tiendas como Zara
        check_prices()
    finally:
        check_state["running"] = False


def convert_existing():
    """Pasa a euros los precios en moneda extranjera, fija la referencia si falta
    y limpia notas antiguas de conversión."""
    conn = sqlite3.connect(DB_PATH)
    try:
        for iid, price, ref, notes, url in conn.execute(
            "SELECT id, price, ref_price, notes, url FROM items"
        ).fetchall():
            new_price = currency.to_euros(price, url)
            new_ref = currency.to_euros(ref, url) if ref else new_price
            new_notes = currency.strip_note(notes)
            if (new_price, new_ref, new_notes) != (price, ref, notes):
                conn.execute("UPDATE items SET price = ?, ref_price = ?, notes = ? WHERE id = ?",
                             (new_price, new_ref, new_notes, iid))
                conn.commit()
    finally:
        conn.close()


# ---------- Seguimiento de precios ----------

CHECK_EVERY = timedelta(hours=12)   # como mucho una lectura por producto cada 12 h
CHECK_PAUSE = 1.5                   # segundos entre tiendas, para no parecer un bot
check_state = {"running": False, "updated": 0}


def check_prices():
    """Vuelve a leer el precio de cada producto y lo actualiza en silencio.

    La rebaja se calcula en la interfaz comparando con ref_price (el precio original),
    así que aquí solo se guarda el precio actual, suba o baje.
    """
    check_state.update(running=True, updated=0)
    conn = sqlite3.connect(DB_PATH)
    try:
        limit = (datetime.now() - CHECK_EVERY).isoformat(timespec="seconds")
        pending = conn.execute(
            """SELECT id, url, price FROM items
               WHERE url LIKE 'http%' AND (checked_at IS NULL OR checked_at < ?)""",
            (limit,),
        ).fetchall()
        for iid, url, price in pending:
            now = datetime.now().isoformat(timespec="seconds")
            try:
                new = currency.to_euros(scrape(url, timeout=10).get("price"), url)
            except Exception:
                new = None  # tienda caída, bloqueo, producto retirado… se ignora
            if new and currency.parse_amount(new) is not None and new != price:
                # "price IS ?": si lo editaste a mano mientras tanto, no se pisa
                cur = conn.execute(
                    "UPDATE items SET price = ?, checked_at = ? WHERE id = ? AND price IS ?",
                    (new, now, iid, price))
                check_state["updated"] += cur.rowcount
            else:
                conn.execute("UPDATE items SET checked_at = ? WHERE id = ?", (now, iid))
            conn.commit()
            time.sleep(CHECK_PAUSE)
    finally:
        conn.close()
        check_state["running"] = False


def localize_existing():
    """Pasa a local las imágenes remotas guardadas antes de existir la caché."""
    conn = sqlite3.connect(DB_PATH)
    try:
        pending = conn.execute(
            "SELECT id, image, url FROM items WHERE image LIKE 'http%'"
        ).fetchall()
        for iid, image, url in pending:
            local = images.localize(image, IMG_DIR, referer=url)
            if images.is_local(local):
                conn.execute("UPDATE items SET image = ? WHERE id = ?", (local, iid))
                conn.commit()
    finally:
        conn.close()


def rows(cursor):
    return [dict(r) for r in cursor.fetchall()]


def error(msg, code=400):
    return jsonify({"error": msg}), code


# ---------- Páginas ----------

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/img/<path:name>")
def local_image(name):
    # Nombres únicos (uuid) -> se pueden cachear "para siempre"
    return send_from_directory(IMG_DIR, name, max_age=31536000)


# ---------- Carpetas ----------

@app.get("/api/folders")
def list_folders():
    return jsonify(rows(db().execute(
        """SELECT f.id, f.name, COUNT(i.id) AS count
           FROM folders f LEFT JOIN items i ON i.folder_id = f.id
           GROUP BY f.id ORDER BY f.name COLLATE NOCASE"""
    )))


@app.post("/api/folders")
def create_folder():
    name = (request.json or {}).get("name", "").strip()
    if not name:
        return error("El nombre no puede estar vacío")
    try:
        cur = db().execute("INSERT INTO folders (name) VALUES (?)", (name,))
        db().commit()
    except sqlite3.IntegrityError:
        return error("Ya existe una carpeta con ese nombre")
    return jsonify({"id": cur.lastrowid, "name": name}), 201


@app.patch("/api/folders/<int:fid>")
def rename_folder(fid):
    name = (request.json or {}).get("name", "").strip()
    if not name:
        return error("El nombre no puede estar vacío")
    try:
        db().execute("UPDATE folders SET name = ? WHERE id = ?", (name, fid))
        db().commit()
    except sqlite3.IntegrityError:
        return error("Ya existe una carpeta con ese nombre")
    return jsonify({"ok": True})


@app.delete("/api/folders/<int:fid>")
def delete_folder(fid):
    # Los artículos no se borran: pasan a "Sin carpeta" (ON DELETE SET NULL)
    db().execute("DELETE FROM folders WHERE id = ?", (fid,))
    db().commit()
    return jsonify({"ok": True})


# ---------- Artículos ----------

@app.get("/api/items")
def list_items():
    folder = request.args.get("folder", "all")
    sql, params = "SELECT * FROM items", ()
    if folder == "none":
        sql += " WHERE folder_id IS NULL"
    elif folder != "all":
        sql += " WHERE folder_id = ?"
        params = (int(folder),)
    sql += " ORDER BY created_at DESC"
    return jsonify(rows(db().execute(sql, params)))


@app.get("/api/counts")
def counts():
    c = db().execute(
        "SELECT COUNT(*) AS total, SUM(folder_id IS NULL) AS none FROM items"
    ).fetchone()
    return jsonify({"all": c["total"], "none": c["none"] or 0})


@app.get("/api/check-status")
def check_status():
    """La interfaz lo consulta para refrescar cuando cambian precios en segundo plano."""
    return jsonify(check_state)


@app.post("/api/preview")
def preview():
    """Extrae los datos sin guardar, para que el usuario los revise."""
    url = (request.json or {}).get("url", "").strip()
    if not url.startswith(("http://", "https://")):
        return error("La URL debe empezar por http:// o https://")
    try:
        data = scrape(url)
    except Exception as exc:  # red, 403, timeouts...
        return error(f"No se pudo leer la página ({exc.__class__.__name__}). "
                     "Puedes rellenar los datos a mano.", 502)
    # Moneda extranjera -> euros (también el precio antes de rebaja, si lo hay)
    data["price"] = currency.to_euros(data.get("price"), url)
    data["ref_price"] = currency.to_euros(data.pop("original_price", None), url)
    return jsonify(data)


@app.post("/api/items")
def create_item():
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return error("Falta la URL")
    # Por si el precio se escribió a mano en otra moneda
    data["price"] = currency.to_euros(data.get("price"), url)
    # Referencia = precio antes de rebaja si la tienda lo mostraba y es mayor;
    # si no, el precio al guardarlo
    ref = currency.to_euros(data.get("ref_price"), url)
    cur_v, ref_v = currency.parse_amount(data.get("price")), currency.parse_amount(ref)
    if not (cur_v and ref_v and ref_v > cur_v):
        ref = data.get("price")
    cur = db().execute(
        """INSERT INTO items (url, title, image, price, ref_price, notes, folder_id,
                                created_at, checked_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            url,
            (data.get("title") or url).strip(),
            images.localize(data.get("image") or None, IMG_DIR, referer=url),
            data.get("price") or None,
            ref or None,                        # precio original (referencia)
            data.get("notes") or None,
            data.get("folder_id") or None,
            datetime.now().isoformat(timespec="seconds"),
            datetime.now().isoformat(timespec="seconds"),  # recién leído
        ),
    )
    db().commit()
    return jsonify({"id": cur.lastrowid}), 201


EDITABLE = ("title", "image", "price", "notes", "folder_id", "url")


@app.patch("/api/items/<int:iid>")
def update_item(iid):
    data = request.json or {}
    fields = {k: (data[k] or None) for k in EDITABLE if k in data}
    if not fields:
        return error("Nada que actualizar")
    old = db().execute("SELECT image, url, price FROM items WHERE id = ?", (iid,)).fetchone()
    if old is None:
        return error("No existe", 404)
    if fields.get("price"):
        fields["price"] = currency.to_euros(fields["price"], fields.get("url") or old["url"])
        # Si cambias el precio a mano, ese pasa a ser el nuevo precio original.
        # (El diálogo de edición reenvía siempre el precio: solo cuenta si cambia.)
        if currency.parse_amount(fields["price"]) != currency.parse_amount(old["price"]):
            fields["ref_price"] = fields["price"]
    if "image" in fields and fields["image"] != old["image"]:
        fields["image"] = images.localize(
            fields["image"], IMG_DIR, referer=fields.get("url") or old["url"]
        )
    sets = ", ".join(f"{k} = ?" for k in fields)
    db().execute(f"UPDATE items SET {sets} WHERE id = ?", (*fields.values(), iid))
    db().commit()
    if "image" in fields and fields["image"] != old["image"]:
        images.remove(old["image"], IMG_DIR)
    return jsonify({"ok": True})


@app.delete("/api/items/<int:iid>")
def delete_item(iid):
    row = db().execute("SELECT image FROM items WHERE id = ?", (iid,)).fetchone()
    db().execute("DELETE FROM items WHERE id = ?", (iid,))
    db().commit()
    if row:
        images.remove(row["image"], IMG_DIR)
    return jsonify({"ok": True})


class JsApi:
    """Funciones expuestas a JS vía window.pywebview.api."""

    def open_url(self, url):
        import webbrowser
        webbrowser.open(url)


if __name__ == "__main__":
    import webview

    # Identidad propia en Windows: la barra de tareas muestra nuestro icono
    # en vez del de Python y no agrupa la ventana con otros scripts.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Wishlist.App")
    except Exception:
        pass

    init_db()
    browser.expected = True
    threading.Thread(target=migrate_existing, daemon=True).start()

    # Puerto fijo: el navegador guarda las preferencias de la interfaz por dirección,
    # y con un puerto aleatorio cada arranque sería una dirección "nueva". Si está
    # ocupado, se usa uno libre cualquiera (se pierden preferencias, pero la app abre).
    import socket
    PORT = 47391
    with socket.socket() as s:
        port = PORT if s.connect_ex(("127.0.0.1", PORT)) != 0 else None

    webview.create_window(
        "Wishlist",
        app,  # pywebview sirve la app WSGI en local
        http_port=port,
        js_api=JsApi(),
        width=1200,
        height=800,
        min_size=(560, 480),
        background_color="#1a1916",  # sin destello blanco al abrir
    )

    def on_start():
        browser.available = True  # ya se pueden abrir ventanas ocultas de lectura

    # Perfil de navegador persistente (no privado): conserva las preferencias de la
    # interfaz (tamaño S/M/L, carpetas abiertas) y las verificaciones ya superadas
    # en tiendas como COS, para no repetir su espera en cada arranque.
    webview.start(
        on_start,
        icon=resource_path("icon.ico"),
        private_mode=False,
        storage_path=os.path.join(DATA_DIR, "webview"),
    )
