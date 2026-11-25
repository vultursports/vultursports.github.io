"""EA SPORTS FC Clubs (proclubs.ea.com): datos extra de los partidos de nuestras competencias.

Solo sirven los partidos que coinciden con uno de VPN, LVA o VPUG (en EA figuran como amistosos
entre clubes). El resto (Division Rivals, amistosos sueltos) se descarta.
Lo que publica cada liga manda siempre; EA solo completa lo que la liga no publica.

EA rechaza los pedidos simples y el navegador oculto, por eso se abre un Chromium visible
(en GitHub Actions corre dentro de una pantalla virtual, xvfb). EA guarda solo los últimos 10
partidos: cada pasada suma los nuevos a datos/ea_partidos.json.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from .base import ErrorConector

def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _jugador(x: dict) -> dict:
    return {
        "alias": (x.get("playername") or "").strip(), "pos": x.get("pos"),
        "goles": _i(x.get("goals")), "asistencias": _i(x.get("assists")),
        "tiros": _i(x.get("shots")), "pases": _i(x.get("passesmade")), "pases_int": _i(x.get("passattempts")),
        "entradas": _i(x.get("tacklesmade")), "entradas_int": _i(x.get("tackleattempts")),
        "atajadas": _i(x.get("saves")), "rojas": _i(x.get("redcards")), "mom": x.get("mom") == "1",
        "nota": float(x["rating"]) if x.get("rating") not in (None, "") else None,
        "segundos": _i(x.get("secondsPlayed")),
        "atajadas_tipo": {k: _i(x.get(c)) for k, c in (("reflejo", "reflexSaves"), ("estirada", "ballDiveSaves"),
                          ("punos", "punchSaves"), ("desvio", "parrySaves"), ("centros", "crossSaves"),
                          ("ubicacion", "goodDirectionSaves")) if _i(x.get(c))},
        # Eventos codificados del partido: se guardan para estudiarlos más adelante
        "eventos": [x.get(f"match_event_aggregate_{n}") or "" for n in range(4)],
    }


def _equipo(jug: list) -> dict:
    s = lambda k: sum(j[k] for j in jug)
    notas = [j["nota"] for j in jug if j["nota"] is not None]
    return {"tiros": s("tiros"), "pases": s("pases"), "pases_int": s("pases_int"), "entradas": s("entradas"),
            "entradas_int": s("entradas_int"), "atajadas": s("atajadas"),
            "nota": round(sum(notas) / len(notas), 2) if notas else None}


def _max_recibidos(m: dict, cid: str) -> int:
    return max((_i(x.get("goalsconceded")) for x in ((m.get("players") or {}).get(cid) or {}).values()), default=0)


def normalizar(m: dict, club_id: str) -> dict | None:
    clubs = m.get("clubs") or {}
    if club_id not in clubs or len(clubs) != 2:
        return None
    rid = next(k for k in clubs if k != club_id)
    nos, riv = clubs[club_id], clubs[rid]
    jn = [_jugador(x) for x in (m.get("players") or {}).get(club_id, {}).values()]
    jr = [_jugador(x) for x in (m.get("players") or {}).get(rid, {}).values()]
    return {
        "id": str(m["matchId"]),
        "fecha_utc": datetime.fromtimestamp(int(m["timestamp"]), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gf": _i(nos.get("goals")), "gc": _i(riv.get("goals")),
        # Goles que hicieron los jugadores: EA pone 3-0 técnico si alguien abandona, aunque nadie haya
        # hecho goles; esto muestra lo que pasó en la cancha (sin contar goles en contra)
        "goles_jugadores": [sum(j["goles"] for j in jn), sum(j["goles"] for j in jr)],
        # Goles según lo que recibió cada equipo (el máximo de "goalsconceded" de sus jugadores): cuenta
        # también los goles de un jugador al que sacaron antes del final (EA vacía su registro) y los en contra
        "goles_recibidos": [_max_recibidos(m, rid), _max_recibidos(m, club_id)],
        "minutos": round(max((j["segundos"] for j in jn + jr), default=0) / 60),
        "abandono": nos.get("winnerByDnf") == "1" or riv.get("winnerByDnf") == "1",
        "rival": {"nombre": ((riv.get("details") or {}).get("name") or "").strip(), "ea_id": rid},
        "jugadores": jn,
        "equipo": {"nosotros": _equipo(jn), "rival": _equipo(jr)} if jn and jr else None,
    }



def bajar(club_id: str, plataforma: str) -> list:
    from playwright.sync_api import sync_playwright
    base = "https://proclubs.ea.com/api/fc/"
    urls = {"partidos": f"{base}clubs/matches?platform={plataforma}&clubIds={club_id}&matchType=friendlyMatch&maxResultCount=10"}
    out = {}
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=False, args=["--window-position=-2400,-2400"])
        try:
            pg = nav.new_page()
            for k, u in urls.items():
                r = pg.goto(u, wait_until="load", timeout=45000)
                if not r or r.status != 200:
                    raise ErrorConector(f"EA {k}: HTTP {r.status if r else '?'}")
                try:
                    out[k] = json.loads(pg.inner_text("body"))
                except json.JSONDecodeError:
                    raise ErrorConector(f"EA {k}: la respuesta no es JSON")
                pg.wait_for_timeout(1500)
        finally:
            nav.close()
    return out["partidos"]


def sincronizar(cfg: dict, previos: dict) -> dict:
    club_id = str(cfg["club_id"])
    crudos = bajar(club_id, cfg.get("plataforma", "common-gen5"))
    partidos = dict(previos)
    for m in crudos:
        n = normalizar(m, club_id)
        if n:
            partidos[n["id"]] = n
    return partidos


# ---------- Unión con los partidos de las ligas ----------

def _clave(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]", "", s)


_RELLENO = {"fc", "cf", "club", "esports", "esport", "e", "sports", "sport", "cd", "ca", "cs", "the", "de", "la", "el"}


def parecido(a: str, b: str) -> float:
    """0 a 1: qué tanto se parecen dos nombres de equipo (EA y la liga los escriben distinto)."""
    ka, kb = _clave(a), _clave(b)
    if not ka or not kb:
        return 0.0
    if ka == kb:
        return 1.0
    ta = {t for t in re.findall(r"[a-z0-9]+", _clave_espacios(a)) if t not in _RELLENO}
    tb = {t for t in re.findall(r"[a-z0-9]+", _clave_espacios(b)) if t not in _RELLENO}
    if ta and tb and (ta <= tb or tb <= ta):
        return 0.9
    return SequenceMatcher(None, ka, kb).ratio()


def _clave_espacios(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower()


# El partido de EA queda registrado al terminar: entre 5 minutos antes y 75 después del horario de la liga
ANTES, DESPUES = timedelta(minutes=5), timedelta(minutes=75)
MIN_MINUTOS = 20   # intentos cortados (se desconectó alguien y se volvió a jugar) no cuentan


def datos_completos(m: dict) -> bool:
    """Si alguien abandona, a veces EA no guarda las estadísticas de nuestro lado (todos con 0 pases
    en 90 minutos). Más de la mitad de los jugadores sin un solo pase intentado = datos rotos."""
    jug = [j for j in m.get("jugadores") or [] if j.get("segundos", 0) >= MIN_MINUTOS * 60]
    return bool(jug) and sum(1 for j in jug if not j["pases_int"]) <= len(jug) / 2


def marcadores(m: dict) -> set:
    """Marcadores posibles de un partido de EA: el que registra EA y el de los goles de los jugadores."""
    s = {(m["gf"], m["gc"])}
    if m.get("goles_jugadores"):
        s.add(tuple(m["goles_jugadores"]))
    return s


def marcador_seguro(m: dict) -> tuple | None:
    """El marcador solo es confiable si EA y los goles de los jugadores dicen lo mismo, o si lo
    confirman los goles que recibió cada equipo.

    Lo segundo cubre los goles que no quedan en ningún jugador: los de uno al que sacaron del lobby
    antes de que cierre el partido (EA deja su registro vacío) y los goles en contra. Contra
    DeportivoFumeta (2026-11-25) EA dio 3-0 con 0 goles de jugadores porque expulsaron al autor de
    los 3 al final, pero los rivales tenían 3 recibidos. Los 3-0 técnicos falsos (AllBoysCantera,
    Marpla FC) tienen 0 recibidos de los dos lados y se descartan."""
    s = marcadores(m)
    if len(s) == 1:
        return next(iter(s))
    if m.get("goles_recibidos") and tuple(m["goles_recibidos"]) == (m["gf"], m["gc"]):
        return m["gf"], m["gc"]
    return None
MIN_PARECIDO_SIN_RESULTADO = 0.6


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def unir(partidos: list, ea_partidos: dict, ahora: datetime | None = None) -> dict:
    """Devuelve {id del partido de la liga: partido de EA}. El resultado oficial es SIEMPRE el de la
    competencia: EA solo aporta las estadísticas.

    - Se buscan los partidos de EA dentro del horario (de 5 minutos antes a 75 después) y se agrupan
      por rival. Si contra el mismo rival hubo más de un intento seguido (se salieron para reiniciar),
      vale el último completo: el de menos de 20 minutos no cuenta.
    - Con resultado de la liga: se une si coincide el marcador (el de EA o el de los goles de los
      jugadores, porque si alguien abandona EA pone 3-0 técnico). Si no coincide pero hubo reinicio
      contra ese rival, se une igual el último intento completo.
      Un solo partido con otro marcador (por ejemplo, una sanción de la liga) no se une.
    - Sin resultado (la liga no lo cargó todavía): nombre parecido y marcador confiable. Sirve para
      mostrar un resultado provisorio.
    - Los W.O. no se jugaron: no se unen. Cada partido de EA se usa una sola vez.
    """
    ahora = ahora or datetime.now(timezone.utc)
    pares = []
    for p in partidos:
        if p.get("estado") == "wo" or p.get("manual"):
            continue
        f = _dt(p["fecha_utc"])
        if f > ahora:
            continue
        grupos = {}
        for m in ea_partidos.values():
            if -ANTES <= _dt(m["fecha_utc"]) - f <= DESPUES:
                grupos.setdefault(m["rival"].get("ea_id") or _clave(m["rival"]["nombre"]), []).append(m)
        for intentos in grupos.values():
            completos = sorted((m for m in intentos if m.get("minutos") is None or m["minutos"] >= MIN_MINUTOS),
                               key=lambda m: m["fecha_utc"])
            if not completos:
                continue
            m = completos[-1]   # si hubo reinicio, el último intento completo es el bueno
            sim = max(parecido(p["rival"]["nombre"], x["rival"]["nombre"]) for x in intentos)
            if p.get("gf") is not None:
                coincide = (p["gf"], p.get("gc")) in marcadores(m)
                reinicio = len(intentos) > 1 and (sim >= MIN_PARECIDO_SIN_RESULTADO
                                                  or any((p["gf"], p.get("gc")) in marcadores(x) for x in intentos))
                if not (coincide or reinicio):
                    continue
            elif sim < MIN_PARECIDO_SIN_RESULTADO or not marcador_seguro(m):
                continue
            d = _dt(m["fecha_utc"]) - f
            pares.append((-sim, abs(d - timedelta(minutes=20)), p["id"], m["id"]))
    usados_p, usados_m, res = set(), set(), {}
    for _, _, pid, mid in sorted(pares):
        if pid in usados_p or mid in usados_m:
            continue
        usados_p.add(pid); usados_m.add(mid)
        res[pid] = ea_partidos[mid]
    return res
