"""Genera la imagen de vista previa (1200x630) que muestran WhatsApp, Instagram, etc. al compartir
el enlace de la web: el próximo partido o, si esa noche hay varios, la lista de la noche."""
from __future__ import annotations

import io
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent
FUENTES = RAIZ / "recursos" / "fuentes"
W, H = 1200, 630
CARBON, ASFALTO, HUESO, PLATA, ROJO = (26, 26, 26), (36, 36, 36), (241, 238, 232), (167, 171, 177), (216, 35, 42)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
_cache: dict[str, Image.Image | None] = {}


def fuente(nombre: str, tam: int, peso: str) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FUENTES / nombre), tam)
    f.set_variation_by_name(peso)
    return f


def imagen(src: str | None) -> Image.Image | None:
    """Abre un escudo/logo local o lo baja de la web de la liga (con caché)."""
    if not src:
        return None
    if src in _cache:
        return _cache[src]
    try:
        if src.startswith("http"):
            r = httpx.get(src, headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content))
        else:
            im = Image.open(src)
        im = im.convert("RGBA")
        bbox = im.getbbox()
        _cache[src] = im.crop(bbox) if bbox else im
    except Exception:
        _cache[src] = None
    return _cache[src]


def pegar(lienzo: Image.Image, im: Image.Image | None, caja: tuple[int, int, int, int]) -> None:
    if im is None:
        return
    x, y, w, h = caja
    escala = min(w / im.width, h / im.height)  # agranda o achica para llenar la caja
    im = im.resize((max(1, round(im.width * escala)), max(1, round(im.height * escala))), Image.LANCZOS)
    lienzo.alpha_composite(im, (x + (w - im.width) // 2, y + (h - im.height) // 2))


def centrado(d: ImageDraw.ImageDraw, cx: int, y: int, texto: str, f, color) -> None:
    w = d.textlength(texto, font=f)
    d.text((cx - w / 2, y), texto, font=f, fill=color)


def recortar(d, texto: str, f, ancho: int) -> str:
    if d.textlength(texto, font=f) <= ancho:
        return texto
    while texto and d.textlength(texto + "…", font=f) > ancho:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGBA", (W, H), CARBON)
    d = ImageDraw.Draw(im)
    b = 34  # bisel del octógono del escudo
    octo = [(b, 0), (W - b, 0), (W, b), (W, H - b), (W - b, H), (b, H), (0, H - b), (0, b)]
    d.polygon(octo, fill=ROJO)
    i = 6
    interior = [(b + i * .4, i), (W - b - i * .4, i), (W - i, b + i * .4), (W - i, H - b - i * .4),
                (W - b - i * .4, H - i), (b + i * .4, H - i), (i, H - b - i * .4), (i, b + i * .4)]
    d.polygon(interior, fill=ASFALTO)
    # franja diagonal plateada (como en la web)
    franja = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(franja).polygon([(560, 6), (700, 6), (560, H - 6), (420, H - 6)], fill=(167, 171, 177, 16))
    im.alpha_composite(franja)
    return im, ImageDraw.Draw(im)


def generar(partidos: list, hoy: bool, logos_ligas: dict, destino: Path) -> None:
    im, d = base()
    titulo = fuente("BigShouldersDisplay.ttf", 46, "Black")
    escudo = RAIZ / "estaticos" / "img" / "escudo.png"

    if not partidos:
        pegar(im, imagen(str(escudo)), (450, 110, 300, 300))
        centrado(d, W // 2, 440, "VULTUR SPORTS", fuente("BigShouldersDisplay.ttf", 80, "Black"), HUESO)
        centrado(d, W // 2, 535, "Partidos, tablas y plantel", fuente("Archivo.ttf", 30, "Medium"), PLATA)

    elif len(partidos) == 1:
        p = partidos[0]
        centrado(d, W // 2, 52, "HOY JUGAMOS" if hoy else "PRÓXIMO PARTIDO", titulo, ROJO)
        comp = f"{p['competencia']}, {p['jornada'].lower()}"
        fc = fuente("Archivo.ttf", 28, "Medium")
        logo = imagen(logos_ligas.get(p["liga"]))
        lw = 0
        if logo:
            l2 = logo.copy(); l2.thumbnail((90, 34), Image.LANCZOS); lw = l2.width + 12
        tw = d.textlength(comp, font=fc)
        x0 = W / 2 - (tw + lw) / 2
        if logo:
            im.alpha_composite(l2, (int(x0), 112 + (34 - l2.height) // 2))
        d.text((x0 + lw, 113), comp, font=fc, fill=PLATA)
        izq, der = (escudo, p["rival"].get("escudo_grande") or p["rival"].get("escudo")), None
        nombres = ("VULTUR SPORTS", p["rival"]["nombre"].upper())
        if not p["local"]:
            izq = (izq[1], izq[0]); nombres = nombres[::-1]
        pegar(im, imagen(str(izq[0])), (90, 185, 260, 260))
        pegar(im, imagen(str(izq[1])), (850, 185, 260, 260))
        fn = fuente("BigShouldersDisplay.ttf", 40, "Black")
        centrado(d, 220, 470, recortar(d, nombres[0], fn, 330), fn, HUESO)
        centrado(d, 980, 470, recortar(d, nombres[1], fn, 330), fn, HUESO)
        centrado(d, W // 2, 205, p["hora"], fuente("BigShouldersDisplay.ttf", 190, "Black"), HUESO)
        centrado(d, W // 2, 420, p["noche_txt"], fuente("Archivo.ttf", 32, "Medium"), PLATA)
        centrado(d, W // 2, 545, "Hora argentina", fuente("Archivo.ttf", 24, "Regular"), PLATA)

    else:
        pegar(im, imagen(str(escudo)), (70, 60, 110, 110))
        d.text((200, 66), "HOY JUGAMOS" if hoy else "PRÓXIMOS PARTIDOS", font=fuente("BigShouldersDisplay.ttf", 64, "Black"), fill=HUESO)
        d.text((202, 136), partidos[0]["noche_txt"].capitalize() + ", hora argentina", font=fuente("Archivo.ttf", 28, "Medium"), fill=PLATA)
        fh = fuente("BigShouldersDisplay.ttf", 72, "Black")
        fr = fuente("BigShouldersDisplay.ttf", 50, "ExtraBold")
        fs = fuente("Archivo.ttf", 24, "Medium")
        filas = partidos[:4]
        alto = min(120, 390 // len(filas))
        y = 205
        for p in filas:
            d.rectangle((70, y, W - 70, y + alto - 12), fill=(46, 46, 46))
            d.text((96, y + (alto - 12 - 72) / 2 - 4), p["hora"], font=fh, fill=HUESO)
            pegar(im, imagen(logos_ligas.get(p["liga"])), (300, y + 14, 110, alto - 40))
            pegar(im, imagen(p["rival"].get("escudo_archivo") or p["rival"].get("escudo_url")), (430, y + 10, alto - 32, alto - 32))
            d.text((430 + alto - 12, y + 14), recortar(d, "vs " + p["rival"]["nombre"], fr, 560), font=fr, fill=HUESO)
            d.text((432 + alto - 12, y + alto - 50), recortar(d, f"{'Local' if p['local'] else 'Visitante'}, {p['competencia']}, {p['jornada'].lower()}", fs, 560), font=fs, fill=PLATA)
            y += alto

    im.convert("RGB").save(destino, "PNG", optimize=True)
