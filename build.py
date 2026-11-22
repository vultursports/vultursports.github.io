"""Genera el sitio estático en site/ a partir de datos/*.json.

Uso:  python build.py
Horas: todo se muestra en hora argentina (UTC-3, sin horario de verano). Los partidos se
agrupan por "noche de juego": lo que se juega entre las 00:00 y las 05:59 cuenta para la noche
anterior.
"""
from __future__ import annotations

import json
from collections import Counter
import re
import shutil
from xml.sax.saxutils import escape
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import jugadores as jug_mod
import escudos as esc_mod
import og
import rivales as riv_mod
from jinja2 import Environment, FileSystemLoader, select_autoescape

RAIZ = Path(__file__).resolve().parent
DATOS = RAIZ / "datos"
SITE = RAIZ / "site"
AR = timezone(timedelta(hours=-3), "AR")

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

# Identidad visual y créditos de cada liga (nombre completo, web y redes van en config/ligas.yaml)
LIGAS_UI = {
    "lva": {"corto": "LVA"},
    "vpn": {"corto": "VPN"},
    "vpug": {"corto": "VPUG"},
}
REDES_TXT = {"instagram": "Instagram", "x": "X", "youtube": "YouTube", "twitch": "Twitch",
             "facebook": "Facebook", "discord": "Discord"}


def leer(nombre, defecto):
    f = DATOS / nombre
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else defecto


