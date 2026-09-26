# ( Wishlist )

App de escritorio para Windows que guarda productos de cualquier tienda online en
carpetas. Pegas la URL de un producto y la app saca sola el título, la imagen y el
precio, y después avisa si baja de precio.

---

## Qué hace

- **Añadir por URL.** Pega el enlace de un producto (en el buscador o en cualquier parte
  de la ventana) y la app extrae título, imagen y precio. Antes de guardar puedes
  revisarlos y corregirlos.
- **Carpetas.** Crea, renombra y elimina carpetas propias. Mueve productos arrastrando la
  tarjeta a la barra lateral o desde el menú de la tarjeta. Cada carpeta se despliega
  para ver sus productos. Lo que no tiene carpeta queda en `( Sin carpeta )`.
- **Rebajas.** Cada vez que abres la app se revisan los precios en segundo plano (como
  mucho cada 12 h por producto). Si un producto baja respecto a su precio original, se
  marca como `29,95 € (↓21%)`. Si al guardarlo ya estaba rebajado, se toma el precio
  tachado de la tienda como original. El orden **Rebaja** muestra primero los mayores
  descuentos.
- **Euros siempre.** Los precios en otras monedas (£, $, CHF, ¥…) se convierten
  automáticamente con los tipos del Banco Central Europeo.
- **Imágenes locales.** Cada imagen se descarga una vez, se reduce a 800 px y se guarda
  en WebP (unos 40–80 KB). Aunque la tienda la borre, la tuya sigue ahí, y la app carga
  al instante y sin conexión.
- **Tarjetas uniformes.** Marco 4:5 para todas. Los productos sobre fondo liso y las
  portadas se muestran enteros sobre su propio color de fondo; las fotos de modelo
  llenan la tarjeta.
- **Tiendas difíciles.** Las que bloquean lectores automáticos (Zara, COS…) se leen con
  una ventana oculta del navegador de la propia app. No resuelve captchas: si una tienda
  pide uno, los datos se rellenan a mano.
- **Buscar y ordenar** por fecha, precio, nombre o rebaja. Tres tamaños de tarjeta
  (S · M · L) y diseño adaptable, desde ventana pequeña a pantalla completa.

## Instalación

Necesitas **Windows 10/11** y **Python 3.10 o superior**.

```bat
git clone https://github.com/orilxpez/Wishlist.git
cd Wishlist
build.bat
```

`build.bat` crea el entorno virtual, instala las dependencias, genera el icono y
compila `dist\Wishlist.exe`, un único archivo que funciona sin Python instalado.

### Abrir la app

| Forma | Cuándo usarla |
|---|---|
| `dist\Wishlist.exe` | Para usarla o compartirla sin Python. Tarda ~1 s más en abrir porque se descomprime en cada arranque. |
| `run_dev.bat` | Mientras desarrollas: ejecuta el código directamente, sin compilar. |
| Acceso directo a `.venv\Scripts\pythonw.exe app.py` | La forma más rápida en tu propio equipo, sin consola, y no la bloquea Smart App Control. |

> **Smart App Control / SmartScreen.** El `.exe` no está firmado. Windows puede mostrar
> "Windows protegió su PC" (*Más información → Ejecutar de todas formas*) o bloquearlo
> si Smart App Control está activo. En ese caso, usa el acceso directo con `pythonw.exe`.

## Dónde se guardan los datos

Todo queda fuera del proyecto, en `%APPDATA%\WishlistApp`:

| Ruta | Contenido |
|---|---|
| `wishlist.db` | Base de datos SQLite: carpetas y productos |
| `images\` | Imágenes de los productos en WebP |
| `webview\` | Perfil del navegador interno: preferencias de la interfaz y verificaciones ya superadas en tiendas |

Para hacer una copia de seguridad o pasar tu wishlist a otro PC, copia esa carpeta.
Recompilar o actualizar la app no la toca.

## Estructura

```
app.py          Servidor Flask, API, base de datos y ventana (pywebview)
scraper.py      Extrae título, imagen y precio: Open Graph, JSON-LD y selectores de tienda
browser.py      Lectura con ventana oculta para tiendas que bloquean lectores simples
currency.py     Detección de moneda y conversión a euros (api.frankfurter.dev, BCE)
images.py       Descarga, reescalado y caché local de imágenes
templates/      HTML de la interfaz
static/         CSS, JavaScript y tipografías
design/         Visión de diseño y referencias
make_icon.py    Genera icon.ico
build.bat       Instala y compila el .exe
```

## Cómo lee una tienda

1. **Lectura rápida** con `requests` + BeautifulSoup, por orden de fiabilidad:
   metadatos Open Graph → JSON-LD de schema.org (`Product` y `ProductGroup` con variantes)
   → selectores específicos (Amazon) → microdatos → fallback genérico.
2. **Precio original**, si lo hay: `product:sale_price`, `StrikethroughPrice` en JSON-LD,
   el precio tachado de Amazon o las clases habituales de "antes" en tiendas.
3. Si la tienda bloquea la lectura o no trae precio, se abre la página en una **ventana
   oculta** (WebView2), se espera a que cargue como en cualquier navegador y se analiza
   el HTML resultante. Si la tienda muestra una pantalla de espera, se aguanta hasta 60 s.

## Diseño

Inspirado en [cosmos.so](https://www.cosmos.so/) y en maquetas editoriales: negro cálido
`#1a1916`, texto `#ece9e1`, líneas de 1 px, etiquetas `( ASÍ )` en mono y las imágenes
como protagonistas. Un único color de acento, `#d9694f`, reservado para rebajas y para
eliminar. Principios y decisiones en [design/VISION.md](design/VISION.md).

## Tecnología

[Flask](https://flask.palletsprojects.com/) · [pywebview](https://pywebview.flowrl.com/)
(WebView2) · SQLite · [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) ·
[Pillow](https://python-pillow.org/) · [PyInstaller](https://pyinstaller.org/) ·
tipos de cambio de [Frankfurter](https://frankfurter.dev/)

Tipografías [Geist y Geist Mono](https://vercel.com/font) de Vercel, con licencia
SIL Open Font License 1.1, incluidas en `static/fonts`.

## Limitaciones conocidas

- Algunas tiendas grandes (Amazon a veces) bloquean las lecturas automáticas. En esos
  productos no se detectan rebajas, pero no se rompe nada.
- Si una tienda cambia su página o el producto se agota, puede que no se encuentre el
  precio. Ese producto conserva el último precio conocido.
- La primera lectura de algunas tiendas (COS) tarda ~20 s por su verificación. Las
  siguientes son mucho más rápidas.
