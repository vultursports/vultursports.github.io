"""VPN — Virtual Pro Network (virtualpronetwork.com).

Lee los mismos JSON públicos que carga la web de VPN al navegar (Next.js /_next/data/...).
Trae: fixture completo de la temporada, tabla de nuestro grupo y estadísticas por jugador
de cada partido jugado.
"""
from __future__ import annotations

import json
import re

from .base import ErrorConector, cliente, guardar_raw, pedir

BASE = "https://virtualpronetwork.com"
EVENTOS = {"1": "goles", "2": "asistencias", "3": "vallas", "7": "vallas_def", "5": "amarillas", "6": "rojas"}


def _build_id(c, comunidad: str, team_slug: str) -> str:
    html = pedir(c, f"{BASE}/{comunidad}/teams/{team_slug}", como_json=False)
    m = re.search(r'"buildId":"([^"]+)"', html)
    if not m:
        raise ErrorConector("VPN: no encontré buildId")
    return m.group(1)


def _data(c, bid: str, ruta: str, params: str):
    return pedir(c, f"{BASE}/_next/data/{bid}/{ruta}.json?{params}")["pageProps"]


def sincronizar(cfg: dict, cfg_club: dict, partidos_previos: dict) -> dict:
    """Devuelve {"partidos": [...], "tablas": [...]} normalizados."""
    com = cfg["comunidad"]
    tid = cfg["team_id"]
    slug = cfg["team_slug"]
    partidos, tablas, sanciones = [], [], []

    with cliente() as c:
        bid = _build_id(c, com, slug)

        for comp in cfg["competencias"]:
            ruta = f"{com}/league/{comp['league_id']}/{comp['league_slug']}/season/{comp['season_id']}/standings"
            params = (f"communitySlug={com}&id={comp['league_id']}&url={comp['league_slug']}"
                      f"&seasonId={comp['season_id']}&tab=standings")
            st = _data(c, bid, ruta, params)
            guardar_raw("vpn", f"standings_{comp['season_id']}", st)

            liga = st["league"]
            grupos = {g["tid"]: g["name"] for g in (st.get("groups") or [])}
            mi_grupo = grupos.get(tid)
            filas = [r for r in st["table"] if not grupos or grupos.get(r["tid"]) == mi_grupo]
            filas.sort(key=lambda r: r["pos"])
            # VPN publica posiciones de la tabla general; el movimiento se calcula dentro del grupo
            orden_ant = sorted((r for r in filas if r.get("prevPos")), key=lambda r: r["prevPos"])
            pos_ant_grupo = {r["tid"]: i + 1 for i, r in enumerate(orden_ant)}
            nombre_comp = liga["name"] + (f" ({mi_grupo.title()})" if mi_grupo else "")
            comp_id = f"vpn-{comp['season_id']}"
            url_tabla = f"{BASE}/{com}/league/{comp['league_id']}/{comp['league_slug']}/season/{comp['season_id']}/standings"

            tablas.append({
                "id": comp_id,
                "liga": "vpn",
                "competencia": nombre_comp,
                "temporada": comp.get("temporada", ""),
                "logo": liga.get("logoBigUrl") or liga.get("logoUrl"),
                "url_origen": url_tabla,
                "filas": [{
                    "pos": i + 1,
                    "equipo": r["team"]["name"],
                    "escudo": r["team"].get("logoSmallUrl") or r["team"].get("logoUrl"),
                    "pj": r["gp"], "g": r["gw"], "e": r["gt"], "p": r["gl"],
                    "gf": r["gf"], "gc": r["gc"], "dg": r["gd"], "pts": r["pts"],
                    "zona": None,
                    "pos_fuente": i + 1, "pos_ant_fuente": pos_ant_grupo.get(r["tid"]),
                    "es_vultur": r["tid"] == tid,
                } for i, r in enumerate(filas)],
            })

            mia = next((r for r in st["table"] if r["tid"] == tid), None)
            if not mia:
                continue
            for m in mia["matches"]:
                local = m["team1"] == tid
                rival = m["awayTeam"] if local else m["homeTeam"]
                jugado = bool(m["published"])
                pid = f"vpn-{m['id']}"
                p = {
                    "id": pid,
                    "liga": "vpn",
                    "competencia_id": comp_id,
                    "competencia": nombre_comp,
                    "jornada": f"Jornada {m['round']}",
                    "fecha_utc": m["date"].replace(".000Z", "Z"),
                    "local": local,
                    "rival": {"nombre": rival["name"], "escudo": rival.get("logoSmallUrl") or rival.get("logoUrl")},
                    "gf": (m["gteam1"] if local else m["gteam2"]) if jugado else None,
                    "gc": (m["gteam2"] if local else m["gteam1"]) if jugado else None,
                    "estado": ("wo" if m.get("forfeit") else "finalizado") if jugado else "programado",
                    "url_origen": f"{BASE}/{com}/matches/{m['id']}",
                    "temporada": {"clave": comp_id, "nombre": f"{liga['name']} {_corto(comp.get('temporada', ''))}".strip()},
                    "stats": [],
                }
                # Detalle por jugador: solo partidos jugados y que todavía no tenemos con stats.
                previo = partidos_previos.get(pid)
                if jugado and previo and previo.get("stats") and previo.get("gf") == p["gf"] and "formacion" in previo:
                    p["stats"], p["equipo_stats"], p["formacion"] = previo["stats"], previo.get("equipo_stats"), previo["formacion"]
                elif jugado:
                    try:
                        rep = _data(c, bid, f"{com}/matches/{m['id']}", f"communitySlug={com}&id={m['id']}")["report"]
                        lado = rep["home"] if rep["home"]["teamId"] == tid else rep["away"]
                        otro = rep["away"] if lado is rep["home"] else rep["home"]
                        p["stats"] = [_stat_jugador(j) for j in lado.get("players", [])]
                        p["equipo_stats"] = _equipo(lado, otro)
                        p["formacion"] = _formacion(lado)
                    except ErrorConector as e:
                        print("  aviso VPN detalle:", e)
                partidos.append(p)

        # Temporadas anteriores (todo el historial disponible en VPN). Las cerradas se bajan una
        # sola vez: si ya tenemos partidos guardados de esa temporada, no se vuelven a pedir.
        actuales = {f"vpn-{x['season_id']}" for x in cfg["competencias"]}
        partidos += _historial(c, bid, com, slug, tid, partidos_previos, actuales)

        # Jugadores no habilitados para los próximos partidos (lo publica VPN en cada partido)
        for p in [x for x in partidos if x["estado"] == "programado"][:3]:
            mid = p["id"].split("-", 1)[1]
            try:
                rep = _data(c, bid, f"{com}/matches/{mid}", f"communitySlug={com}&id={mid}")["report"]
                lado = rep["home"] if rep["home"]["teamId"] == tid else rep["away"]
                for j in lado.get("ineligible") or []:
                    sanciones.append({
                        "liga": "vpn", "competencia": p["competencia"],
                        "jugador": (j.get("name") or j.get("username") or str(j)).strip() if isinstance(j, dict) else str(j),
                        "motivo": (j.get("reason") if isinstance(j, dict) else None) or "No habilitado para este partido",
                        "cumple": f"{p['jornada']} vs {p['rival']['nombre']}", "partido_id": p["id"], "vigente": True,
                    })
            except ErrorConector as e:
                print("  aviso VPN habilitados:", e)
    return {"partidos": partidos, "tablas": tablas, "sanciones": sanciones, "titulos": _titulos_vpn()}


