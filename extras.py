"""Cálculos extra del sitio: jugador de la noche, hitos, récords de partido,
control cruzado con EA.

Regla del club: donde se muestra algo "actual", nunca información vieja. Lo actual se calcula con
una ventana reciente y desaparece solo si no hay datos nuevos; lo de partidos terminados queda siempre.
"""
from __future__ import annotations

from datetime import timedelta

DIAS_CONTROL = 30
EA_RECIENTES = 5          # EA está "vigente" si alguno de los últimos 5 partidos tiene sus datos

HITOS = {
    "pj": ([50, 100, 150, 200, 250, 300, 400, 500], "partidos", "partido"),
    "goles": ([10, 25, 50, 75, 100, 150, 200, 250, 300], "goles", "gol"),
    "asistencias": ([10, 25, 50, 75, 100, 150, 200], "asistencias", "asistencia"),
    "mvp": ([5, 10, 25, 50, 75, 100], "veces MVP", "vez MVP"),
}


def jugados(partidos: list) -> list:
    """Partidos jugados de verdad (con resultado y sin W.O.), del más reciente al más viejo."""
    return sorted((p for p in partidos if p.get("resultado") and not p.get("wo")), key=lambda p: p["fecha_utc"], reverse=True)


def ea_vigente(partidos: list) -> bool:
    return any(p.get("ea") for p in jugados(partidos)[:EA_RECIENTES])


def hitos(j: dict) -> list:
    """Hitos del jugador (50/100 partidos, 25/50 goles...) con el partido en que los alcanzó."""
    cuenta = {k: 0 for k in HITOS}
    out = []
    for x in sorted((x for x in j["partidos"] if x["p"].get("resultado")), key=lambda x: x["p"]["fecha_utc"]):
        s = x["s"]
        suma = {"pj": 1, "goles": s.get("goles") or 0, "asistencias": s.get("asistencias") or 0, "mvp": 1 if s.get("mvp") else 0}
        for k, (marcas, plural, _) in HITOS.items():
            antes = cuenta[k]
            cuenta[k] += suma[k]
            for m in marcas:
                if antes < m <= cuenta[k]:
                    out.append({"tipo": k, "n": m, "txt": f"{m} {plural}", "p": x["p"]})
    return sorted(out, key=lambda h: h["p"]["fecha_utc"], reverse=True)



def records_partido(partidos: list, id_de) -> list:
    """Récords individuales en un solo partido. En empate queda el primero que lo logró."""
    def mejor(titulo, unidad, valor, minimo=1, fuente="liga"):
        top = None
        for p in sorted(jugados(partidos), key=lambda p: p["fecha_utc"]):
            for s in p.get("stats") or []:
                if not s.get("alias"):
                    continue
                v = valor(s)
                if v is not None and v >= minimo and (top is None or v > top["valor"]):
                    top = {"titulo": titulo, "unidad": unidad, "valor": v, "id": id_de(s["alias"]), "alias": s["alias"], "p": p, "fuente": fuente}
        return top
    ea = lambda campo: (lambda s: s["ea"][campo] if s.get("ea") else None)
    perfecto = lambda s: s["ea"]["pases"] if s.get("ea") and s["ea"]["pases_int"] >= 10 and s["ea"]["pases"] == s["ea"]["pases_int"] else None
    lista = [
        mejor("Más goles en un partido", "goles", lambda s: s.get("goles") or 0, 2),
        mejor("Más asistencias en un partido", "asistencias", lambda s: s.get("asistencias") or 0, 2),
        mejor("Mejor nota en un partido", "de nota", lambda s: s.get("rating") if (s.get("rating") or -1) >= 0 else None),
        mejor("Más tiros en un partido", "tiros", ea("tiros"), 3, "ea"),
        mejor("Más entradas ganadas en un partido", "entradas", ea("entradas"), 3, "ea"),
        mejor("Más atajadas en un partido", "atajadas", ea("atajadas"), 3, "ea"),
        mejor("Pases perfectos", "pases sin errar", perfecto, 10, "ea"),
    ]
    return [r for r in lista if r]


def control_cruzado(partidos: list, hoy_noche) -> list:
    """Partidos recientes donde los goles o asistencias de la liga no coinciden con los de EA.
    No se corrige nada: lo de la liga manda; solo se avisa en la página de Estado."""
    desde = hoy_noche - timedelta(days=DIAS_CONTROL)
    out = []
    for p in jugados(partidos):
        if not p.get("ea") or p["noche"] < desde:
            continue
        for s in p.get("stats") or []:
            e = s.get("ea")
            if not e:
                continue
            dif = []
            if (s.get("goles") or 0) != e["goles"]:
                dif.append(f"goles: liga {s.get('goles') or 0}, EA {e['goles']}")
            if (s.get("asistencias") or 0) != e["asistencias"]:
                dif.append(f"asistencias: liga {s.get('asistencias') or 0}, EA {e['asistencias']}")
            if dif:
                out.append({"p": p, "alias": s["alias"], "dif": "; ".join(dif)})
    return out
