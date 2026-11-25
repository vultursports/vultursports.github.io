"""Genera una versión de PRUEBA del sitio en site-demo/ con sanciones y un choque de horarios
inventados, para ver cómo se ven los avisos. No toca datos/ ni site/.

Uso:  python herramientas/demo_sanciones.py   y abrir site-demo/index.html con un servidor local.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import build  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="vultur-demo-"))
shutil.copytree(RAIZ / "datos", tmp / "datos")
d = tmp / "datos"

# Sanciones inventadas
(d / "sanciones_lva.json").write_text(json.dumps([{
    "liga": "lva", "competencia": "1ra Div - Legacy", "jugador": "Corona_ruso",
    "motivo": "Expulsión directa (tarjeta roja)", "fechas": 1, "cumple": "Fecha 16", "vigente": True,
}], ensure_ascii=False), encoding="utf-8")
(d / "sanciones_vpn.json").write_text(json.dumps([{
    "liga": "vpn", "competencia": "Liga Argentina 4ta División (Grupo A)", "jugador": "Zk__godd",
    "motivo": "No habilitado para este partido", "cumple": "Jornada 10 vs Arabia Team", "vigente": True,
}], ensure_ascii=False), encoding="utf-8")

# Choque de horarios inventado: un partido de VPN movido a las 22:40 de hoy (01:40 UTC)
ps = json.loads((d / "partidos.json").read_text(encoding="utf-8"))
vpug_hoy = next(p for p in ps if p["liga"] == "vpug" and p["estado"] == "programado")
vpn_prox = next(p for p in ps if p["liga"] == "vpn" and p["estado"] == "programado")
vpn_prox["fecha_utc"] = vpug_hoy["fecha_utc"].replace(":30:00", ":40:00")
ps.sort(key=lambda p: p["fecha_utc"])
(d / "partidos.json").write_text(json.dumps(ps, ensure_ascii=False), encoding="utf-8")

build.DATOS = d
build.SITE = RAIZ / "site-demo"
build.main()
shutil.rmtree(tmp, ignore_errors=True)
print("Demo lista en site-demo/")