def _corto(temporada: str) -> str:
    """'Temporada 11' -> 'T11'."""
    n = "".join(ch for ch in temporada if ch.isdigit())
    return f"T{n}" if n else temporada


def _historial(c, bid: str, com: str, slug: str, tid: int, previos: dict, actuales: set) -> list:
    hist = _data(c, bid, f"{com}/teams/{slug}/seasons", f"communitySlug={com}&id={slug}&tab=seasons")["history"]
    guardar_raw("vpn", "temporadas", hist)
    try:
        vitrina = _data(c, bid, f"{com}/teams/{slug}/trophies", f"communitySlug={com}&id={slug}&tab=trophies")["cabinet"]
        guardar_raw("vpn", "vitrina", vitrina)
    except ErrorConector as e:
        print("  aviso VPN vitrina:", e)
    salida = []
    for s in hist.get("seasons", []):
        comp_id = f"vpn-{s['key']}"
        if comp_id in actuales:
            continue
        ya = [p for p in previos.values() if p.get("competencia_id") == comp_id]
        if ya and not s.get("active") and all("formacion" in p for p in ya if p.get("stats")):
            salida += ya  # temporada cerrada y ya guardada
            continue
        nombre = s["competitionName"]
        temporada = {"clave": comp_id, "nombre": f"{nombre} {s.get('seasonShort', '')}".strip()}
        pagina, items = 1, []
        while True:
            m = _data(c, bid, f"{com}/teams/{slug}/matches",
                      f"communitySlug={com}&id={slug}&tab=matches&view=results&comp={s['key']}&page={pagina}")["matches"]
            items += m.get("items", [])
            if not m.get("hasMore") or pagina > 10:
                break
            pagina += 1
        for it in items:
            if it.get("status") != "played":
                continue
            pid = f"vpn-{it['id']}"
            if pid in previos and previos[pid].get("stats") and "formacion" in previos[pid]:
                salida.append(previos[pid])
                continue
            try:
                rep = _data(c, bid, f"{com}/matches/{it['id']}", f"communitySlug={com}&id={it['id']}")["report"]
            except ErrorConector as e:
                print("  aviso VPN historial:", e)
                continue
            local = rep["home"]["teamId"] == tid
            lado, otro = (rep["home"], rep["away"]) if local else (rep["away"], rep["home"])
            sc = rep["match"].get("score") or {}
            gf, gc = (sc.get("home"), sc.get("away")) if local else (sc.get("away"), sc.get("home"))
            salida.append({
                "id": pid, "liga": "vpn", "competencia_id": comp_id, "competencia": nombre,
                "jornada": it.get("roundLabel") or f"Jornada {rep['match'].get('round')}",
                "fecha_utc": rep["match"]["date"].replace(".000Z", "Z"),
                "local": local,
                "rival": {"nombre": otro["team"]["name"], "escudo": otro["team"].get("logoUrl")},
                "gf": gf, "gc": gc,
                "estado": "wo" if rep["match"].get("forfeit") else "finalizado",
                "url_origen": f"{BASE}/{com}/matches/{it['id']}",
                "temporada": temporada,
                "stats": [_stat_jugador(j) for j in lado.get("players", [])],
                "equipo_stats": _equipo(lado, otro),
                "formacion": _formacion(lado),
            })
    return salida


