# Wishlist

App de escritorio para Windows para guardar productos de tiendas online en carpetas.
Pegas la URL de un producto y la app saca sola el título, la imagen y el precio.

- Carpetas propias, con arrastrar y soltar para mover productos.
- Precios en otras monedas convertidos a euros (tipos del BCE).
- Seguimiento de rebajas: al abrir la app se revisan los precios y las bajadas se marcan como `(↓21%)`.
- Imágenes guardadas en local, así que funciona sin conexión salvo para añadir productos.
- Lee también tiendas que bloquean lectores simples (Zara, COS…) con un navegador oculto.

Hecha con Flask, pywebview (WebView2) y SQLite. La dirección de diseño está en [design/VISION.md](design/VISION.md).

## Uso

Necesitas Python 3.10 o superior.

1. Ejecuta `build.bat`. Crea el entorno, instala las dependencias y genera `dist\Wishlist.exe`.
2. Para abrir la app sin compilar, usa `run_dev.bat`.

Los datos (base de datos e imágenes) se guardan en `%APPDATA%\WishlistApp`, fuera del proyecto.

## Tipografía

Usa [Geist y Geist Mono](https://vercel.com/font) (licencia SIL Open Font License), incluidas en `static/fonts`.
