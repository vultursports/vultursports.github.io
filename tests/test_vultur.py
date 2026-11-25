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

    def test_flechas_quedan_hasta_la_fecha_siguiente(self):
        hist = sync.DATOS / "historial_posiciones.json"
        antes = hist.read_text(encoding="utf-8") if hist.exists() else None
        fila = lambda e, pos, pj: {"equipo": e, "pos": pos, "pj": pj}
        try:
            sync.escribir("historial_posiciones.json", {"t": {
                "2000-01-01": {"pos": {"a": 2, "b": 1}, "pj_max": 3},   # antes de la fecha 4
                "2000-01-02": {"pos": {"a": 1, "b": 2}, "pj_max": 4},   # se jugó la fecha 4
            }})
            tablas = {"t": {"id": "t", "filas": [fila("A", 1, 4), fila("B", 2, 4)]}}  # hoy no se jugó nada
            sync.calcular_movimientos(tablas)
        finally:
            if antes is not None:
                hist.write_text(antes, encoding="utf-8")
        self.assertEqual([f["mov"] for f in tablas["t"]["filas"]], [1, -1])


class DatosEA(unittest.TestCase):
    """EA solo completa partidos de nuestras competencias: misma hora, mismo marcador, rival parecido."""

    def ea(self, mid, fecha, rival, gf, gc):
        return {"id": mid, "fecha_utc": fecha, "gf": gf, "gc": gc, "rival": {"nombre": rival}, "jugadores": []}

    def liga(self, pid, fecha, rival, gf, gc, **extra):
        return {"id": pid, "fecha_utc": fecha, "rival": {"nombre": rival}, "gf": gf, "gc": gc, **extra}

    def test_reinicio_y_resultado_tecnico(self):
        """Se salen todos para reiniciar: EA registra el intento cortado y el partido real con 3-0 técnico."""
        from conectores import ea
        p = [self.liga("m", "2026-11-20T02:00:00Z", "MARPLA FC", 0, 0)]
        corto = {**self.ea("1", "2026-11-20T02:06:17Z", "Marpla FC", 0, 3), "goles_jugadores": [0, 0], "minutos": 2}
        real = {**self.ea("2", "2026-11-20T02:27:10Z", "Marpla FC", 0, 3), "goles_jugadores": [0, 0], "minutos": 92}
        u = ea.unir(p, {"1": corto, "2": real})
        self.assertEqual(u["m"]["id"], "2")
        # Reinicio después de 30 minutos y la liga con otro resultado: vale el último intento completo
        r1 = {**self.ea("3", "2026-11-21T02:35:00Z", "Rival", 1, 0), "goles_jugadores": [1, 0], "minutos": 35}
        r2 = {**self.ea("4", "2026-11-21T02:58:00Z", "Rival", 2, 2), "goles_jugadores": [2, 2], "minutos": 92}
        p3 = [self.liga("r", "2026-11-21T02:00:00Z", "Rival", 0, 3)]  # la liga sancionó
        self.assertEqual(ea.unir(p3, {"3": r1, "4": r2})["r"]["id"], "4")
        # Un solo partido con otro marcador (sanción, como Villa San Carlos): no se une
        self.assertEqual(ea.unir(p3, {"4": r2}), {})
        # EA no guardó nuestras estadísticas (todos con 0 pases en 90 minutos): datos descartados
        jug = lambda pases: [{"pases_int": pases, "segundos": 5500}]
        self.assertFalse(ea.datos_completos({"jugadores": jug(10) + jug(0) * 10}))
        self.assertTrue(ea.datos_completos({"jugadores": jug(10) * 10 + jug(0)}))
        # Sin resultado de la liga y con marcador dudoso: no hay resultado provisorio
        p2 = [self.liga("n", "2026-11-20T02:00:00Z", "MARPLA FC", None, None)]
        self.assertEqual(ea.unir(p2, {"2": real}), {})

    def test_goles_perdidos_de_un_expulsado(self):
        """Al goleador lo sacaron del lobby al final: EA dejó su registro vacío y perdió sus goles,
        pero los rivales tienen los goles recibidos."""
        from conectores import ea
        fumeta = {**self.ea("1", "2026-11-25T01:59:30Z", "DeportivoFumeta", 3, 0), "goles_jugadores": [0, 0],
                  "goles_recibidos": [3, 0]}
        self.assertEqual(ea.marcador_seguro(fumeta), (3, 0))
        p = [self.liga("f", "2026-11-25T01:30:00Z", "DeportivoFumeta", None, None)]
        self.assertEqual(ea.unir(p, {"1": fumeta})["f"]["id"], "1")  # resultado provisorio
        # 3-0 técnico falso (fue 0-0, AllBoysCantera): nadie recibió goles, no se acepta
        allboys = {**self.ea("2", "2026-11-24T01:53:56Z", "AllBoysCantera", 3, 0), "goles_jugadores": [0, 0],
                   "goles_recibidos": [0, 0]}
        self.assertIsNone(ea.marcador_seguro(allboys))
        # Partido guardado antes de existir el dato: se sigue exigiendo que coincidan los goles de los jugadores
        self.assertIsNone(ea.marcador_seguro({**fumeta, "goles_recibidos": None}))

    def test_goles_recibidos_desde_ea(self):
        from conectores import ea
        jug = lambda n, recib, seg=5600: {f"p{n}{k}": {"playername": f"j{k}", "goalsconceded": str(recib), "goals": "0",
                                                       "secondsPlayed": str(seg), "rating": "7"} for k in range(3)}
        crudo = {"matchId": 9, "timestamp": 1795571970,
                 "clubs": {"1": {"goals": "3"}, "2": {"goals": "0", "details": {"name": "Rival"}}},
                 "players": {"1": {**jug("a", 0), "vacio": {"playername": "x", "goalsconceded": "0", "secondsPlayed": "0", "rating": "3.00"}},
                             "2": {**jug("b", 3), "suplente": {"playername": "s", "goalsconceded": "1", "secondsPlayed": "900", "rating": "6"}}}}
        n = ea.normalizar(crudo, "1")
        self.assertEqual(n["goles_recibidos"], [3, 0])  # el máximo: un suplente que entró tarde recibió menos
        self.assertEqual(ea.marcador_seguro(n), (3, 0))

    def test_nombres_parecidos(self):
        from conectores import ea
        self.assertEqual(ea.parecido("BOCA   JUNIORS", "BOCA JUNIORS"), 1.0)
        self.assertGreaterEqual(ea.parecido("ESPANYOL FC", "Espanyol Barcelona fc"), 0.9)
        self.assertLess(ea.parecido("Marpla FC", "Motor Psico"), 0.6)

    def test_union(self):
        from conectores import ea
        partidos = [self.liga("a", "2026-11-19T02:00:00Z", "Real Envido", 2, 0),
                    self.liga("b", "2026-11-19T02:30:00Z", "Espanyol Barcelona fc", 1, 0),
                    self.liga("c", "2026-11-20T02:00:00Z", "MARPLA FC", 0, 0),        # EA dice 0-3: no se une
                    self.liga("d", "2026-11-21T02:00:00Z", "LMJ eSports", None, None),  # sin resultado: provisorio
                    self.liga("e", "2026-11-22T02:00:00Z", "Otro", 3, 0, estado="wo")]  # W.O.: no se jugó
        eas = {m["id"]: m for m in [
            self.ea("1", "2026-11-19T02:23:13Z", "Real Envido", 2, 0),
            self.ea("2", "2026-11-19T02:50:54Z", "ESPANYOL FC", 1, 0),
            self.ea("3", "2026-11-20T02:06:17Z", "Marpla FC", 0, 3),
            self.ea("4", "2026-11-21T02:20:00Z", "LMJ eSports", 4, 1),
            self.ea("5", "2026-11-22T02:20:00Z", "Otro", 3, 0),
            self.ea("6", "2026-11-19T05:00:00Z", "Real Envido", 2, 0)]}  # fuera de horario
        u = ea.unir(partidos, eas)
        self.assertEqual({k: m["id"] for k, m in u.items()}, {"a": "1", "b": "2", "d": "4"})



