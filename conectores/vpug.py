"""VPUG — Virtual Pro Uruguay Gaming (vpugvirtualprouruguaygaming.com).

Público (sin cuenta): tabla y rankings.
Con cuenta de jugador (variables VPUG_EMAIL y VPUG_PASSWORD): además el fixture completo y el
detalle de cada partido (goles, asistencias, nota, figura). Las credenciales nunca van en el
código: en la PC se leen de .env y en GitHub de los secretos del repo.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from .base import ErrorConector, cliente, guardar_raw, pedir

SITIO = "https://vpugvirtualprouruguaygaming.com"
ZONAS = {"ASCENSO": "ascenso", "DESCENSO": "descenso", "REDUCIDO": "reducido", "PLAYOFF": "playoff"}


def _login(c, api: str) -> str | None:
    email, clave = os.environ.get("VPUG_EMAIL"), os.environ.get("VPUG_PASSWORD")
    if not (email and clave):
        return None
    r = c.post(f"{api}/auth/login", json={"email": email, "password": clave})
    if r.status_code != 200 or "token" not in r.json():
        raise ErrorConector(f"VPUG: no se pudo iniciar sesión (HTTP {r.status_code})")
    return r.json()["token"]


def temporada_y_division(c, api: str, club: int, t_cfg: int, d_cfg: int):
    """Temporada en curso y división donde juega el club, según la API de VPUG. Así una temporada
    nueva o un ascenso/descenso se toman solos. Si no se encuentra, se usa la de config/ligas.yaml.
    Si la temporada encontrada ya no está en curso, la tabla se marca "_terminada": queda como tabla
    final hasta que empiece la siguiente."""
    try:
        temps = sorted(pedir(c, f"{api}/temporadas"), key=lambda x: (x.get("estado") == "EN_CURSO", x["id"]), reverse=True)
        divs = sorted((x["id"] for x in pedir(c, f"{api}/divisiones")), key=lambda i: i != d_cfg)
        for temp in temps[:2]:
            for div in divs:
                tabla = pedir(c, f"{api}/tabla?temporadaId={temp['id']}&divisionId={div}")
                if any((r.get("club") or {}).get("id") == club for r in tabla.get("filas") or []):
                    tabla["_terminada"] = bool(temp.get("estado")) and temp.get("estado") != "EN_CURSO"
                    return temp["id"], div, tabla
    except (ErrorConector, KeyError, TypeError) as e:
        print("  aviso VPUG temporada:", e)
    return t_cfg, d_cfg, pedir(c, f"{api}/tabla?temporadaId={t_cfg}&divisionId={d_cfg}")


def sincronizar(cfg: dict, cfg_club: dict, partidos_previos: dict) -> dict:
    api = cfg["api_base"].rstrip("/")
    club = cfg["club_id"]
    partidos, plantel = [], []
    with cliente() as c:
        t, d, tabla = temporada_y_division(c, api, club, cfg["temporada_id"], cfg["division_id"])
        comp_id = f"vpug-{t}-{d}"
        guardar_raw("vpug", f"tabla_{t}_{d}", tabla)
        rank = pedir(c, f"{api}/estadisticas/rankings?temporadaId={t}&divisionId={d}")
        guardar_raw("vpug", f"rankings_{t}_{d}", rank)
        nombre = f"{tabla['division']['nombre']} División"

        token = _login(c, api)
        if token:
            c.headers["Authorization"] = f"Bearer {token}"
            info = pedir(c, f"{api}/clubes/{club}")
            plantel = [{k: j.get(k) for k in ("idExterno", "nombreCompleto", "dorsal", "posicion", "esDt", "esSubDt", "pais")}
                       for j in [info.get("dt"), info.get("subDt"), *(info.get("plantel") or [])] if j]
            fixture = pedir(c, f"{api}/partidos?temporadaId={t}&divisionId={d}")
            mios = [p for j in fixture["jornadas"] for p in j["partidos"]
                    if club in (p["local"]["id"], p["visitante"]["id"])]
            # Partidos sin resultado de cada equipo. Un equipo dado de baja ya no tiene ninguno (VPUG le
            # carga todos los que faltan 1-0 para el rival) mientras nosotros todavía tenemos.
            pendientes: dict = {}
            for j in fixture["jornadas"]:
                for x in j["partidos"]:
                    for eq in ((x.get("local") or {}).get("id"), (x.get("visitante") or {}).get("id")):
                        pendientes[eq] = pendientes.get(eq, 0) + (0 if x.get("jugado") else 1)
            ahora = datetime.now(timezone.utc)
            for m in mios:
                local = m["local"]["id"] == club
                rival = m["visitante"] if local else m["local"]
                jugado = bool(m.get("jugado"))
                pid = f"vpug-{m['id']}"
                gl, gv = m.get("golesLocal"), m.get("golesVisitante")
                p = {
                    "id": pid,
                    "liga": "vpug",
                    "competencia_id": comp_id,
                    "competencia": nombre,
                    "jornada": f"Fecha {m['jornada']}" if m.get("fase") == "LIGA" else f"{m.get('fase', '').title()}",
                    "fecha_utc": m["fechaHora"].replace(".000Z", "Z"),
                    "local": local,
                    "rival": {"nombre": rival["nombre"].strip(), "escudo": rival.get("escudo")},
                    "gf": (gl if local else gv) if jugado else None,
                    "gc": (gv if local else gl) if jugado else None,
                    "estado": "finalizado" if jugado else ("aplazado" if m.get("aplazado") else "programado"),
                    "url_origen": f"{SITIO}/partidos/{m['id']}",
                    "temporada": {"clave": comp_id, "nombre": f"{nombre} {fixture['temporada']['nombre'].replace('·', '').replace('  ', ' ').replace('Temporada ', 'T')}"},
                    "stats": [],
                }
                previo = partidos_previos.get(pid) or {}
                fecha = datetime.fromisoformat(p["fecha_utc"].replace("Z", "+00:00"))
                # W.O.: VPUG no los marca; los carga como un partido jugado 1-0. Se reconocen porque el
                # resultado aparece antes de la fecha (equipo dado de baja), o porque el partido no tiene
                # ningún dato y el rival ya no tiene partidos pendientes mientras nosotros sí.
                rival_de_baja = pendientes.get(rival["id"]) == 0 and pendientes.get(club, 0) > 0
                if jugado and (fecha > ahora or (previo.get("estado") == "wo" and ahora - fecha > timedelta(days=14))):
                    p["estado"], p["equipo_stats"] = "wo", None
                    partidos.append(p)
                    continue
                # VPUG a veces carga primero solo a la figura y después al resto: si el partido es de la
                # última semana y tiene menos de 11 jugadores (o sin datos de EA), se vuelve a pedir.
                reciente = ahora - fecha < timedelta(days=7)
                incompleto = previo and (len(previo.get("stats") or []) < 11 or not previo.get("equipo_stats"))
                if jugado and previo and previo.get("stats") and previo.get("gf") == p["gf"] and "equipo_stats" in previo \
                        and not (reciente and incompleto):
                    p["stats"], p["equipo_stats"] = previo["stats"], previo["equipo_stats"]
                elif jugado:
                    try:
                        det = pedir(c, f"{api}/partidos/{m['id']}")
                        sin_datos = not det.get("figura") and not det.get("ea") and not any(
                            (det.get(k) or {}).get("jugadores") for k in ("local", "visitante"))
                        if sin_datos and (rival_de_baja or previo.get("estado") == "wo"):
                            p["estado"], p["equipo_stats"] = "wo", None
                            partidos.append(p)
                            continue
                        figura = (det.get("figura") or {}).get("id")
                        lado = det["local"] if local else det["visitante"]
                        p["stats"] = [_stat(j, figura) for j in lado.get("jugadores", [])]
                        ea = det.get("ea") or {}
                        conv = lambda e: e and {"tiros": e.get("tiros"), "pases": e.get("pases"), "pases_int": e.get("pasesIntentados"),
                                                "entradas": e.get("entradas"), "entradas_int": e.get("entradasIntentadas"),
                                                "atajadas": e.get("atajadas"), "nota": None}
                        nos, riv = (ea.get("local"), ea.get("visitante")) if local else (ea.get("visitante"), ea.get("local"))
                        p["equipo_stats"] = {"nosotros": conv(nos), "rival": conv(riv)} if (nos or riv) else None
                    except ErrorConector as e:
                        print("  aviso VPUG detalle:", e)
                        if previo.get("estado") == "wo":
                            p["estado"], p["equipo_stats"] = "wo", None
                partidos.append(p)
        else:
            print("  VPUG sin cuenta: solo tabla y rankings (definir VPUG_EMAIL y VPUG_PASSWORD)")

    fmt = tabla.get("formato") or {}
    filas = [{
        "pos": r["posicion"],
        "equipo": r["club"]["nombre"],
        "escudo": r["club"].get("escudo"),
        "pj": r["pj"], "g": r["g"], "e": r["e"], "p": r["p"],
        "gf": r["gf"], "gc": r["gc"], "dg": r["dg"], "pts": r["pts"],
        "zona": ZONAS.get(r.get("zona") or "", None),
        "es_vultur": r["club"]["id"] == club,
    } for r in tabla["filas"]]

    def nuestros(lista):
        return [{"alias": x["jugador"].strip(), "valor": x["valor"], "partidos": x["partidos"]}
                for x in lista if x["club"]["id"] == club]

    destacados = [
        {"liga": "vpug", "competencia": nombre, "stat": stat, "pos": n + 1, "alias": x["jugador"].strip(),
         "valor": x["valor"], "url_origen": f"{SITIO}/liga/estadisticas"}
        for lista, stat in ((rank.get("goleadores", []), "goles"), (rank.get("asistidores", []), "asistencias"))
        for n, x in enumerate(lista[:5]) if x["club"]["id"] == club
    ]
    # Partidos de temporadas anteriores: la API solo devuelve los de la temporada actual; se conservan
    if partidos:
        partidos += [p for p in partidos_previos.values() if p.get("competencia_id") != comp_id]
    return {
        "destacados": destacados,
        "partidos": partidos,
        "plantel": plantel,
        "tablas": [{
            **({"terminado": True} if tabla.get("_terminada") else {}),
            "id": comp_id,
            "liga": "vpug",
            "competencia": nombre,
            "temporada": tabla["temporada"]["nombre"],
            "logo": None,
            "url_origen": f"{SITIO}/liga/tabla",
            "jornadas": f"{tabla.get('jornadasJugadas')}/{tabla.get('jornadasTotales')}",
            "formato": {k: fmt.get(k) for k in ("ascensosDirectos", "ascensos", "descensos")},
            "filas": filas,
        }],
        "rankings": {
            "id": comp_id,
            "liga": "vpug",
            "goleadores": nuestros(rank.get("goleadores", [])),
            "asistidores": nuestros(rank.get("asistidores", [])),
            "url_origen": f"{SITIO}/liga/estadisticas",
        },
    }


def _stat(j: dict, figura_id) -> dict:
    return {
        "alias": (j.get("idExterno") or j.get("nombre") or "").strip(),
        "alias_id": str(j.get("id")),
        "nombre": (j.get("nombre") or "").strip(),
        "posicion": j.get("posicion"),
        "goles": j.get("goles") or 0,
        "asistencias": j.get("asistencias") or 0,
        "mvp": j.get("id") == figura_id,
        "rating": j.get("nota"),
        "amarillas": j.get("amarillas") or 0,
        "rojas": j.get("rojas") or 0,
        "valla_invicta": False,
    }
