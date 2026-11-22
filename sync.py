"""Baja los datos públicos de cada liga activa y los guarda normalizados en datos/.

Uso:  python sync.py
Si una liga falla, se conservan sus datos anteriores y el error queda en datos/estado.json.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

import yaml

from conectores import lva, vpn, vpug
from conectores.base import ahora_iso

RAIZ = Path(__file__).resolve().parent
DATOS = RAIZ / "datos"
CONECTORES = {"lva": lva, "vpn": vpn, "vpug": vpug}


def leer(nombre, defecto):
    f = DATOS / nombre
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else defecto


def escribir(nombre, datos):
    DATOS.mkdir(exist_ok=True)
    (DATOS / nombre).write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def cargar_env() -> None:
    """Lee .env (solo en la PC). En GitHub las variables vienen de los secretos del repo."""
    f = RAIZ / ".env"
    if not f.exists():
        return
    for linea in f.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def calcular_movimientos(tablas: dict) -> None:
    """Agrega a cada fila "mov": cuántos puestos subió (+) o bajó (-) con la última fecha jugada.
    Las flechas quedan hasta que se juega la fecha siguiente (como en VPN).
    VPN publica la posición anterior; para las otras ligas se guarda una foto de la tabla por noche
    (posiciones y partidos jugados) y se compara con la última foto de antes de la fecha actual,
    es decir, la última en la que el máximo de partidos jugados era menor que ahora."""
    import re
    from datetime import datetime, timedelta, timezone
    hist = leer("historial_posiciones.json", {})
    noche = (datetime.now(timezone(timedelta(hours=-3))) - timedelta(hours=6)).date().isoformat()
    clave = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    for t in tablas.values():
        filas = t.get("filas", [])
        if filas and all(f.get("pos_ant_fuente") for f in filas):
            for f in filas:
                f["mov"] = f["pos_ant_fuente"] - f["pos_fuente"]
            continue
        fotos = hist.setdefault(t["id"], {})
        actual = {clave(f["equipo"]): f["pos"] for f in filas}
        pj_max = max((f.get("pj") or 0 for f in filas), default=0)
        fotos[noche] = {"pos": actual, "pj_max": pj_max}
        anteriores = [n for n in sorted(fotos) if n < noche]
        # Foto de antes de la fecha actual; las fotos viejas (sin pj_max) sirven si la tabla era distinta
        base, base_n = {}, None
        for n in reversed(anteriores):
            foto = fotos[n]
            pos = foto.get("pos", foto) if isinstance(foto, dict) else {}
            if ("pj_max" in foto and foto["pj_max"] < pj_max) or ("pj_max" not in foto and pos != actual):
                base, base_n = pos, n
                break
        for f in filas:
            ant = base.get(clave(f["equipo"]))
            f["mov"] = (ant - f["pos"]) if ant else None
        # Guardar las últimas 30 noches, sin borrar nunca la foto que se está usando como base
        for n in sorted(fotos)[:-30]:
            if n != base_n:
                del fotos[n]
    escribir("historial_posiciones.json", hist)


def main() -> int:
    cargar_env()
    cfg = yaml.safe_load((RAIZ / "config" / "ligas.yaml").read_text(encoding="utf-8"))
    partidos = {p["id"]: p for p in leer("partidos.json", [])}
    tablas = {t["id"]: t for t in leer("tablas.json", [])}
    rankings = {r["id"]: r for r in leer("rankings.json", [])}
    carga = leer("carga_resultados.json", [])
    estado = leer("estado.json", {"ligas": {}})

    for clave, lcfg in cfg["ligas"].items():
        mod = CONECTORES.get(clave)
        if not lcfg.get("activa") or not mod:
            continue
        print(f"→ {clave}")
        e = estado["ligas"].setdefault(clave, {})
        e["intento"] = ahora_iso()
        try:
            previos = {k: v for k, v in partidos.items() if v["liga"] == clave}
            out = mod.sincronizar(lcfg, cfg["club"], previos)
            # Protección: si una liga devuelve de golpe muchos menos partidos (por ejemplo, porque
            # cambió su web), no se pisan los datos buenos y queda marcado como falla.
            if len(previos) > 10 and len(out["partidos"]) < len(previos) * 0.5:
                raise RuntimeError(f"devolvió {len(out['partidos'])} partidos y antes había {len(previos)}: "
                                   "se conservan los datos anteriores")
            # Reemplaza lo de esta liga (los partidos que desaparecen de la fuente se conservan).
            for p in out["partidos"]:
                previo = partidos.get(p["id"])
                # Registro de cuándo carga la liga cada resultado (para ajustar el horario del robot)
                if previo and previo.get("gf") is None and p.get("gf") is not None:
                    carga.append({"liga": clave, "partido": p["id"], "rival": p["rival"]["nombre"],
                                  "jugado": p["fecha_utc"], "detectado": ahora_iso()})
                partidos[p["id"]] = p
            for t in out["tablas"]:
                t["actualizado"] = ahora_iso()
                tablas[t["id"]] = t
            # Torneos terminados: si la liga dejó de publicar una tabla y no nos quedan partidos por
            # jugar en ese torneo, la tabla se quita (los partidos y estadísticas quedan en el historial).
            publicadas = {t["id"] for t in out["tablas"]}
            pendientes = {p.get("competencia_id") for p in partidos.values()
                          if p["liga"] == clave and p.get("gf") is None and p.get("competencia_id")}
            for tid in [k for k, t in tablas.items() if t.get("liga") == clave and k not in publicadas and k not in pendientes]:
                print(f"  tabla terminada, se quita: {tablas[tid].get('competencia')}")
                del tablas[tid]
            if "titulos" in out:
                escribir(f"titulos_{clave}.json", out["titulos"])
            if "sanciones" in out:
                escribir(f"sanciones_{clave}.json", out["sanciones"])
            if "destacados" in out:
                escribir(f"destacados_{clave}.json", out["destacados"])
            if "alineacion" in out:
                escribir(f"alineacion_{clave}.json", out["alineacion"])
            if out.get("plantel"):
                escribir(f"plantel_{clave}.json", out["plantel"])
            if out.get("rankings"):
                rankings[out["rankings"]["id"]] = out["rankings"]
            e.update(ok=ahora_iso(), error=None, fallos_seguidos=0,
                     partidos=len(out["partidos"]), tablas=len(out["tablas"]))
            print(f"  ok: {len(out['partidos'])} partidos, {len(out['tablas'])} tablas")
        except Exception as ex:  # una liga caída no frena a las demás
            traceback.print_exc()
            e.update(error=str(ex)[:300], fallos_seguidos=e.get("fallos_seguidos", 0) + 1)

    # Partidos cargados a mano (opcional)
    manual = RAIZ / "datos" / "manual" / "partidos.yaml"
    if manual.exists():
        for p in yaml.safe_load(manual.read_text(encoding="utf-8")) or []:
            p.setdefault("stats", [])
            p["manual"] = True
            partidos[p["id"]] = p

    calcular_movimientos(tablas)
    escribir("partidos.json", sorted(partidos.values(), key=lambda p: p["fecha_utc"]))
    escribir("tablas.json", list(tablas.values()))
    escribir("rankings.json", list(rankings.values()))
    escribir("carga_resultados.json", carga)
    estado["sync"] = ahora_iso()
    escribir("estado.json", estado)
    return 0


if __name__ == "__main__":
    sys.exit(main())