def a_local(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(AR)


def fecha_larga(d) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


EDICIONES: list = []  # [(fecha_desde, nombre)] ordenadas; se cargan de config/ligas.yaml


# Cancha: códigos de posición unificados entre ligas y su lugar (x: izq→der, y: arriba = ataque).
# Es la misma tabla que usa estaticos/js/plantel.js para "El 11 más usado".
ALIAS_POS = {"PO": "POR", "GK": "POR", "LTD": "LD", "LTI": "LI", "CAD": "LD", "CAI": "LI"}
LUGAR = {"POR": (50, 91), "DFC": (50, 76), "LD": (86, 71), "LI": (14, 71), "MCD": (50, 61), "MC": (50, 47),
         "MD": (86, 44), "MI": (14, 44), "MCO": (50, 31), "DC": (50, 11), "DD": (70, 13), "DI": (30, 13),
         "ED": (87, 17), "EI": (13, 17), "SD": (50, 22)}


LINEA = {"LI": "def", "DFC": "def", "LD": "def", "MI": "med", "MC": "med", "MD": "med",
         "EI": "del", "DI": "del", "DC": "del", "DD": "del", "ED": "del"}
BANDAS = {"LI", "LD", "MI", "MD", "EI", "ED"}


def posiciones_x(pos: list) -> list:
    """x de cada jugador. Si en una línea hay un puesto repetido (p. ej. dos LI, como a veces carga
    la LVA), toda la línea se reparte a lo ancho para que nadie quede fuera de la cancha ni encimado."""
    xs = [LUGAR[p][0] for p in pos]
    grupos: dict[str, list] = {}
    for i, p in enumerate(pos):
        grupos.setdefault(LINEA.get(p, p), []).append(i)
    for idx in grupos.values():
        if len(idx) == len({pos[i] for i in idx}):
            continue  # sin repetidos: cada uno en su lugar
        idx.sort(key=lambda i: LUGAR[pos[i]][0])
        n = len(idx)
        if any(pos[i] in BANDAS for i in idx):
            nuevos = [14 + k * 72 / (n - 1) for k in range(n)]
        else:
            paso = min(34 if n == 2 else 26, 76 / (n - 1))
            nuevos = [50 + (k - (n - 1) / 2) * paso for k in range(n)]
        for i, x in zip(idx, nuevos):
            xs[i] = x
    return xs


FILA_FORMACION = {"LI": 0, "DFC": 0, "LD": 0, "MCD": 1, "MI": 2, "MC": 2, "MD": 2, "MCO": 3, "SD": 3,
                  "EI": 4, "DI": 4, "DC": 4, "DD": 4, "ED": 4}


def formacion_por_lineas(stats: list) -> str | None:
    """Nombre de la formación según las posiciones cargadas (por ejemplo 4-1-2-1-2). Solo si están
    los 10 jugadores de campo con una posición conocida."""
    filas = [0] * 5
    campo = 0
    for s in stats:
        pos = ALIAS_POS.get(s.get("posicion") or "", s.get("posicion") or "")
        if pos == "POR":
            continue
        if pos not in FILA_FORMACION:
            return None
        filas[FILA_FORMACION[pos]] += 1
        campo += 1
    return "-".join(str(n) for n in filas if n) if campo == 10 else None


def alineacion(stats: list, ficha_de: dict) -> list:
    """Ubica en la cancha a los jugadores de un partido según la posición que ocuparon."""
    lista = [(ALIAS_POS.get(s.get("posicion") or "", s.get("posicion") or ""), s) for s in stats]
    lista = [(pos, s) for pos, s in lista if s.get("alias") and pos in LUGAR]
    salida = []
    for x, (pos, s) in zip(posiciones_x([p for p, _ in lista]), lista):
        j = ficha_de.get(jug_mod.clave(s["alias"])) or {}
        salida.append({"x": round(x, 1), "y": LUGAR[pos][1], "pos": pos,
                       "alias": s["alias"], "dorsal": j.get("dorsal"), "pagina": j.get("pagina"),
                       "nota": s.get("rating") if (s.get("rating") or -1) >= 0 else None,
                       "goles": s.get("goles") or 0, "asist": s.get("asistencias") or 0, "mvp": s.get("mvp")})
    return salida


def oficial_vpn(unir: dict) -> dict | None:
    """Alineación habitual oficial que el club carga en VPN, con los mismos códigos de puesto que el resto
    de la web (correcciones del club: en la 4-1-2-1-2 MI/MD son MC; en dos puntas DD/DI son DC)."""
    o = leer("alineacion_vpn.json", None)
    if not o or len(o.get("jugadores") or []) < 11:
        return None
    corr = dict(CORRECCION_POS.get(o["formacion"], {}))
    if not any(j["pos"] == "DC" for j in o["jugadores"]):
        corr.update({"DD": "DC", "DI": "DC"})
    jugadores = []
    for j in o["jugadores"]:
        pos = corr.get(j["pos"], j["pos"])
        k = jug_mod.clave(j["alias"])
        jugadores.append({"id": unir.get(k, k), "alias": j["alias"], "pos": ALIAS_POS.get(pos, pos)})
    return {"formacion": o["formacion"], "jugadores": jugadores, "url_origen": o.get("url_origen")}


def once_oficial(oficial: dict, lista: list, ficha_de: dict) -> dict:
    """El 11 oficial de VPN ubicado en la cancha, con los números de cada jugador en esos partidos."""
    stats = []
    for j in oficial["jugadores"]:
        jugados = [x for p in lista if p.get("resultado") and not p.get("wo") for x in p.get("stats", [])
                   if x.get("alias") and jug_mod.clave(x["alias"]) == j["id"]]
        notas = [x["rating"] for x in jugados if (x.get("rating") or -1) >= 0]
        stats.append({"alias": (ficha_de.get(j["id"]) or {}).get("alias") or j["alias"], "posicion": j["pos"],
                      "goles": sum(x.get("goles") or 0 for x in jugados), "asistencias": sum(x.get("asistencias") or 0 for x in jugados),
                      "rating": round(sum(notas) / len(notas), 2) if notas else None, "mvp": False, "pj": len(jugados)})
    placed = alineacion(stats, ficha_de)
    for x, s in zip(placed, [s for s in stats if s["posicion"] in LUGAR]):
        x["pj"] = s["pj"]
    return {"jugadores": placed, "formacion": oficial["formacion"], "oficial": True}


def once_mas_usado(lista: list, ficha_de: dict) -> dict | None:
    """Alineación más repetida en una lista de partidos y, por puesto, quien más veces lo ocupó."""
    conteo, partidos_de = Counter(), {}
    jug: dict[str, dict] = {}
    for p in lista:
        if not p.get("resultado") or p.get("wo"):
            continue
        pos = [ALIAS_POS.get(x.get("posicion") or "", x.get("posicion") or "") for x in p.get("stats", [])]
        if len(pos) >= 10 and all(pos):
            k = ",".join(sorted(pos)); conteo[k] += 1; partidos_de.setdefault(k, []).append(p)
        for x in p.get("stats", []):
            if not x.get("alias"):
                continue
            j = jug.setdefault(jug_mod.clave(x["alias"]), {"alias": x["alias"], "pj": 0, "pos": Counter(), "notas": [], "goles": 0, "asist": 0})
            j["pj"] += 1; j["goles"] += x.get("goles") or 0; j["asist"] += x.get("asistencias") or 0
            q = ALIAS_POS.get(x.get("posicion") or "", x.get("posicion") or "")
            if q: j["pos"][q] += 1
            if (x.get("rating") or -1) >= 0: j["notas"].append(x["rating"])
    if not conteo:
        return None
    firma, veces = conteo.most_common(1)[0]
    slots = firma.split(",")
    pares = sorted(((j["pos"][q], k, i) for k, j in jug.items() for i, q in enumerate(slots) if j["pos"][q]),
                   key=lambda t: (-t[0], -jug[t[1]]["pj"]))
    usado, asignado = set(), {}
    for _, k, i in pares:
        if k not in usado and i not in asignado:
            usado.add(k); asignado[i] = k
    for i in range(len(slots)):
        if i not in asignado:
            libre = max((k for k in jug if k not in usado), key=lambda k: jug[k]["pj"], default=None)
            if libre: usado.add(libre); asignado[i] = libre
    stats = []
    for i, q in enumerate(slots):
        if i in asignado:
            j = jug[asignado[i]]
            stats.append({"alias": j["alias"], "posicion": q, "goles": j["goles"], "asistencias": j["asist"],
                          "rating": round(sum(j["notas"]) / len(j["notas"]), 2) if j["notas"] else None, "mvp": False})
    placed = alineacion(stats, ficha_de)
    for x in placed:
        x["pj"] = jug[jug_mod.clave(x["alias"])]["pj"]
    nombres = Counter(p["formacion"] for p in partidos_de[firma] if p.get("formacion"))
    return {"jugadores": placed, "formacion": nombres.most_common(1)[0][0] if nombres else None,
            "veces": veces, "total": sum(conteo.values())}


def rachas(lista: list) -> dict:
    """Rachas del club en partidos jugados (sin W.O.), en orden cronológico."""
    mejor_g = mejor_inv = act_g = act_inv = 0
    for p in lista:
        r = p["resultado"]
        act_g = act_g + 1 if r == "g" else 0
        act_inv = act_inv + 1 if r in ("g", "e") else 0
        mejor_g, mejor_inv = max(mejor_g, act_g), max(mejor_inv, act_inv)
    actual = None
    if lista:
        ult = lista[-1]["resultado"]
        n = 0
        for p in reversed(lista):
            if p["resultado"] == ult: n += 1
            else: break
        actual = {"tipo": ult, "n": n}
    return {"victorias": mejor_g, "invicto": mejor_inv, "actual": actual}


def edicion_de(d) -> str:
    nombre = ""
    for desde, n in EDICIONES:
        if d >= desde:
            nombre = n
    return nombre


# Correcciones de posiciones pedidas por el club para que VPN coincida con la LVA:
# - en la 4-1-2-1-2, VPN registra a los volantes como MD/MI, pero son dos MC;
# - en formaciones de dos puntas, VPN llama DD/DI a los delanteros; son dos DC.
CORRECCION_POS = {"4-1-2-1-2": {"MD": "MC", "MI": "MC"}}


def preparar_partido(p: dict, ligas: dict) -> dict:
    corr = dict(CORRECCION_POS.get(p.get("formacion") or "", {}))
    # VPN llama DD/DI a los dos delanteros de una formación de dos puntas; la LVA los registra como
    # dos DC. Si la alineación no tiene un DC (dos puntas), se muestran como DC.
    if p.get("liga") == "vpn" and not any(x.get("posicion") == "DC" for x in p.get("stats", [])):
        corr.update({"DD": "DC", "DI": "DC"})
    if corr:
        for s in p.get("stats", []):
            if s.get("posicion") in corr:
                s["posicion"] = corr[s["posicion"]]
    loc = a_local(p["fecha_utc"])
    noche = (loc - timedelta(hours=6)).date()
    p = dict(p)
    p["dt"] = loc
    p["hora"] = loc.strftime("%H:%M")
    p["noche"] = noche
    p["noche_txt"] = fecha_larga(noche)
    p["noche_corta"] = f"{DIAS[noche.weekday()][:3]} {noche.day} {MESES[noche.month - 1][:3]}"
    p["liga_ui"] = ligas[p["liga"]]
    p["condicion"] = "Local" if p["local"] else "Visitante"
    if p["gf"] is not None and p["gc"] is not None:
        p["resultado"] = "g" if p["gf"] > p["gc"] else ("p" if p["gf"] < p["gc"] else "e")
    else:
        p["resultado"] = None
    p["wo"] = p.get("estado") == "wo"
    p["mvp"] = next((s["alias"] for s in p.get("stats", []) if s.get("mvp")), None)
    p["goleadores"] = [(s["alias"], s["goles"]) for s in p.get("stats", []) if s.get("goles")]
    for s in p.get("stats", []):
        if s.get("rating") is None:
            s["rating"] = -1  # para ordenar; se muestra vacío
    p["pagina"] = f"/partido/{p['id']}/"
    p["temporada"] = p.get("temporada") or {"clave": p.get("competencia_id", p["liga"]), "nombre": p["competencia"]}
    p["edicion"] = edicion_de(noche)
    return p


def ventana(filas, alrededor=2):
    i = next((k for k, f in enumerate(filas) if f["es_vultur"]), 0)
    ini = max(0, min(i - alrededor, len(filas) - (2 * alrededor + 1)))
    return filas[ini: ini + 2 * alrededor + 1]


def generar_ics(partidos, club) -> str:
    def f(dt):
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ahora = datetime.now(timezone.utc)
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Vultur Sports//Calendario//ES",
              "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{club} — Partidos",
              "X-WR-TIMEZONE:America/Argentina/Buenos_Aires", "REFRESH-INTERVAL;VALUE=DURATION:PT3H"]
    for p in partidos:
        res = f" ({p['gf']}-{p['gc']})" if p["resultado"] else ""
        titulo = f"{p['liga_ui']['corto']}: Vultur Sports vs {p['rival']['nombre']}{res}"
        desc = f"{p['competencia']}, {p['jornada']}. {p['condicion']}. Fuente: {p['url_origen']}"
        lineas += ["BEGIN:VEVENT", f"UID:{p['id']}@vultursports.github.io", f"DTSTAMP:{f(ahora)}",
                   f"DTSTART:{f(p['dt'])}", f"DTEND:{f(p['dt'] + timedelta(minutes=30))}",
                   f"SUMMARY:{titulo}", f"DESCRIPTION:{desc}", f"URL:{p['url_origen']}", "END:VEVENT"]
    lineas.append("END:VCALENDAR")
    return "\r\n".join(lineas) + "\r\n"


