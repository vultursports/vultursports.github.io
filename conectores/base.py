"""Utilidades comunes de los conectores.

Cada conector lee SOLO datos públicos (lo que ve cualquier visitante de la web de la liga),
pide despacio y se identifica con un User-Agent de navegador normal.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "datos" / "raw"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)
PAUSA_SEG = 1.5  # entre pedidos al mismo sitio


class ErrorConector(Exception):
    pass


def cliente() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": UA, "Accept": "application/json, text/html;q=0.9"},
        timeout=httpx.Timeout(90.0, connect=30.0),  # VPUG en Render puede tardar en "despertar"
        follow_redirects=True,
    )


def pedir(c: httpx.Client, url: str, intentos: int = 3, como_json: bool = True):
    ultimo = None
    for i in range(intentos):
        try:
            r = c.get(url)
            if r.status_code == 200:
                time.sleep(PAUSA_SEG)
                return r.json() if como_json else r.text
            ultimo = f"HTTP {r.status_code}"
            if r.status_code == 404:
                break
        except (httpx.HTTPError, json.JSONDecodeError) as e:  # red caída, timeout, JSON roto
            ultimo = repr(e)
        time.sleep(5 * (i + 1))
    raise ErrorConector(f"{url} -> {ultimo}")


def guardar_raw(fuente: str, nombre: str, datos) -> None:
    """Guarda la respuesta cruda (sirve para depurar y re-procesar sin volver a pedir)."""
    d = RAW / fuente
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{nombre}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
