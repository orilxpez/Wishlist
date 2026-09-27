"""Lectura con navegador para tiendas que no sirven la página a lectores simples.

Algunas tiendas (Zara, por ejemplo) responden primero con una verificación que
solo supera un navegador que ejecute JavaScript. En esos casos se abre la página
en una ventana OCULTA de la propia app (WebView2, el mismo motor que su ventana),
se espera a que cargue como en cualquier navegador y se lee el HTML resultante.

No resuelve captchas: si la tienda pide uno, no aparecerá el precio y se
devuelve lo que haya, para rellenar a mano.
"""
import threading
import time

_lock = threading.Lock()   # una ventana oculta cada vez
available = False          # True cuando la ventana principal de pywebview ya está en marcha
expected = False           # True si la app se ejecuta con ventana (no en pruebas/servidor)


def wait_available(timeout=20):
    """Espera a que la ventana esté lista, si se espera que la haya."""
    t0 = time.time()
    while expected and not available and time.time() - t0 < timeout:
        time.sleep(0.25)

# ¿Ya hay datos de producto en la página?
READY_JS = """
!!(document.querySelector('meta[property="og:price:amount"], meta[property="product:price:amount"]')
   || [...document.querySelectorAll('script[type="application/ld+json"]')]
        .some(s => /"price"\\s*:/i.test(s.textContent))
   || document.querySelector('[itemprop="price"]')
   || document.querySelector('#productTitle') && document.querySelector('.a-price .a-offscreen'))  // Amazon
"""


# Pantallas de espera / verificación (COS, Akamai, Cloudflare…): se aguanta más
# Incluye páginas aún "vacías" (sin título ni apenas texto): las verificaciones por
# JavaScript (COS, Akamai…) se ven así mientras trabajan.
WAITING_JS = r"""
(() => {
  const title = document.title || '';
  const text = ((document.body && document.body.innerText) || '').trim();
  return !title.trim() || text.length < 200 ||
    /patience|waiting room|queue|just a moment|checking your browser|verif|un momento|espera/i
      .test(title + ' ' + text.slice(0, 400));
})()
"""
EXTENDED_TIMEOUT = 60


def fetch(url, timeout=20):
    """Devuelve (html, url_final) renderizados, o None si no se puede.

    Espera hasta `timeout` s a que aparezcan datos de producto; si la tienda está
    mostrando una pantalla de espera o verificación, amplía hasta EXTENDED_TIMEOUT.
    """
    if not available:
        return None
    import webview

    with _lock:
        win = None
        try:
            win = webview.create_window("", url, hidden=True)
            t0 = time.time()
            limit = timeout
            ready = reloaded = False
            while time.time() - t0 < limit:
                time.sleep(0.5)
                try:
                    ready = bool(win.evaluate_js(READY_JS))
                    if not ready and limit == timeout and win.evaluate_js(WAITING_JS):
                        limit = EXTENDED_TIMEOUT  # la tienda nos tiene en espera
                    # Algunas tiendas (Amazon) muestran una página intermedia la primera
                    # vez y el producto a partir de la siguiente carga: se recarga una vez.
                    if not ready and not reloaded and time.time() - t0 > 6 and limit == timeout:
                        reloaded = True
                        win.load_url(url)
                except Exception:
                    ready = False
                if ready:
                    break
            if ready:
                time.sleep(0.8)  # margen para que se pinte el precio tachado
            # Si justo está navegando (redirección tras la verificación) se reintenta
            for _ in range(3):
                try:
                    html = win.evaluate_js("document.documentElement.outerHTML")
                    final = win.evaluate_js("location.href") or url
                    if html:
                        return html, final
                except Exception:
                    pass
                time.sleep(1)
            return None
        except Exception:
            return None
        finally:
            if win is not None:
                try:
                    win.destroy()
                except Exception:
                    pass
