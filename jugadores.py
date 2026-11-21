"""Une las estadísticas de cada jugador entre ligas y calcula totales y rankings.

Un mismo jugador aparece con nombres apenas distintos en cada liga ("VSP-Ch4cKaL" / "VSP-ch4cKaL").
Se unen automáticamente si coinciden ignorando mayúsculas, espacios y signos. Los casos que no
coinciden solos se resuelven en config/plantel.yaml.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

LIGAS = ("lva", "vpn", "vpug")
NOTA_BASE = 6.5   # nota "neutra" para el ranking ajustado
PESO_BASE = 3     # cuántos partidos "imaginarios" con nota base suma el ajuste
MIN_PJ_NOTA = 3   # partidos mínimos para entrar al ranking de nota


def clave(alias: str) -> str:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", alias or "") if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", sin_acentos.lower())


# Posiciones que suman valla invicta (arquero y defensores), con los códigos de las tres ligas
DEFENSIVAS = {"POR", "PO", "GK", "DFC", "LD", "LI", "LTD", "LTI", "CAD", "CAI"}


def valla_invicta(p: dict, s: dict) -> bool:
    """Valla invicta tal como la publica la liga en el partido (solo VPN la publica por jugador)."""
    return bool(s.get("valla_invicta"))


ARQUERO = {"POR", "PO", "GK"}


def arquero(j: dict) -> int:
    """Partidos jugados de arquero."""
    return sum(1 for x in j["partidos"] if (x["s"].get("posicion") or "") in ARQUERO)


def _vacio():
    return {"pj": 0, "goles": 0, "asistencias": 0, "mvp": 0, "amarillas": 0, "rojas": 0, "vallas": 0, "notas": []}


def _cerrar(s: dict) -> dict:
    notas = s.pop("notas")
    s["nota"] = round(sum(notas) / len(notas), 2) if notas else None
    s["nota_ajustada"] = round((sum(notas) + NOTA_BASE * PESO_BASE) / (len(notas) + PESO_BASE), 2) if notas else None
    s["ga"] = s["goles"] + s["asistencias"]
    return s


def armar(partidos: list, plantel_vpug: list, ajustes: dict) -> dict:
    unir = {clave(k): clave(v) for k, v in (ajustes.get("unir") or {}).items()}
    ocultar = {clave(x) for x in (ajustes.get("ocultar") or [])}
    nombres = {clave(k): v for k, v in (ajustes.get("nombres") or {}).items()}
    ficha_vpug = {clave(j.get("idExterno")): j for j in plantel_vpug}

    jug: dict[str, dict] = {}

    def obtener(k):
        if k not in jug:
            jug[k] = {"id": k, "variantes": Counter(), "por_liga": {l: _vacio() for l in LIGAS},
                      "total": _vacio(), "posiciones": Counter(), "partidos": []}
        return jug[k]

    for p in partidos:
        if not p.get("resultado"):
            continue
        for s in p.get("stats", []):
            if not s.get("alias"):
                continue  # registro de la liga sin jugador asignado
            k = clave(s["alias"])
            k = unir.get(k, k)
            if k in ocultar:
                continue
            j = obtener(k)
            j["variantes"][s["alias"].strip()] += 1
            if s.get("posicion"):
                j["posiciones"][s["posicion"]] += 1
            nota = s.get("rating")
            for acc in (j["total"], j["por_liga"][p["liga"]]):
                acc["pj"] += 1
                acc["goles"] += s.get("goles") or 0
                acc["asistencias"] += s.get("asistencias") or 0
                acc["mvp"] += 1 if s.get("mvp") else 0
                acc["amarillas"] += s.get("amarillas") or 0
                acc["rojas"] += s.get("rojas") or 0
                acc["vallas"] += 1 if valla_invicta(p, s) else 0
                if nota is not None and nota >= 0:
                    acc["notas"].append(nota)
            j["partidos"].append({"p": p, "s": s})

    # Jugadores del plantel de VPUG que todavía no tienen partidos con estadísticas
    for k, f in ficha_vpug.items():
        k = unir.get(k, k)
        if k not in ocultar:
            obtener(k)["variantes"][(f.get("idExterno") or "").strip()] += 0

    salida = []
    for k, j in jug.items():
        f = ficha_vpug.get(k) or {}
        alias = (f.get("idExterno") or "").strip() or j["variantes"].most_common(1)[0][0]
        salida.append({
            "id": k,
            "alias": nombres.get(k, alias),
            "nombre_real": (f.get("nombreCompleto") or "").strip(),
            "dorsal": f.get("dorsal"),
            # Posición: la que más jugó en sus últimos 20 partidos; si no tiene, la del plantel de VPUG
            "posicion": _posicion_reciente(j["partidos"]) or f.get("posicion"),
            "posiciones": _posiciones(j["partidos"]),
            "rol": "DT" if f.get("esDt") else ("Sub DT" if f.get("esSubDt") else None),
            "en_plantel_vpug": bool(f),
            "total": _cerrar(j["total"]),
            "por_liga": {l: _cerrar(v) for l, v in j["por_liga"].items()},
            "partidos": sorted(j["partidos"], key=lambda x: x["p"]["fecha_utc"], reverse=True),
            "pagina": f"jugador-{k}.html",
        })
    return {"jugadores": salida}


# Códigos unificados entre ligas (VPN usa PO/LTD/LTI) y su nombre para mostrar
ALIAS_POS = {"PO": "POR", "GK": "POR", "LTD": "LD", "LTI": "LI", "CAD": "LD", "CAI": "LI"}
NOMBRE_POS = {"POR": "Arquero", "DFC": "Defensor central", "LD": "Lateral derecho", "LI": "Lateral izquierdo",
              "MCD": "Mediocampista defensivo", "MC": "Mediocampista central", "MD": "Volante derecho",
              "MI": "Volante izquierdo", "MCO": "Mediocampista ofensivo", "DC": "Delantero centro",
              "DD": "Delantero derecho", "DI": "Delantero izquierdo", "ED": "Extremo derecho",
              "EI": "Extremo izquierdo", "SD": "Segundo delantero"}


def _posiciones(partidos: list) -> list:
    """Puestos jugados y cuántas veces, de más a menos."""
    c = Counter(ALIAS_POS.get(x["s"]["posicion"], x["s"]["posicion"]) for x in partidos if x["s"].get("posicion"))
    total = sum(c.values())
    return [{"pos": p, "nombre": NOMBRE_POS.get(p, p), "pj": n, "pct": round(100 * n / total)} for p, n in c.most_common()]


def _posicion_reciente(partidos: list, n: int = 20) -> str | None:
    recientes = sorted(partidos, key=lambda x: x["p"]["fecha_utc"])[-n:]
    c = Counter(x["s"].get("posicion") for x in recientes if x["s"].get("posicion"))
    return c.most_common(1)[0][0] if c else None


def rankings(jugadores: list, ambito: str) -> dict:
    def st(j):
        return j["total"] if ambito == "todas" else j["por_liga"][ambito]
    con_pj = [j for j in jugadores if st(j)["pj"] > 0]

    def top(campo, minimo=1):
        # Vallas invictas: en empate va primero el que más jugó de arquero
        orden = sorted((j for j in con_pj if (st(j)[campo] or 0) >= minimo),
                       key=lambda j: (-(st(j)[campo] or 0), -(arquero(j) if campo == "vallas" else 0), st(j)["pj"]))
        return orden[:1]
    nota = sorted((j for j in con_pj if st(j)["nota_ajustada"] and st(j)["pj"] >= MIN_PJ_NOTA),
                  key=lambda j: (-st(j)["nota"], -st(j)["pj"]))[:1]
    return {"goles": top("goles"), "asistencias": top("asistencias"), "mvp": top("mvp"), "nota": nota,
            "vallas": top("vallas"), "pj": top("pj")}
