# Wishlist — Visión de diseño

> **Un archivo tranquilo de las cosas que quiero, donde los objetos hablan y la interfaz calla.**

---

## El futuro que buscamos

Es domingo por la tarde. Abro Wishlist y no hay nada que me grite: ni badges, ni colores de marca, ni botones compitiendo. Veo un muro oscuro y cálido donde las fotos de los productos flotan como piezas de una exposición, cada una con su proporción real. Debajo de cada una, en letra pequeña y mono, solo lo imprescindible: nombre, precio, fecha.

A la izquierda, mis carpetas como el índice de una revista. Despliego *Casa* y leo lo que hay dentro como una lista de texto limpia. Un clic y la vista me lleva a esa pieza.

Veo algo que me gusta en una web, copio la URL y la pego en cualquier sitio de la ventana. Dos segundos después está ahí, con su foto, su precio y su carpeta. No he rellenado ningún formulario.

Al cabo de unos meses, Wishlist no es una lista de la compra: es **mi gusto hecho visible**. La recorro para decidir qué compro de verdad, y la mitad de las veces descubro que ya no lo quiero. Eso también es que funciona.

---

## Principios

Cada principio dice qué **hacer** y, igual de importante, qué **dejar de hacer**.

### 1. El objeto es el protagonista
La imagen del producto es el único elemento "fuerte" de la pantalla. Todo lo demás es soporte.
- **Sí:** imágenes sin marco, con su proporción real y en mosaico (masonry); acciones que solo aparecen al pasar el ratón.
- **No:** tarjetas con borde o sombra, iconos de colores, botones siempre visibles, miniaturas en lugares secundarios. La barra lateral es solo texto.

### 2. Tipografía como estructura
La jerarquía la marcan el tamaño y el tipo de letra, no el color ni las cajas.
- **Sí:** Geist para el contenido; Geist Mono en mayúsculas para las etiquetas y los datos (`( WISHLIST )`, precios, fechas); títulos grandes con tracking negativo; contadores como superíndice `(09)`.
- **No:** negritas repartidas, más de dos tamaños de texto en un mismo bloque, emojis como iconos.

### 3. Cuadrícula editorial silenciosa
La página se organiza como una publicación impresa: columnas y líneas finas.
- **Sí:** separadores de 1px en `--line`, columnas claras, mucho espacio negativo.
- **No:** paneles con fondos distintos para separar zonas, esquinas muy redondeadas (máximo 6px en imágenes, píldoras solo en controles).

### 4. Paleta cálida y casi monocroma
Un negro que no es negro y un blanco que no es blanco. El color lo ponen los productos.
- **Sí:** `#1a1916` fondo · `#ece9e1` texto · `#7b776b` secundario · `#34322c` líneas. Solo aparece otro color para avisar de algo peligroso (borrar) o de un aviso.
- **No:** colores de acento decorativos, degradados, estados hover que cambien el tono.

### 5. Cero fricción para capturar
Guardar algo tiene que costar menos que dejar la pestaña abierta.
- **Sí:** un solo campo que distingue entre URL y búsqueda; pegar en cualquier parte; datos sacados automáticamente y editables en el mismo paso.
- **No:** formularios obligatorios, pasos de confirmación, elegir carpeta antes de ver el producto.

### 6. Calma por defecto
La app no reclama atención; la espera.
- **Sí:** animaciones cortas y suaves (≤ 400 ms), toasts discretos, confirmaciones solo si se borra algo.
- **No:** notificaciones, contadores de "novedades", modales que aparecen solos.

---

## Prueba de decisión

Ante cualquier cambio de UX o UI, pregúntate:

1. ¿Hace **más protagonista al objeto** o le quita espacio?
2. ¿Se puede resolver con **tipografía o espacio** en lugar de con un elemento nuevo?
3. ¿**Añade fricción** a guardar algo?
4. ¿Seguiría pareciendo una **página editorial** si le quitáramos las fotos?

Si alguna respuesta va en contra, el cambio necesita otra forma.

**Decisiones que esta visión ya ha tomado:**
- Barra lateral sin miniaturas ni precios → solo nombres (principios 1 y 2).
- Sin totales ni cifras agregadas (suma de precios, etc.): no ayudan a decidir y meten ruido (principio 6).
- Un único campo URL/búsqueda en vez de dos (principio 5).
- Icono de la app: un cuadrado liso `#1a1916` (principios 4 y 6).

**Decisiones que orienta a partir de ahora:**
- Una **vista en lista** podría encajar si es tipográfica (tipo índice), no una tabla con bordes.
- Un **estado "comprado"** o "descartado" debería apagar la pieza (opacidad, texto tachado en mono), no ponerle etiquetas de color.
- **Seguimiento de precios (hecho):** dato mono junto al precio, `79,00 € (↓21%)`, en el acento cálido `#d9694f`, el único color fuera de la paleta base. Nunca gráficos ni avisos. La referencia es el precio original: el tachado de la tienda al guardar o, si no hay, el precio de ese momento. Las subidas se aplican en silencio.

---

## Referencias
- [cosmos.so](https://www.cosmos.so/): tipografía, píldoras, imágenes flotantes, espacio negativo.
- Layout editorial en columnas con etiquetas `( F ) ( PROJECTS ) ( B ) ( S )`: cuadrícula de 1px, metadatos en mayúsculas, bloques de texto pequeños junto a imágenes grandes.
- Guarda nuevas referencias en `design/inspo/` y `design/referencias/`.
