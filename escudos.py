"""Copia local y prolija de los escudos de los rivales.

Cada liga sube los escudos como quiere: algunos con mucho margen vacío, otros con fondo blanco o
negro. Acá se recortan al dibujo, se centran en un cuadrado de 160 px y se guardan en
datos/escudos/ (se procesan una sola vez). La web usa estas copias.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import httpx
from PIL import Image, ImageChops

TAM = 160
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


def _recortar(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    alfa = im.getchannel("A")
    if alfa.getextrema()[0] < 250:  # tiene transparencia: recortar a lo visible
        caja = alfa.point(lambda v: 255 if v > 20 else 0).getbbox()
    else:  # fondo liso (blanco/negro): recortar lo que difiere del color de la esquina
        fondo = Image.new("RGBA", im.size, im.getpixel((0, 0)))
        caja = ImageChops.difference(im, fondo).convert("L").point(lambda v: 255 if v > 30 else 0).getbbox()
    return im.crop(caja) if caja else im


def _cuadrado(im: Image.Image) -> Image.Image:
    escala = min(TAM / im.width, TAM / im.height)
    im = im.resize((max(1, round(im.width * escala)), max(1, round(im.height * escala))), Image.LANCZOS)
    lienzo = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
    lienzo.alpha_composite(im, ((TAM - im.width) // 2, (TAM - im.height) // 2))
    return lienzo


class Escudos:
    def __init__(self, carpeta: Path):
        self.carpeta = carpeta
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.indice_f = carpeta / "indice.json"
        self.indice = json.loads(self.indice_f.read_text(encoding="utf-8")) if self.indice_f.exists() else {}
        self.cliente = None

    def local(self, url: str | None) -> str | None:
        """Devuelve el nombre del archivo local del escudo (o la URL original si no se pudo)."""
        if not url:
            return None
        url = url.replace("_thumb", "")
        if url in self.indice and (self.carpeta / self.indice[url]).exists():
            return self.indice[url]
        nombre = hashlib.sha1(url.encode()).hexdigest()[:16] + ".webp"
        try:
            self.cliente = self.cliente or httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
            r = self.cliente.get(url)
            r.raise_for_status()
            _cuadrado(_recortar(Image.open(io.BytesIO(r.content)))).save(self.carpeta / nombre, "WEBP", quality=88, method=6)
        except Exception:
            return None
        self.indice[url] = nombre
        return nombre

    def guardar(self):
        self.indice_f.write_text(json.dumps(self.indice, indent=0, ensure_ascii=False), encoding="utf-8")
        if self.cliente:
            self.cliente.close()