class PrecisionSeApaga(unittest.TestCase):
    """Si EA deja de dar datos, la sección Precisión desaparece sola (no queda congelada)."""

    def jugador(self, con_ea):  # con_ea: índices (0 = más reciente) de los partidos con datos de EA
        ea = {"tiros": 2, "pases": 10, "pases_int": 12, "entradas": 1, "entradas_int": 3, "atajadas": 0}
        return {"partidos": [{"p": {"resultado": "g"}, "s": {"goles": 1, **({"ea": ea} if i in con_ea else {})}}
                             for i in range(30)]}

    def test_con_datos_recientes(self):
        j = self.jugador({0, 1, 2, 3})
        build.ficha_ea(j)
        self.assertEqual(j["precision"]["pj"], 4)

    def test_api_vencida(self):
        j = self.jugador(set(range(10, 30)))  # los últimos 10 partidos ya no tienen datos de EA
        build.ficha_ea(j)
        self.assertNotIn("precision", j)

    def test_pocos_datos(self):
        j = self.jugador({0, 1})
        build.ficha_ea(j)
        self.assertNotIn("precision", j)


class Extras(unittest.TestCase):
    """Jugador de la noche, hitos y récords: lo actual se apaga solo, lo histórico queda."""

    def partido(self, pid, noche, stats, gf=1, gc=0):
        from datetime import date
        n = date.fromisoformat(noche)
        return {"id": pid, "fecha_utc": f"{noche}T02:00:00Z", "noche": n, "noche_txt": noche, "resultado": "g" if gf > gc else "p",
                "gf": gf, "gc": gc, "rival": {"nombre": "X"}, "stats": stats}

    def stats(self, notas, goles=None):
        base = [{"alias": f"j{i}", "rating": 6.0, "goles": 0} for i in range(7)]
        for i, n in enumerate(notas):
            base[i]["rating"] = n
        for i, g in (goles or {}).items():
            base[i]["goles"] = g
        return base

    def test_hitos_y_records(self):
        import extras
        j = {"partidos": [{"p": self.partido(str(i), "2026-11-20", []), "s": {"goles": 1}} for i in range(10)]}
        self.assertEqual([h["txt"] for h in extras.hitos(j)], ["10 goles"])
        ps = [self.partido("a", "2026-11-20", self.stats([], {0: 3})), self.partido("b", "2026-11-21", self.stats([], {1: 3}))]
        r = {x["titulo"]: x for x in extras.records_partido(ps, lambda a: a)}
        self.assertEqual(r["Más goles en un partido"]["id"], "j0")  # en empate, el primero que lo logró


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
