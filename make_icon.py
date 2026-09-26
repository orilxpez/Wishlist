"""Genera icon.ico: cuadrado redondeado #1a1916 con "()" en Geist Mono, como las etiquetas de la app."""
from PIL import Image, ImageDraw, ImageFont

BG = (26, 25, 22, 255)      # --bg
FG = (236, 233, 225, 255)   # --text
FONT = "static/fonts/GeistMono.woff2"
RADIUS = 0.225              # esquinas redondeadas (proporción del lado)
GAP = 0.0                   # hueco extra entre paréntesis (proporción del lado)


def render(size):
    # Se dibuja a 4x y se reduce: bordes más limpios en tamaños pequeños
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * RADIUS), fill=BG)

    font = ImageFont.truetype(FONT, int(S * 0.46))
    # En tamaños pequeños, trazo más grueso para que se siga leyendo
    weight = 400 if size >= 64 else 560 if size >= 32 else 700
    try:
        font.set_variation_by_axes([weight])
    except Exception:
        pass

    # Cada paréntesis por separado para controlar el hueco entre ellos
    boxes = [d.textbbox((0, 0), ch, font=font) for ch in "()"]
    widths = [b[2] - b[0] for b in boxes]
    top = min(b[1] for b in boxes)
    height = max(b[3] for b in boxes) - top
    gap = S * GAP
    x = (S - (sum(widths) + gap)) / 2
    y = (S - height) / 2 - top
    for ch, box, w in zip("()", boxes, widths):
        d.text((x - box[0], y), ch, font=font, fill=FG)
        x += w + gap
    return img.resize((size, size), Image.LANCZOS)


sizes = [16, 24, 32, 48, 64, 128, 256]
frames = [render(s) for s in sizes]
frames[-1].save("icon.ico", sizes=[(s, s) for s in sizes], append_images=frames[:-1])
print("icon.ico generado")
