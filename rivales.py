"""Historial contra cada rival, sumando todas las ligas.

Los rivales se unen:
1. por nombre, ignorando mayúsculas, espacios y signos ("AllBoysCantera" y "All Boys Cantera");
2. por escudo: si dos nombres distintos usan el mismo escudo, son el mismo club
   ("Claypole eSports" en la LVA y "Claypole eSp" en VPUG);
3. a mano, en config/rivales.yaml.
"""
from __future__ import annotations

import io
import itertools
import json
import re
from collections import Counter
from pathlib import Path

import httpx
from PIL import Image

from jugadores import clave

UMBRAL_MISMO_NOMBRE = 160  # escudos parecidos (rediseñados, con relieve) cuando el nombre base coincide
SEGUNDOS_EQUIPOS = re.compile(r"\b(reserva|cantera|academia|juvenil|sub ?\d+|b|ii|2)\b", re.I)
SUFIJOS = re.compile(r"\b(e-?sports?|esp|esport|fc|cf|club|team)\b", re.I)


def nombre_base(nombre: str) -> str:
    """'San Miguel eSports' y 'San Miguel eSp' -> 'sanmiguel'."""
    return clave(SUFIJOS.sub(" ", nombre))


def _puede_unir(nombres_a: set, nombres_b: set, dist: int) -> bool:
    # Un segundo equipo (reserva, cantera, "2") nunca se une con otro que no lo sea
    seg_a = any(SEGUNDOS_EQUIPOS.search(n) for n in nombres_a)
    seg_b = any(SEGUNDOS_EQUIPOS.search(n) for n in nombres_b)
    if seg_a != seg_b:
        return False
    ba, bb = {nombre_base(n) for n in nombres_a}, {nombre_base(n) for n in nombres_b}
    mismo_nombre = any(x and y and (x == y or x.startswith(y) or y.startswith(x)) for x in ba for y in bb)
    # Solo se unen si el nombre tiene relación; un escudo igual con nombres distintos queda separado
    # (ante la duda, separados; si es el mismo club renombrado, se une en config/rivales.yaml).
    return mismo_nombre and dist <= UMBRAL_MISMO_NOMBRE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


def _huella(im: Image.Image, n: int = 16) -> str:
    """Huella del dibujo del escudo (dHash 16x16), sin importar tamaño ni márgenes."""
    im = im.convert("RGBA")
    caja = im.getbbox()
    im = im.crop(caja) if caja else im
    fondo = Image.new("RGBA", im.size, (128, 128, 128, 255))
    fondo.alpha_composite(im)
    g = fondo.convert("L").resize((n + 1, n), Image.LANCZOS)
    px = g.load()
    return "".join("1" if px[c, r] > px[c + 1, r] else "0" for r in range(n) for c in range(n))


def huellas(urls: set[str], cache_archivo: Path) -> dict[str, str]:
    cache = json.loads(cache_archivo.read_text(encoding="utf-8")) if cache_archivo.exists() else {}
    nuevas = [u for u in urls if u not in cache]
    if nuevas:
        with httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as c:
            for u in nuevas:
                try:
                    cache[u] = _huella(Image.open(io.BytesIO(c.get(u).content)))
                except Exception:
                    pass  # escudo caído: se reintenta en la próxima actualización
        cache_archivo.write_text(json.dumps(cache, indent=0), encoding="utf-8")
    return cache


def unir_por_escudo(partidos: list, unir: dict, cache_archivo: Path, separar: set | None = None) -> dict[str, str]:
    """Devuelve uniones nuevas {clave_rival: clave_principal} para el mismo club con distinto nombre."""
    escudo_de: dict[str, str] = {}
    nombres: dict[str, set] = {}
    separar = separar or set()
    for p in partidos:
        k = clave(p["rival"]["nombre"]); k = unir.get(k, k)
        nombres.setdefault(k, set()).add(p["rival"]["nombre"].strip())
        url = p["rival"].get("escudo_url") or p["rival"].get("escudo")
        if url and url.startswith("http"):
            escudo_de.setdefault(k, url.replace("_thumb", ""))
    h = huellas(set(escudo_de.values()), cache_archivo)
    claves = sorted(k for k in escudo_de if escudo_de[k] in h)
    nuevas: dict[str, str] = {}
    for a, b in itertools.combinations(claves, 2):
        ha, hb = h[escudo_de[a]], h[escudo_de[b]]
        if frozenset((a, b)) in separar:
            continue
        if _puede_unir(nombres[a], nombres[b], sum(x != y for x, y in zip(ha, hb))):
            principal = nuevas.get(a, a)
            nuevas[b] = principal
    return nuevas


def armar(partidos: list, ajustes: dict, cache_escudos: Path | None = None) -> dict[str, dict]:
    unir = {clave(k): clave(v) for k, v in (ajustes.get("unir") or {}).items()}
    separar = {frozenset((clave(a), clave(b))) for a, b in (ajustes.get("separar") or [])}
    por_escudo = unir_por_escudo(partidos, unir, cache_escudos, separar) if cache_escudos else {}
    for k, v in por_escudo.items():
        unir.setdefault(k, unir.get(v, v))
    rivales: dict[str, dict] = {}
    for p in partidos:
        k = clave(p["rival"]["nombre"])
        k = unir.get(k, k)
        r = rivales.setdefault(k, {"id": k, "nombres": Counter(), "escudos": [], "partidos": [],
                                   "ligas": set(), "pagina": f"/rival/{k}/"})
        r["nombres"][p["rival"]["nombre"].strip()] += 1
        if p["rival"].get("escudo"):
            r["escudos"].append(p["rival"]["escudo"])
        r["partidos"].append(p)
        r["ligas"].add(p["liga"])
        p["rival_pagina"] = r["pagina"]

    for r in rivales.values():
        r["nombre"] = r["nombres"].most_common(1)[0][0]
        # Preferir el escudo más grande disponible (VPN tiene versión "_thumb")
        esc = [e.replace("_thumb", "") for e in r["escudos"]]
        r["escudo"] = esc[-1] if esc else None
        jugados = [p for p in r["partidos"] if p.get("resultado")]
        r["jugados"] = sorted(jugados, key=lambda p: p["fecha_utc"], reverse=True)
        r["proximos"] = sorted((p for p in r["partidos"] if not p.get("resultado")), key=lambda p: p["fecha_utc"])
        r["g"] = sum(1 for p in jugados if p["resultado"] == "g")
        r["e"] = sum(1 for p in jugados if p["resultado"] == "e")
        r["p"] = sum(1 for p in jugados if p["resultado"] == "p")
        r["gf"] = sum(p["gf"] or 0 for p in jugados)
        r["gc"] = sum(p["gc"] or 0 for p in jugados)
        r["pj"] = len(jugados)
        r["unido_por_escudo"] = len(r["nombres"]) > 1 and any(clave(n) in por_escudo for n in r["nombres"])
    return rivales