def _titulos_vpn() -> list:
    """Títulos de la vitrina oficial de VPN (se leen del archivo guardado al sincronizar)."""
    from .base import RAW
    f = RAW / "vpn" / "vitrina.json"
    if not f.exists():
        return []
    v = json.loads(f.read_text(encoding="utf-8"))
    return [{"liga": "vpn", "nombre": t.get("name") or t.get("competitionName") or t.get("label") or "Título",
             "fecha": (t.get("date") or t.get("spanLabel") or ""), "fuente": f"{BASE}/uy/teams/vultur-sports/trophies"}
            for t in (v.get("titles") or [])]


def _formacion(lado: dict) -> str | None:
    """Nombre de la formación que publica VPN para ese partido (por ejemplo "4-3-1-2")."""
    return ((lado.get("report") or {}).get("formation") or {}).get("name")


def _equipo(lado: dict, otro: dict) -> dict | None:
    """Estadísticas del partido por equipo (las publica VPN desde EA)."""
    def conv(e):
        if not e:
            return None
        return {"tiros": e.get("shots"), "pases": e.get("passesMade"), "pases_int": e.get("passAttempts"),
                "entradas": e.get("tacklesMade"), "entradas_int": e.get("tackleAttempts"),
                "atajadas": e.get("saves"), "nota": e.get("averageRating")}
    a, b = conv(lado.get("eaTotals")), conv(otro.get("eaTotals"))
    return {"nosotros": a, "rival": b} if (a or b) else None


def _stat_jugador(j: dict) -> dict:
    s = {v: 0 for v in EVENTOS.values()}
    for k, n in (j.get("stats") or {}).items():
        if k in EVENTOS:
            s[EVENTOS[k]] += n
    ea = j.get("ea") or {}
    pos = j.get("position") or {}
    return {
        "alias": (j.get("name") or "").strip(),
        "alias_id": str(j.get("userId")),
        "posicion": pos.get("code"),
        "goles": s["goles"],
        "asistencias": s["asistencias"],
        "mvp": bool(j.get("motm")),
        "rating": ea.get("rating"),
        "amarillas": s["amarillas"],
        "rojas": s["rojas"],
        "valla_invicta": bool(s["vallas"] or s["vallas_def"]),
    }


if __name__ == "__main__":  # prueba rápida: python -m conectores.vpn
    import yaml
    from .base import RAIZ
    cfg = yaml.safe_load((RAIZ / "config" / "ligas.yaml").read_text(encoding="utf-8"))
    out = sincronizar(cfg["ligas"]["vpn"], cfg["club"], {})
    print(json.dumps(out["tablas"][0]["filas"][:3], ensure_ascii=False, indent=1))
    print(len(out["partidos"]), "partidos")
