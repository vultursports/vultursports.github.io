"""Pruebas automáticas. Uso:  python -m unittest discover -s tests -v

Cubren lo que más fácil se rompe: la lectura de los datos de cada liga, la unión de jugadores y
rivales, las correcciones de posiciones y que la web completa se genere sin errores.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import build  # noqa: E402
import jugadores  # noqa: E402
import rivales  # noqa: E402
import sync  # noqa: E402
from conectores import lva, vpn, vpug  # noqa: E402

LIGAS = {k: {"corto": k.upper(), "nombre": k, "clave": k} for k in ("vpn", "lva", "vpug")}


class LecturaVPN(unittest.TestCase):
    def test_temporada_corta(self):
        self.assertEqual(vpn._corto("Temporada 11"), "T11")

    def test_estadisticas_de_jugador(self):
        j = {"userId": 1, "name": " VSP-Ch4cKaL ", "position": {"code": "DD"}, "motm": True,
             "stats": {"1": 2, "2": 1, "5": 1}, "ea": {"rating": 8.1}}
        s = vpn._stat_jugador(j)
        self.assertEqual((s["alias"], s["goles"], s["asistencias"], s["amarillas"], s["mvp"], s["rating"]),
                         ("VSP-Ch4cKaL", 2, 1, 1, True, 8.1))

    def test_formacion_publicada(self):
        self.assertEqual(vpn._formacion({"report": {"formation": {"name": "4-1-2-1-2"}}}), "4-1-2-1-2")
        self.assertIsNone(vpn._formacion({}))


class LecturaLVA(unittest.TestCase):
    def test_torneo_desde_url(self):
        self.assertEqual(lva._torneo_de("https://x/rest/v1/matches?select=*&tournament_id=eq.abc-123"), "abc-123")

    def test_tabla(self):
        filas = [{"celdas": ["1", "Deportivo Centro", "14", "11", "2", "1", "29", "10", "+19", "35"], "escudo": None},
                 {"celdas": ["14", "Vultur Sports", "15", "4", "3", "8", "12", "22", "-10", "15"], "escudo": None}]
        t = lva._tabla("ecfa9127-xxxx", "1ra DiV - Legacy", filas, "vultur sports")
        self.assertEqual(t["competencia"], "1ra Div - Legacy")
        v = t["filas"][1]
        self.assertEqual((v["pos"], v["pts"], v["dg"], v["es_vultur"]), (14, 15, -10, True))


class LecturaVPUG(unittest.TestCase):
    def test_estadisticas_y_figura(self):
        j = {"id": 7, "idExterno": "Corona_ruso ", "nombre": "Matías", "posicion": "DFC", "goles": 1, "nota": 7.6}
        self.assertTrue(vpug._stat(j, 7)["mvp"])
        self.assertEqual(vpug._stat(j, 8)["alias"], "Corona_ruso")


class UnionDeNombres(unittest.TestCase):
    def test_clave_ignora_mayusculas_signos_y_acentos(self):
        self.assertEqual(jugadores.clave("VSP-Ch4cKaL"), jugadores.clave("VSP-ch4cKaL"))
        self.assertEqual(jugadores.clave("Fc Echeverría"), jugadores.clave("Fc Echeverria"))

    def test_rivales(self):
        self.assertTrue(rivales._puede_unir({"San Miguel eSports"}, {"San Miguel eSp"}, 111))   # mismo club, escudo rediseñado
        self.assertFalse(rivales._puede_unir({"Instituto Reserva"}, {"Instituto Senior"}, 26))  # reserva: nunca
        self.assertFalse(rivales._puede_unir({"Tu Vieja Crew"}, {"Emporio Zamudio"}, 9))       # nombres sin relación
        self.assertFalse(rivales._puede_unir({"Talleres Esports"}, {"Talleres Reserva"}, 10))


class Posiciones(unittest.TestCase):
    def partido(self, formacion, posiciones, liga="vpn"):
        return {"id": "x", "liga": liga, "competencia": "c", "jornada": "Fecha 1", "fecha_utc": "2026-11-19T02:00:00Z",
                "local": True, "rival": {"nombre": "R"}, "gf": 1, "gc": 0, "estado": "finalizado", "formacion": formacion,
                "stats": [{"alias": f"j{i}", "posicion": q} for i, q in enumerate(posiciones)]}

    def test_correcciones_vpn(self):
        p = build.preparar_partido(self.partido("4-1-2-1-2", ["PO", "LTD", "DFC", "DFC", "LTI", "MCD", "MD", "MI", "MCO", "DD", "DI"]), LIGAS)
        pos = sorted(s["posicion"] for s in p["stats"])
        self.assertEqual(pos.count("MC"), 2)   # MD/MI -> MC en la 4-1-2-1-2
        self.assertEqual(pos.count("DC"), 2)   # DD/DI -> DC con dos puntas

    def test_tres_delanteros_se_respetan(self):
        p = build.preparar_partido(self.partido("4-3-2-1", ["PO", "DFC", "DFC", "LTD", "LTI", "MCD", "MC", "MC", "DD", "DI", "DC"]), LIGAS)
        self.assertIn("DD", [s["posicion"] for s in p["stats"]])

    def test_alineacion_ubica_en_la_cancha(self):
        stats = [{"alias": "a", "posicion": "POR"}, {"alias": "b", "posicion": "DFC"}, {"alias": "c", "posicion": "DFC"}]
        xs = {x["alias"]: x for x in build.alineacion(stats, {})}
        self.assertGreater(xs["a"]["y"], xs["b"]["y"])          # el arquero abajo
        self.assertNotEqual(xs["b"]["x"], xs["c"]["x"])         # dos centrales separados


class Movimientos(unittest.TestCase):
    def test_vpn_usa_posicion_anterior_del_grupo(self):
        tablas = {"t": {"id": "t", "filas": [
            {"equipo": "A", "pos": 1, "pos_fuente": 1, "pos_ant_fuente": 2},
            {"equipo": "B", "pos": 2, "pos_fuente": 2, "pos_ant_fuente": 1}]}}
        hist = sync.DATOS / "historial_posiciones.json"
        antes = hist.read_text(encoding="utf-8") if hist.exists() else None
        try:
            sync.calcular_movimientos(tablas)
        finally:
            if antes is not None:
                hist.write_text(antes, encoding="utf-8")
        self.assertEqual([f["mov"] for f in tablas["t"]["filas"]], [1, -1])


class GenerarWeb(unittest.TestCase):
    def test_la_web_se_genera_completa(self):
        if not (RAIZ / "datos" / "partidos.json").exists():
            self.skipTest("todavía no hay datos")
        destino = Path(tempfile.mkdtemp(prefix="vultur-test-"))
        original = build.SITE
        try:
            build.SITE = destino
            build.main()
            for pagina in ("index.html", "calendario/index.html", "tablas/index.html", "plantel/index.html", "vitrina/index.html",
                           "estado/index.html", "404.html", "og.png"):
                self.assertTrue((destino / pagina).exists(), pagina)
            datos = (destino / "plantel" / "index.html").read_text(encoding="utf-8")
            self.assertIn('id="datos-plantel"', datos)
        finally:
            build.SITE = original
            shutil.rmtree(destino, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
