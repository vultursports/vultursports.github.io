"""LVA — Liga Virtual Argentina (ligavirtualargentina.com).

Abre las páginas públicas de la LVA con un navegador automático (Playwright), igual que un
visitante, y lee los datos que esas páginas reciben para mostrarse: fixture, tabla y
estadísticas por jugador. No usa claves ni accesos propios.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import json

from .base import RAW, guardar_raw

SITIO = "https://ligavirtualargentina.com"
ESTADOS = {"approved": "finalizado", "live": "en_vivo", "scheduled": "programado"}


def _torneo_de(url: str) -> str | None:
    v = parse_qs(urlparse(url).query).get("tournament_id", [""])[0]
    return v[3:] if v.startswith("eq.") else None


def sincronizar(cfg: dict, cfg_club: dict, partidos_previos: dict) -> dict:
    from playwright.sync_api import sync_playwright

    nombre_club = cfg_club["nombre"].lower()
    respuestas: list[tuple[str, object]] = []

    def capturar(r):
        if "/rest/v1/" in r.url and r.request.method == "GET" and r.ok:
            try:
                respuestas.append((r.url, r.json()))
            except Exception:  # respuestas HEAD/vacías
                pass

    partidos, tablas = [], []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pg = nav.new_page(locale="es-AR", timezone_id="America/Argentina/Buenos_Aires")
        pg.on("response", capturar)

        # 1) Fixture: un pedido por torneo
        pg.goto(f"{SITIO}/fixture", wait_until="networkidle")
        torneos = pg.eval_on_selector_all("select option", "os => os.map(o => [o.value, o.text.trim()])")
        for val, _ in torneos:
            pg.select_option("select", val)
            pg.wait_for_timeout(2000)
        fixture = {}
        for url, datos in respuestas:
            t = _torneo_de(url)
            if "/matches?" in url and t and isinstance(datos, list):
                fixture[t] = datos

        # Torneos terminados ("Ver Finalizados"): cada uno se revisa una sola vez y queda anotado
        archivo_fin = RAW / "lva" / "finalizados.json"
        revisados = json.loads(archivo_fin.read_text(encoding="utf-8")) if archivo_fin.exists() else {}
        activos = {t for t, _ in torneos}
        nuevos_fin = []
        try:
            pg.click("text=Ver Finalizados")
            pg.wait_for_timeout(2500)
            for val, nom in pg.eval_on_selector_all("select option", "os => os.map(o => [o.value, o.text.trim()])"):
                if val not in activos and val not in revisados:
                    pg.select_option("select", val)
                    pg.wait_for_timeout(2000)
                    nuevos_fin.append((val, nom))
        except Exception as e:
            print("  aviso LVA finalizados:", e)
        for url, datos in respuestas:
            t = _torneo_de(url)
            if "/matches?" in url and t and isinstance(datos, list):
                fixture[t] = datos

        mios = {}
        for tid, nombre in torneos + nuevos_fin:
            ms = [m for m in fixture.get(tid, [])
                  if nombre_club in (m["home_team"]["name"] + " " + m["away_team"]["name"]).lower()]
            if ms:
                mios[tid] = (nombre, ms)
        guardar_raw("lva", "fixture", {t: fixture.get(t) for t, _ in torneos})
        if not mios:
            nav.close()
            return {"partidos": [], "tablas": []}

        team_id = next(m["home_team"]["id"] if nombre_club in m["home_team"]["name"].lower() else m["away_team"]["id"]
                       for _, ms in mios.values() for m in ms)

        # 2) Tablas (se leen de la tabla que muestra la página)
        pg.goto(f"{SITIO}/tabla-posiciones", wait_until="networkidle")
        for tid, (nombre, _) in [(t, v) for t, v in mios.items() if t in activos]:
            pg.select_option("select", tid)
            pg.wait_for_timeout(2500)
            filas = pg.evaluate("""() => [...document.querySelectorAll('table')].map(t =>
                [...t.querySelectorAll('tbody tr')].map(tr => ({
                    celdas: [...tr.querySelectorAll('td')].map(td => td.innerText.trim()),
                    escudo: tr.querySelector('img') ? tr.querySelector('img').src : null
                })))""")
            tabla = next((t for t in filas if any(nombre_club in " ".join(r["celdas"]).lower() for r in t)), None)
            if tabla:
                tablas.append(_tabla(tid, nombre, tabla, nombre_club))

        # 3) Estadísticas por jugador (la página carga las de todos los partidos del torneo)
        respuestas.clear()
        pg.goto(f"{SITIO}/estadisticas", wait_until="networkidle")
        for tid in [t for t in mios if t in activos]:
            try:
                pg.select_option("select", tid)
                pg.wait_for_timeout(2500)
            except Exception:
                pass
        fin_con_vultur = [t for t in mios if t not in activos]
        if fin_con_vultur:
            try:
                pg.click("text=Ver Finalizados")
                pg.wait_for_timeout(2500)
                for tid in fin_con_vultur:
                    pg.select_option("select", tid)
                    pg.wait_for_timeout(3000)
            except Exception as e:
                print("  aviso LVA estadísticas finalizados:", e)
        stats_por_partido: dict[str, list] = {}
        for url, datos in respuestas:
            if "/player_match_stats?" in url and isinstance(datos, list):
                for s in datos:
                    if s.get("team_id") == team_id:
                        stats_por_partido.setdefault(s["match_id"], []).append(s)
        # Sanciones publicadas por la LVA (páginas públicas de estadísticas y de sanciones)
        pg.goto(f"{SITIO}/equipos", wait_until="networkidle")  # carga todos los torneos con su campeón
        pg.wait_for_timeout(1500)
        pg.goto(f"{SITIO}/sanciones", wait_until="networkidle")
        pg.wait_for_timeout(2500)
        sanciones_raw = {}
        for url, datos in respuestas:
            if "/sanctions?" in url and isinstance(datos, list):
                for x in datos:
                    sanciones_raw[x.get("id") or len(sanciones_raw)] = x
        guardar_raw("lva", "sanciones", list(sanciones_raw.values()))
        nav.close()

    for tid, (nombre, ms) in mios.items():
        comp_id = f"lva-{tid[:8]}"
        for i, m in enumerate(sorted(ms, key=lambda m: m["match_date"])):
            local = m["home_team"]["id"] == team_id
            rival = m["away_team"] if local else m["home_team"]
            estado = ESTADOS.get(m["status"], "programado")
            # La LVA aprueba por adelantado los partidos de un equipo dado de baja: W.O.
            fecha = datetime.fromisoformat(m["match_date"])
            previo = partidos_previos.get(f"lva-{m['id']}") or {}
            if estado == "finalizado" and (fecha > datetime.now(timezone.utc) or previo.get("estado") == "wo"):
                estado = "wo"
            jugado = estado in ("finalizado", "wo")
            vistos = {}
            for n, s in enumerate(stats_por_partido.get(m["id"], [])):
                # sin duplicados por jugador; los registros sin jugador asignado se conservan todos
                vistos[s.get("player_id") or f"sin-jugador-{n}"] = _stat(s)
            partidos.append({
                "id": f"lva-{m['id']}",
                "liga": "lva",
                "competencia_id": comp_id,
                "competencia": _nombre_torneo(nombre),
                "jornada": (m.get("stage") or f"Fecha {i + 1}").strip(),
                "fecha_utc": m["match_date"].replace("+00:00", "Z"),
                "local": local,
                "rival": {"nombre": rival["name"].strip(), "escudo": rival.get("logo_url")},
                "gf": (m["home_goals"] if local else m["away_goals"]) if jugado else None,
                "gc": (m["away_goals"] if local else m["home_goals"]) if jugado else None,
                "estado": estado,
                "url_origen": f"{SITIO}/fixture",
                "temporada": {"clave": comp_id, "nombre": _nombre_torneo(nombre)},
                "stats": list(vistos.values()),
            })
    for tid, nom in nuevos_fin:
        revisados[tid] = {"nombre": nom, "con_vultur": tid in mios}
    archivo_fin.parent.mkdir(parents=True, exist_ok=True)
    archivo_fin.write_text(json.dumps(revisados, ensure_ascii=False, indent=1), encoding="utf-8")
    ya = {p["id"] for p in partidos}
    claves_fin = {f"lva-{t[:8]}" for t, v in revisados.items() if v.get("con_vultur")}
    partidos += [p for p in partidos_previos.values() if p.get("competencia_id") in claves_fin and p["id"] not in ya]
    # Títulos: torneos donde la LVA marca a Vultur como campeón
    todos_torneos = {}
    for url, datos in respuestas:
        if "/tournaments?" in url and isinstance(datos, list):
            for t in datos:
                todos_torneos.setdefault(t.get("id"), {}).update({k: v for k, v in t.items() if v is not None})
    titulos = [{"liga": "lva", "nombre": _nombre_torneo(t.get("name", "")), "fecha": (t.get("created_at") or "")[:10],
                "fuente": f"{SITIO}/equipos"}
               for t in todos_torneos.values() if t.get("champion_id") == team_id]
    nombres_torneo = {tid: _nombre_torneo(n) for tid, n in torneos}
    sanciones = [{
        "liga": "lva",
        "competencia": nombres_torneo.get(x.get("tournament_id"), ""),
        "jugador": ((x.get("player") or {}).get("game_user") or (x.get("player") or {}).get("name") or "").strip(),
        "motivo": x.get("reason") or x.get("sanction_type"),
        "fechas": x.get("matches_count"),
        "cumple": x.get("match_to_serve_stage"),
        "vigente": x.get("status") != "served",
    } for x in sanciones_raw.values() if x.get("team_id") == team_id]
    return {"partidos": partidos, "tablas": tablas, "sanciones": sanciones, "titulos": titulos}


def _nombre_torneo(n: str) -> str:
    return n.replace("DiV", "Div").strip()


def _num(x: str) -> int:
    try:
        return int(x.replace("+", "").strip())
    except ValueError:
        return 0


def _tabla(tid: str, nombre: str, filas: list, nombre_club: str) -> dict:
    out = []
    for r in filas:
        c = r["celdas"]
        if len(c) < 10:
            continue
        # Columnas de la LVA: Pos, Equipo, PJ, G, E, P, GF, GC, DG, Pts
        out.append({
            "pos": _num(c[0]) or len(out) + 1,
            "equipo": c[1].strip(),
            "escudo": r["escudo"],
            "pj": _num(c[2]), "g": _num(c[3]), "e": _num(c[4]), "p": _num(c[5]),
            "gf": _num(c[6]), "gc": _num(c[7]), "dg": _num(c[8]), "pts": _num(c[9]),
            "zona": None,
            "es_vultur": nombre_club in c[1].lower(),
        })
    return {
        "id": f"lva-{tid[:8]}",
        "liga": "lva",
        "competencia": _nombre_torneo(nombre),
        "temporada": "",
        "logo": None,
        "url_origen": f"{SITIO}/tabla-posiciones",
        "filas": out,
    }


def _stat(s: dict) -> dict:
    jug = s.get("player") or {}
    return {
        "alias": (jug.get("game_user") or jug.get("name") or "").strip(),
        "alias_id": str(s.get("player_id")),
        "posicion": s.get("position_played") or jug.get("position"),
        "goles": s.get("goals") or 0,
        "asistencias": s.get("assists") or 0,
        "mvp": bool(s.get("is_mvp")),
        "rating": s.get("rating"),
        "amarillas": s.get("yellow_cards") or 0,
        "rojas": s.get("red_cards") or 0,
        "valla_invicta": False,
    }