def main():
    cfg = yaml.safe_load((RAIZ / "config" / "ligas.yaml").read_text(encoding="utf-8"))
    ligas = {}
    # Orden fijo de las ligas en todo el sitio (selectores, filtros, créditos)
    ORDEN_LIGAS = ["vpn", "lva", "vpug"]
    for k, l in sorted(cfg["ligas"].items(), key=lambda kv: ORDEN_LIGAS.index(kv[0]) if kv[0] in ORDEN_LIGAS else 99):
        if k not in LIGAS_UI:
            continue
        nombre = l["nombre"].split("—", 1)[-1].strip()
        ligas[k] = {**LIGAS_UI[k], "clave": k, "nombre": nombre, "sitio": l["sitio"],
                    "redes": [(REDES_TXT.get(r, r), u) for r, u in (l.get("redes") or {}).items()],
                    "activa": l.get("activa", False)}

    ahora = datetime.now(AR)
    EDICIONES[:] = sorted((e["desde"], e["nombre"]) for e in cfg["club"].get("ediciones", []))
    edicion_actual = edicion_de(ahora.date())
    partidos = [preparar_partido(p, ligas) for p in leer("partidos.json", [])]
    tablas = leer("tablas.json", [])
    estado = leer("estado.json", {})
    for t in tablas:
        t["liga_ui"] = ligas[t["liga"]]
        t["mini"] = ventana(t["filas"])
        orden_z = ['lider', 'ascenso', 'playoff', 'reducido', 'clasifica', 'descenso']
        nombres_z = {'lider': 'Líder', 'ascenso': 'Ascenso', 'playoff': 'Playoffs', 'reducido': 'Reducido', 'clasifica': 'Clasifica', 'descenso': 'Descenso'}
        presentes = {f["zona"] for f in t["filas"] if f.get("zona")}
        nombres_t = {**nombres_z, **(t.get("nombres_zona") or {})}
        t["leyenda"] = [(z, nombres_t.get(z, z.title())) for z in sorted(presentes, key=lambda z: orden_z.index(z) if z in orden_z else 99)]
        t["corto"] = re.sub(r"\s*\(.*?\)", "", t["competencia"]).replace("Liga Argentina ", "").strip()
        t["vultur"] = next((f for f in t["filas"] if f["es_vultur"]), None)
        t["actualizado_txt"] = a_local(t["actualizado"]).strftime("%d/%m %H:%M") if t.get("actualizado") else ""

    # Escudos: copias locales recortadas y del mismo tamaño
    esc = esc_mod.Escudos(DATOS / "escudos")
    def escudo_local(url):
        n = esc.local(url)
        return (f"/escudos/{n}", str(DATOS / "escudos" / n)) if n else (url, None)
    for p in partidos:
        p["rival"]["escudo_url"] = p["rival"].get("escudo")
        p["rival"]["escudo"], p["rival"]["escudo_archivo"] = escudo_local(p["rival"]["escudo_url"])
    for t in tablas:
        for f in t["filas"]:
            f["escudo"] = escudo_local(f.get("escudo"))[0]
    esc.guardar()

    pos_en = {t["id"]: ({jug_mod.clave(f["equipo"]): f["pos"] for f in t["filas"]}, len(t["filas"])) for t in tablas}
    for p in partidos:
        mapa, n = pos_en.get(p.get("competencia_id"), ({}, 0))
        p["pos_nos"] = next((f["pos"] for t in tablas if t["id"] == p.get("competencia_id") for f in t["filas"] if f["es_vultur"]), None)
        p["pos_rival"] = mapa.get(jug_mod.clave(p["rival"]["nombre"]))

    for p in partidos:
        p["empezo"] = p["dt"] <= ahora
    # La tarjeta principal muestra "Se está jugando" hasta que empieza el siguiente partido de la misma
    # noche; si es el último de la noche, durante 30 minutos. Después pasa sola al siguiente.
    EN_JUEGO = timedelta(minutes=30)
    orden = sorted(partidos, key=lambda p: p["dt"])
    for p, sig in zip(orden, orden[1:] + [None]):
        mismo_dia = sig is not None and sig["noche"] == p["noche"] and sig["dt"] > p["dt"]
        p["fin_tarjeta"] = sig["dt"] if mismo_dia else p["dt"] + EN_JUEGO
    proximos = [p for p in partidos if p["resultado"] is None and p["fin_tarjeta"] > ahora]
    jugados = [p for p in partidos if p["resultado"]][::-1]
    # Ya se jugaron pero la liga todavía no cargó (o no aprobó) el resultado: siguen en el
    # calendario, en "Jugados", con un "?" hasta que aparezca el marcador.
    sin_resultado = [p for p in partidos if p["resultado"] is None and p["fin_tarjeta"] <= ahora]
    cal_jugados = sorted(jugados + sin_resultado, key=lambda p: p["dt"], reverse=True)
    proximo = proximos[0] if proximos else None

    # Orden de las competencias: primero la que se juega antes; después las que no publican
    # fixture (VPUG); al final las que ya no tienen partidos por jugar.
    def orden_comp(t):
        prox = [p["dt"] for p in proximos if p.get("competencia_id") == t["id"]]
        if prox:
            return (0, min(prox).isoformat())
        if not any(p.get("competencia_id") == t["id"] for p in partidos):
            return (1, "")
        return (2, "")
    tablas.sort(key=orden_comp)
    hoy_noche = (ahora - timedelta(hours=6)).date()
    # Los partidos de una noche quedan en "Esta semana" hasta las 12 del mediodía del día
    # siguiente (tengan o no resultado); después solo están en el calendario.
    desde_noche = (ahora - timedelta(hours=12)).date()
    semana = sorted((p for p in partidos if desde_noche <= p["noche"] <= hoy_noche + timedelta(days=7)), key=lambda p: p["dt"])
    # Tarjetas del próximo partido: la página pasa sola de una a otra a medida que empiezan
    tarjetas = proximos[:6]

    def agrupar(lista):
        grupos = []
        for p in lista:
            if not grupos or grupos[-1]["noche"] != p["noche"]:
                grupos.append({"noche": p["noche"], "txt": p["noche_txt"], "partidos": []})
            grupos[-1]["partidos"].append(p)
        return grupos

    # Jugadores
    ajustes = yaml.safe_load((RAIZ / "config" / "plantel.yaml").read_text(encoding="utf-8")) or {}
    js = jug_mod.armar(partidos, leer("plantel_vpug.json", []), ajustes)["jugadores"]
    con_pj = [j for j in js if j["total"]["pj"]]
    ambitos = [{"clave": "todas", "titulo": "Todas", "liga": None}] + [
        {"clave": k, "titulo": l["nombre"], "liga": l} for k, l in ligas.items()
        if any(j["por_liga"][k]["pj"] for j in js)]
    for a in ambitos:
        clave_st = (lambda j: j["total"]) if a["clave"] == "todas" else (lambda j, k=a["clave"]: j["por_liga"][k])
        a["filas"] = sorted((j for j in js if clave_st(j)["pj"]),
                            key=lambda j: (-(clave_st(j)["nota"] or 0), -clave_st(j)["pj"]))
        a["rank"] = jug_mod.rankings(js, a["clave"])
    sin_partidos = sorted((j for j in js if not j["total"]["pj"]), key=lambda j: j["alias"].lower())

    # Filtro del plantel: temporadas de cada liga y ediciones del juego
    temporadas = {}
    for p in partidos:
        if p.get("resultado") and p.get("stats"):
            t = p["temporada"]
            x = temporadas.setdefault(t["clave"], {"clave": t["clave"], "nombre": t["nombre"], "liga": p["liga"],
                                                   "edicion": p["edicion"], "desde": p["fecha_utc"]})
            x["desde"] = min(x["desde"], p["fecha_utc"])
    temporadas_lista = sorted(temporadas.values(), key=lambda t: t["desde"], reverse=True)
    ediciones_con_datos = [n for _, n in reversed(EDICIONES) if any(t["edicion"] == n for t in temporadas_lista)]
    apariciones = []
    for j in js:
        for x in j["partidos"]:
            p, s = x["p"], x["s"]
            nota = s.get("rating")
            apariciones.append([j["id"], p["liga"], p["temporada"]["clave"], p["edicion"], s.get("goles") or 0,
                                s.get("asistencias") or 0, 1 if s.get("mvp") else 0,
                                nota if nota is not None and nota >= 0 else None,
                                s.get("posicion") or "", p["id"], 1 if jug_mod.valla_invicta(p, s) else 0,
                                s.get("amarillas") or 0, s.get("rojas") or 0])
        # Por temporada (ficha)
        por_t = {}
        for x in j["partidos"]:
            p, s = x["p"], x["s"]
            k = p["temporada"]["clave"]
            a = por_t.setdefault(k, {"nombre": p["temporada"]["nombre"], "liga_ui": p["liga_ui"], "edicion": p["edicion"],
                                     "desde": p["fecha_utc"], "pj": 0, "goles": 0, "asistencias": 0, "mvp": 0,
                                     "vallas": 0, "amarillas": 0, "rojas": 0, "notas": []})
            a["pj"] += 1; a["goles"] += s.get("goles") or 0; a["asistencias"] += s.get("asistencias") or 0
            a["mvp"] += 1 if s.get("mvp") else 0
            a["vallas"] += 1 if jug_mod.valla_invicta(p, s) else 0
            a["amarillas"] += s.get("amarillas") or 0
            a["rojas"] += s.get("rojas") or 0
            if s.get("rating") is not None and s["rating"] >= 0:
                a["notas"].append(s["rating"])
            a["desde"] = min(a["desde"], p["fecha_utc"])
        for a in por_t.values():
            a["nota"] = round(sum(a["notas"]) / len(a["notas"]), 1) if a["notas"] else None
        j["por_temporada"] = sorted(por_t.values(), key=lambda a: a["desde"], reverse=True)
    plantel_datos = {
        "jugadores": {j["id"]: {"alias": j["alias"], "dorsal": j["dorsal"], "pos": j["posicion"], "pagina": j["pagina"]} for j in js},
        "ap": apariciones,
        # Formación publicada por la liga en cada partido (solo VPN la publica; no se calcula)
        "form": {p["id"]: p["formacion"] for p in partidos if p.get("formacion")},
        "minimoNota": jug_mod.MIN_PJ_NOTA,
        "actuales": [t["id"] for t in tablas],  # temporada en curso de cada liga
        # "Alineación habitual" que el club carga en VPN: se usa en lugar del 11 calculado para VPN
        "oficial": oficial_vpn({jug_mod.clave(k): jug_mod.clave(v) for k, v in (ajustes.get("unir") or {}).items()}),
        "notaBase": jug_mod.NOTA_BASE, "pesoBase": jug_mod.PESO_BASE,
    }

    sync_txt = a_local(estado["sync"]).strftime("%d/%m a las %H:%M") if estado.get("sync") else "nunca"
    # Avisos: suspendidos y choques de horario
    sanciones = [s for k in ligas for s in leer(f"sanciones_{k}.json", [])]

    # Jugadores destacados: nuestros jugadores que aparecen en el top 5 que publica cada liga
    # (puesto y valor tal cual los muestra la liga; acá no se calcula nada)
    NOMBRE_TOP = {"goles": "Goleadores", "asistencias": "Asistencias", "nota": "Mejor valoración",
                  "vallas": "Vallas invictas", "vallas_def": "Vallas invictas (defensa)", "mvp": "MVP"}
    unir_alias = {jug_mod.clave(k): jug_mod.clave(v) for k, v in (ajustes.get("unir") or {}).items()}
    por_jugador = {}
    for k in ["vpn", "lva", "vpug"]:
        if k not in ligas:
            continue
        for d in leer(f"destacados_{k}.json", []):
            jid = unir_alias.get(jug_mod.clave(d["alias"]), jug_mod.clave(d["alias"]))
            j = {x["id"]: x for x in js}.get(jid)
            if d["stat"] == "vallas" and k == "vpn":
                d = {**d, "stat_txt": "Vallas invictas (arquero)"}
            fila = por_jugador.setdefault(jid, {"j": j or {"alias": d["alias"], "dorsal": None, "pagina": None}, "tops": []})
            # Temporada a la que corresponde el top (la más reciente de esa liga y competencia),
            # para mostrarlo solo cuando en el Plantel está elegida esa liga/temporada
            temp = next((p["temporada"]["clave"] for p in reversed(partidos) if p["liga"] == k
                         and p.get("temporada") and p.get("competencia") == d["competencia"]),
                        next((p["temporada"]["clave"] for p in reversed(partidos) if p["liga"] == k and p.get("temporada")), ""))
            fila["tops"].append({**d, "temp": temp, "liga_ui": ligas[k], "stat_txt": d.get("stat_txt") or NOMBRE_TOP.get(d["stat"], d["stat"])})
    destacados = sorted(por_jugador.values(), key=lambda f: (min(t["pos"] for t in f["tops"]), -len(f["tops"])))
    for f in destacados:
        f["tops"].sort(key=lambda t: t["pos"])
    for s in sanciones:
        s["liga_ui"] = ligas[s["liga"]]
    avisos = [{"tipo": "sancion", "liga_ui": s["liga_ui"], "titulo": f"{s['jugador']} no puede jugar",
               "detalle": f"{s['competencia']}" + (f", {s['cumple']}" if s.get("cumple") else "") + "."
                          + (f" Motivo: {s['motivo'][0].lower() + s['motivo'][1:]}." if s.get("motivo") else "")}
              for s in sanciones if s.get("vigente")]
    # Choques: partidos de ligas distintas a menos de 30 minutos; los encadenados van en un solo aviso
    grupo = []
    def cerrar_grupo():
        if len(grupo) > 1 and len({p["liga"] for p in grupo}) > 1:
            cuando = "hoy" if grupo[0]["noche"] == hoy_noche else f"el {grupo[0]['noche_txt']}"
            avisos.append({"tipo": "choque", "liga_ui": None, "titulo": f"Choque de horarios {cuando}",
                           "detalle": ", ".join(f"{p['hora']} {p['liga_ui']['corto']} vs {p['rival']['nombre']}" for p in grupo) + "."})
    for p in proximos:
        if grupo and (p["dt"] - grupo[-1]["dt"]).total_seconds() >= 30 * 60:
            cerrar_grupo(); grupo = []
        grupo.append(p)
    cerrar_grupo()
    for j in js:
        j["sanciones"] = [s for s in sanciones if jug_mod.clave(s["jugador"]) == j["id"]]

    # Cada sanción vigente se asigna al partido en que se cumple
    pagina_jugador = {j["id"]: j["pagina"] for j in js}
    ficha_de = {j["id"]: j for j in js}

    # Formación: VPN la publica en cada partido. La LVA y VPUG no la publican: se calcula con las
    # posiciones que carga esa misma liga, contando jugadores por línea (defensa, MCD, medio, MCO,
    # delanteros). Nunca se toma de otra liga. Si faltan posiciones, queda sin nombre.
    for p in partidos:
        if p["liga"] != "vpn" and not p.get("formacion"):
            p["formacion"] = formacion_por_lineas(p.get("stats", []))
    plantel_datos["form"] = {p["id"]: p["formacion"] for p in partidos if p.get("formacion")}
    for p in partidos:
        p["once"] = alineacion(p.get("stats", []), ficha_de) if p.get("resultado") else []
        for s in p.get("stats", []):
            s["pagina"] = (ficha_de.get(jug_mod.clave(s.get("alias", ""))) or {}).get("pagina")
    for p in partidos:
        p["sancionados"] = []
    for s in (x for x in sanciones if x.get("vigente")):
        destino = next((p for p in partidos if p["id"] == s.get("partido_id")), None)
        if not destino and s.get("cumple"):
            destino = next((p for p in proximos if p["liga"] == s["liga"] and p["competencia"] == s["competencia"]
                            and p["jornada"].lower() == s["cumple"].lower()), None)
        if not destino:
            destino = next((p for p in proximos if p["liga"] == s["liga"] and p["competencia"] == s["competencia"]), None)
        if destino:
            destino["sancionados"].append({**s, "pagina": pagina_jugador.get(jug_mod.clave(s["jugador"]))})

    # Forma reciente: últimos 5 resultados de Vultur en cada competencia
    forma = {}
    for p in sorted((x for x in partidos if x["resultado"]), key=lambda x: x["fecha_utc"]):
        forma.setdefault(p.get("competencia_id"), []).append(p)
    forma = {k: v[-5:] for k, v in forma.items()}
    for t in tablas:
        t["forma"] = forma.get(t["id"], [])

    # Récords del club (todo el historial; los W.O. cuentan como cualquier resultado)
    jugados_reales = sorted((p for p in partidos if p["resultado"]), key=lambda x: x["fecha_utc"])
    con_pj = [j for j in js if j["total"]["pj"]]
    records = {
        "pj": len(jugados_reales),
        "g": sum(p["resultado"] == "g" for p in jugados_reales),
        "e": sum(p["resultado"] == "e" for p in jugados_reales),
        "p": sum(p["resultado"] == "p" for p in jugados_reales),
        "gf": sum(p["gf"] for p in jugados_reales), "gc": sum(p["gc"] for p in jugados_reales),
        "goleada": max(jugados_reales, key=lambda p: (p["gf"] - p["gc"], p["gf"]), default=None),
        "derrota": min(jugados_reales, key=lambda p: (p["gf"] - p["gc"], -p["gc"]), default=None),
        "rachas": rachas(jugados_reales),
        "desde": jugados_reales[0]["noche_txt"] if jugados_reales else "",
        "anio_desde": jugados_reales[0]["noche"].year if jugados_reales else "",
        "goleador": max(con_pj, key=lambda j: (j["total"]["goles"], -j["total"]["pj"]), default=None),
        "asistidor": max(con_pj, key=lambda j: (j["total"]["asistencias"], -j["total"]["pj"]), default=None),
        "mas_pj": max(con_pj, key=lambda j: j["total"]["pj"], default=None),
        "mas_mvp": max(con_pj, key=lambda j: (j["total"]["mvp"], -j["total"]["pj"]), default=None),
        "mas_vallas": max(con_pj, key=lambda j: (j["total"]["vallas"], jug_mod.arquero(j), -j["total"]["pj"]), default=None),
        "vallas": sum(1 for p in jugados_reales if p["gc"] == 0),
    }

    # Previa de los partidos por jugar: forma en esa competencia y nuestro 11 más usado en ella
    once_por_comp = {}
    for p in partidos:
        if p["resultado"] is None:
            cid = p.get("competencia_id")
            if cid not in once_por_comp:
                de_comp = [x for x in partidos if x.get("competencia_id") == cid]
                ofi = plantel_datos.get("oficial")
                once_por_comp[cid] = (once_oficial(ofi, de_comp, ficha_de) if ofi and p["liga"] == "vpn"
                                      else once_mas_usado(de_comp, ficha_de))
            p["previa_once"] = once_por_comp[cid]
            p["forma_comp"] = forma.get(cid, [])

    transmisiones = cfg["club"].get("transmisiones") or []
    twitch_de = {jug_mod.clave(t["jugador"]): t["canal"] for t in transmisiones}
    for j in js:
        j["twitch"] = twitch_de.get(j["id"])
    # Rivales (historial contra cada uno en todas las ligas)
    aj_riv = yaml.safe_load((RAIZ / "config" / "rivales.yaml").read_text(encoding="utf-8")) or {}
    rivales = riv_mod.armar(partidos, aj_riv, DATOS / "escudos_huellas.json")
    lista_rivales = sorted(rivales.values(), key=lambda r: (-len(r["partidos"]), -r["pj"], r["nombre"].lower()))
    # Tablas: cada equipo enlaza al rival (incluye nombres unidos a mano o por escudo)
    unir_riv = {jug_mod.clave(n): k for k, r in rivales.items() for n in r["nombres"]}
    for t in tablas:
        for f in t["filas"]:
            k = unir_riv.get(jug_mod.clave(f["equipo"]), jug_mod.clave(f["equipo"]))
            f["pagina"] = rivales[k]["pagina"] if (not f["es_vultur"] and k in rivales) else None
    por_pagina = {r["pagina"]: r for r in rivales.values()}
    for p in partidos:
        p["rival_info"] = por_pagina.get(p.get("rival_pagina"))

    # Vista previa al compartir: los partidos de la próxima noche de juego
    noche_prox = [p for p in proximos if proximo and p["noche"] == proximo["noche"]]
    url_sitio = cfg["club"].get("url_sitio", "").rstrip("/") + "/"
    og_version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    if noche_prox:
        og_desc = ("Hoy jugamos: " if noche_prox[0]["noche"] == hoy_noche else f"Próximo: {noche_prox[0]['noche_txt']}: ") +                   "; ".join(f"{p['hora']} vs {p['rival']['nombre']} ({p['liga_ui']['corto']})" for p in noche_prox)
    else:
        og_desc = "Partidos, tablas y plantel de Vultur Sports en todas sus competencias."

    # v: versión de css/js, cambia en cada actualización para que el navegador no use copias viejas
    # Vitrina: títulos detectados en las ligas + los cargados a mano
    titulos = []
    for k in ligas:
        for t in leer(f"titulos_{k}.json", []):
            titulos.append({**t, "liga_ui": ligas.get(t.get("liga")), "organiza": ligas[t["liga"]]["nombre"] if t.get("liga") in ligas else ""})
    manual = yaml.safe_load((RAIZ / "config" / "titulos.yaml").read_text(encoding="utf-8")) or {}
    for t in manual.get("titulos") or []:
        titulos.append({"nombre": t.get("nombre", "Título"), "fecha": str(t.get("fecha") or ""), "organiza": t.get("organiza", ""),
                        "nota": t.get("nota"), "liga_ui": None})
    titulos.sort(key=lambda t: t.get("fecha") or "", reverse=True)
    vpn_hist = leer("raw/vpn/temporadas.json", {})
    mejor_vpn = next((h for h in vpn_hist.get("highlights", []) if h.get("key") == "best"), None)
    datos_estante = {
        "vpn": (f"Mejor puesto: {mejor_vpn['value']} en " + mejor_vpn["hint"].replace("Liga Argentina ", "").replace(" · ", " (") + ")")
               if mejor_vpn and mejor_vpn.get("hint") else "",
        "lva": f"{len({p.get('competencia_id') for p in partidos if p['liga'] == 'lva'})} torneos jugados",
        "vpug": "Primera temporada en curso",
    }
    estantes = [{"liga": l, "dato": datos_estante.get(k, ""), "reservado": i == 0} for i, (k, l) in enumerate(ligas.items())]

    # Página de estado
    estado_ligas = []
    for k, l in ligas.items():
        e = (estado.get("ligas") or {}).get(k, {})
        ok = a_local(e["ok"]) if e.get("ok") else None
        estado_ligas.append({"liga_ui": l, "error": e.get("error"), "fallos": e.get("fallos_seguidos", 0),
                             "ok_txt": ok.strftime("%d/%m/%Y %H:%M") if ok else None,
                             "ok_reciente": bool(ok) and (ahora - ok) < timedelta(hours=12),
                             "partidos": sum(1 for p in partidos if p["liga"] == k)})

    # Franja "Hoy jugamos" (todas las páginas): próximos partidos; el navegador muestra los de hoy
    hoy_datos = [{"inicio": p["dt"].isoformat(), "fin": p["fin_tarjeta"].isoformat(), "noche": p["noche"].isoformat(),
                  "hora": p["hora"], "rival": p["rival"]["nombre"], "liga": p["liga_ui"]["corto"], "pagina": p["pagina"]}
                 for p in proximos[:10]]
    # Calendario en vista de mes (computadora)
    cal_datos = [{"noche": p["noche"].isoformat(), "hora": p["hora"], "rival": p["rival"]["nombre"], "liga": p["liga"],
                  "corto": p["liga_ui"]["corto"], "pagina": p["pagina"], "escudo": p["rival"].get("escudo"),
                  "res": p["resultado"], "gf": p.get("gf"), "gc": p.get("gc"), "inicio": p["dt"].isoformat()}
                 for p in sorted(partidos, key=lambda p: p["dt"])]
    ctx = dict(club=cfg["club"]["nombre"], hoy_datos=hoy_datos, cal_datos=cal_datos, redes_club=[(REDES_TXT.get(k, k), k, u) for k, u in (cfg["club"].get("redes") or {}).items()], v=og_version, destacados=destacados, tarjetas=tarjetas, ahora=ahora, records=records, estado_ligas=estado_ligas,
               titulos=titulos, estantes=estantes,
               total_partidos=len(partidos), total_jugadores=len(js), total_rivales=len(rivales),
               total_escudos=len(list((DATOS / "escudos").glob("*.webp"))), plantel_datos=plantel_datos, temporadas_lista=temporadas_lista,
               ediciones_con_datos=ediciones_con_datos, edicion_actual=edicion_actual, transmisiones=transmisiones, avisos=avisos,
               lista_rivales=lista_rivales,
               og_imagen=f"{url_sitio}og.png?v={og_version}", og_desc=og_desc, url_sitio=url_sitio, ligas=ligas, tablas=tablas, proximo=proximo,
               semana=agrupar(semana), recientes=jugados[:5],
               cal_proximos=agrupar(proximos), cal_jugados=agrupar(cal_jugados),
               sync_txt=sync_txt, hoy_noche=hoy_noche,
               ambitos=ambitos, sin_partidos=sin_partidos,
               ligas_en_uso=[l for l in ligas.values() if any(p["liga"] == l["clave"] for p in partidos)])

    env = Environment(loader=FileSystemLoader(RAIZ / "plantillas"), autoescape=select_autoescape())
    SITE.mkdir(exist_ok=True)
    for viejo in SITE.iterdir():  # vaciar sin borrar la carpeta (en Windows puede estar en uso)
        shutil.rmtree(viejo) if viejo.is_dir() else viejo.unlink()
    shutil.copytree(RAIZ / "estaticos", SITE / "estaticos")
    if (DATOS / "escudos").exists():
        shutil.copytree(DATOS / "escudos", SITE / "escudos", ignore=shutil.ignore_patterns("*.json"))
    def escribir(ruta, html):  # direcciones limpias: /plantel/ -> plantel/index.html
        destino = SITE / ruta.strip("/") / "index.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(html, encoding="utf-8")
    for ruta, pagina in [("/", "inicio.html"), ("/calendario/", "calendario.html"),
                         ("/tablas/", "tablas.html"), ("/plantel/", "plantel.html"),
                         ("/estado/", "estado.html"), ("/vitrina/", "vitrina.html")]:
        escribir(ruta, env.get_template(pagina).render(pagina=ruta, **ctx))
    tpl = env.get_template("partido.html")
    for p in partidos:
        escribir(p["pagina"], tpl.render(pagina=p["pagina"], p=p, **ctx))
    tpl = env.get_template("rival.html")
    for r in rivales.values():
        escribir(r["pagina"], tpl.render(pagina=r["pagina"], r=r, **ctx))
    tpl = env.get_template("jugador.html")
    for j in js:
        escribir(j["pagina"], tpl.render(pagina=j["pagina"], j=j, **ctx))
    # Página de error; además lleva las direcciones viejas (calendario.html, jugador-x.html...) a las nuevas
    (SITE / "404.html").write_text(env.get_template("404.html").render(pagina="/404", **ctx), encoding="utf-8")
    (SITE / "calendario.ics").write_text(generar_ics(partidos, ctx["club"]), encoding="utf-8", newline="")
    for p in noche_prox:
        p["rival"]["escudo_grande"] = p["rival"].get("escudo_archivo") or p["rival"].get("escudo_url")
    og.generar(noche_prox, bool(noche_prox) and noche_prox[0]["noche"] == hoy_noche,
               {k: str(RAIZ / "estaticos" / "img" / "ligas" / f"{k}.png") for k in ligas}, SITE / "og.png")
    (SITE / ".nojekyll").write_text("")
    # Buscador: jugadores y rivales (se descarga solo al abrir la búsqueda)
    (SITE / "buscar.json").write_text(json.dumps(
        [{"n": j["alias"], "t": "Jugador", "u": j["pagina"]} for j in js]
        + [{"n": r["nombre"], "t": "Rival", "u": r["pagina"], "o": [x for x in r.get("nombres", {}) if x != r["nombre"]]}
           for r in rivales.values()], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # Mapa del sitio para buscadores (Google)
    rutas = (["/", "/calendario/", "/tablas/", "/plantel/", "/vitrina/"] + [p["pagina"] for p in partidos]
             + [r["pagina"] for r in rivales.values()] + [j["pagina"] for j in js])
    base = url_sitio.rstrip("/")
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{base}{escape(r)}</loc></url>\n" for r in rutas) + "</urlset>\n", encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    print(f"site/ generado: {len(partidos)} partidos, {len(tablas)} tablas, {len(con_pj)} jugadores con partidos")


if __name__ == "__main__":
    main()
