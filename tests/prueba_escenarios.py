"""Escenarios: simula cambios que pueden pasar en las ligas y genera la web completa con cada uno.

Cada prueba copia datos/ a una carpeta temporal, cambia lo que haría la liga (un W.O., un jugador
nuevo en un top, una posición nueva, una liga caída, etc.) y comprueba que la web se genere sola y
muestre lo nuevo, sin que nadie tenga que tocar nada.
Uso:  python -m unittest discover -s tests -p "prueba_*.py" -v
(No frenan la publicación: corren aparte, cada vez que cambia el código.)
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import build  # noqa: E402
import sync  # noqa: E402

AR = timezone(timedelta(hours=-3))
HAY_DATOS = (RAIZ / "datos" / "partidos.json").exists()


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Escenario:
    """Copia de datos/ en una carpeta temporal, con la hora que se quiera."""

    def __init__(self, ahora=None):
        self.ahora = ahora

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vultur-esc-"))
        self.datos = self.tmp / "datos"
        shutil.copytree(RAIZ / "datos", self.datos, ignore=shutil.ignore_patterns("raw"))
        if (RAIZ / "datos" / "raw").exists():
            shutil.copytree(RAIZ / "datos" / "raw", self.datos / "raw")
        self.site = self.tmp / "site"
        self.parches = [mock.patch.object(build, "DATOS", self.datos), mock.patch.object(build, "SITE", self.site),
                        mock.patch.object(sync, "DATOS", self.datos)]
        if self.ahora:
            ahora = self.ahora

            class Falso(datetime):
                @classmethod
                def now(cls, tz=None):
                    return ahora.astimezone(tz) if tz else ahora.replace(tzinfo=None)
            self.parches.append(mock.patch.object(build, "datetime", Falso))
        for p in self.parches:
            p.start()
        return self

    def __exit__(self, *a):
        for p in self.parches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def leer(self, nombre, defecto=None):
        f = self.datos / nombre
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else defecto

    def guardar(self, nombre, d):
        (self.datos / nombre).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    def generar(self):
        build.main()
        return self

    def html(self, ruta):
        return (self.site / ruta.strip("/") / "index.html").read_text(encoding="utf-8")


def stat(alias, pos="MC", goles=0, asist=0, rating=7.0, mvp=False):
    return {"alias": alias, "alias_id": None, "posicion": pos, "goles": goles, "asistencias": asist, "mvp": mvp,
            "rating": rating, "amarillas": 0, "rojas": 0, "valla_invicta": False}


def partido(pid, cuando, liga="vpn", gf=None, gc=None, estado=None, rival="Rival Prueba", stats=None, comp=None, local=True):
    partidos_ok = json.loads((RAIZ / "datos" / "partidos.json").read_text(encoding="utf-8"))
    base = next(p for p in reversed(partidos_ok) if p["liga"] == liga)
    return {"id": pid, "liga": liga, "competencia_id": comp or base.get("competencia_id"), "competencia": base["competencia"],
            "jornada": "Fecha 99", "fecha_utc": iso(cuando), "local": local,
            "rival": {"nombre": rival, "escudo": None}, "gf": gf, "gc": gc,
            "estado": estado or ("finalizado" if gf is not None else "programado"),
            "url_origen": base.get("url_origen", ""), "temporada": base.get("temporada"), "stats": stats or []}


class Enlaces(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v and v.startswith("/") and not v.startswith("//"):
                self.urls.append(v)


def enlaces_rotos(site: Path):
    rotos = set()
    for f in site.rglob("*.html"):
        if f.name == "404.html":
            continue
        e = Enlaces()
        e.feed(f.read_text(encoding="utf-8"))
        for u in e.urls:
            ruta = u.split("#")[0].split("?")[0]
            destino = site / ruta.lstrip("/")
            if not (destino.is_file() or (destino / "index.html").is_file()):
                rotos.add((str(f.relative_to(site)), u))
    return sorted(rotos)


@unittest.skipUnless(HAY_DATOS, "todavía no hay datos")
class EscenariosWeb(unittest.TestCase):
    def test_sitio_actual_sin_enlaces_rotos(self):
        with Escenario() as e:
            e.generar()
            self.assertEqual(enlaces_rotos(e.site)[:10], [])

    def test_victoria_y_derrota_por_wo(self):
        ahora = datetime.now(AR)
        with Escenario() as e:
            ps = e.leer("partidos.json")
            ps.append(partido("vpn-test-wo1", ahora - timedelta(days=1, hours=1), gf=3, gc=0, estado="wo", rival="Ganamos WO"))
            ps.append(partido("vpn-test-wo2", ahora - timedelta(days=1), gf=0, gc=3, estado="wo", rival="Perdimos WO"))
            e.guardar("partidos.json", ps)
            e.generar()
            self.assertIn("Victoria por W.O.", e.html("/partido/vpn-test-wo1/"))
            self.assertIn("Derrota por W.O.", e.html("/partido/vpn-test-wo2/"))
            self.assertIn("Ganamos WO", e.html("/calendario/"))
            self.assertIn("Ganamos WO", e.html("/"))

    def test_jugador_entra_y_sale_de_un_top(self):
        with Escenario() as e:
            dest = e.leer("destacados_vpn.json", [])
            comp = dest[0]["competencia"] if dest else "Liga"
            nuevo = {"liga": "vpn", "competencia": comp, "stat": "goles", "pos": 1, "alias": "VSP-Ch4cKaL",
                     "valor": "99", "url_origen": "https://virtualpronetwork.com"}
            e.guardar("destacados_vpn.json", dest + [nuevo])
            e.generar()
            self.assertIn("99", e.html("/plantel/"))
            # Sale de todos los tops (la liga publica los tops sin nosotros)
            for k in ("vpn", "lva", "vpug"):
                e.guardar(f"destacados_{k}.json", [])
            e.generar()
            # Un top de un jugador que no está en el plantel (alias nuevo)
            e.guardar("destacados_lva.json", [{**nuevo, "liga": "lva", "alias": "JugadorDesconocidoXYZ", "pos": 3}])
            e.generar()

    def test_jugador_nuevo_con_posicion_nueva_muchas_veces(self):
        ahora = datetime.now(AR)
        with Escenario() as e:
            ps = e.leer("partidos.json")
            for i in range(25):
                ps.append(partido(f"vpn-test-pos{i}", ahora - timedelta(days=40 - i), gf=2, gc=1, rival=f"Rival {i}",
                                  stats=[stat("Nuevo<Jugador>/ñ", "PO", rating=6 + (i % 4)), stat("ByCrisMor09", "DC", goles=1, rating=7.5),
                                         stat("Otro.Raro", "XYZ", rating=None)]))
            e.guardar("partidos.json", ps)
            e.generar()
            pagina = e.html("/jugador/nuevojugadorn/")
            self.assertIn("Nuevo&lt;Jugador&gt;/ñ", pagina)
            self.assertNotIn("Nuevo<Jugador>", pagina)
            self.assertIn("Sus notas", pagina)
            self.assertNotIn("Nuevo<Jugador>", e.html("/plantel/"))  # el JSON del plantel va escapado
            self.assertEqual(enlaces_rotos(e.site)[:10], [])

    def test_partido_sin_estadisticas_y_sin_nota(self):
        ahora = datetime.now(AR)
        with Escenario() as e:
            ps = e.leer("partidos.json")
            ps.append(partido("vpn-test-sinst", ahora - timedelta(days=2), gf=1, gc=1))
            ps.append(partido("vpn-test-nulos", ahora - timedelta(days=2, hours=1), gf=2, gc=2,
                              stats=[stat("ByCrisMor09", rating=None), stat("Xx", pos=None, rating=None)]))
            e.guardar("partidos.json", ps)
            e.generar()
            self.assertIn("Empate", e.html("/partido/vpn-test-sinst/"))

    def test_resultado_a_medias_y_marcador_raro(self):
        ahora = datetime.now(AR)
        with Escenario() as e:
            ps = e.leer("partidos.json")
            ps.append(partido("vpn-test-medio", ahora - timedelta(days=1), gf=2, gc=None))
            ps.append(partido("vpn-test-golea", ahora - timedelta(days=1, hours=2), gf=15, gc=12, rival="Un club con un nombre larguísimo que no entra en ningún lado FC"))
            e.guardar("partidos.json", ps)
            e.generar()

    def test_sin_partidos_programados_muestra_resumen(self):
        with Escenario() as e:
            ps = [p for p in e.leer("partidos.json") if p.get("gf") is not None]
            e.guardar("partidos.json", ps)
            e.generar()
            self.assertIn("Así nos fue en", e.html("/"))

    def test_sin_ningun_dato(self):
        with Escenario() as e:
            for f in list(e.datos.glob("*.json")):
                f.unlink()
            e.generar()
            self.assertIn("Sin partidos programados", e.html("/"))

    def test_archivos_opcionales_faltan(self):
        with Escenario() as e:
            for n in ("sanciones_lva.json", "sanciones_vpn.json", "titulos_lva.json", "titulos_vpn.json", "destacados_vpn.json",
                      "destacados_lva.json", "destacados_vpug.json", "alineacion_vpn.json", "rankings.json", "plantel_vpug.json",
                      "historial_posiciones.json", "estado.json", "carga_resultados.json"):
                (e.datos / n).unlink(missing_ok=True)
            e.generar()

    def test_competencia_nueva_con_tabla_nueva(self):
        ahora = datetime.now(AR)
        with Escenario() as e:
            ps = e.leer("partidos.json")
            p = partido("lva-test-copa", ahora + timedelta(days=2), liga="lva", comp="lva-copanueva", rival="Rival Copa")
            p["competencia"] = "Copa Nueva 2027"
            p["temporada"] = {"clave": "lva-copanueva", "nombre": "Copa Nueva 2027"}
            ps.append(p)
            e.guardar("partidos.json", ps)
            ts = e.leer("tablas.json")
            filas = [{"pos": i + 1, "pos_fuente": i + 1, "equipo": n, "escudo": None, "pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0,
                      "gc": 0, "dg": 0, "pts": 0, "es_vultur": n == "Vultur Sports"} for i, n in enumerate(["Rival Copa", "Vultur Sports", "Otro"])]
            ts.append({"id": "lva-copanueva", "liga": "lva", "competencia": "Copa Nueva 2027", "filas": filas})
            e.guardar("tablas.json", ts)
            e.generar()
            self.assertIn("Copa Nueva 2027", e.html("/tablas/"))
            self.assertIn("Rival Copa", e.html("/"))

    def test_sancion_vigente_de_un_jugador(self):
        with Escenario() as e:
            e.guardar("sanciones_lva.json", [{"liga": "lva", "jugador": "ByCrisMor09", "competencia": "1ra Div - Legacy",
                                             "motivo": "Doble amarilla", "fechas": 2, "vigente": True, "cumple": "fecha 17"}])
            e.generar()
            self.assertIn("ByCrisMor09 no puede jugar", e.html("/"))

    def test_choque_de_horarios_entre_ligas(self):
        ahora = datetime.now(AR)
        cuando = (ahora + timedelta(days=3)).replace(hour=22, minute=0, second=0, microsecond=0)
        with Escenario() as e:
            ps = e.leer("partidos.json")
            ps.append(partido("vpn-test-ch1", cuando, liga="vpn", rival="Choque A"))
            ps.append(partido("lva-test-ch2", cuando + timedelta(minutes=10), liga="lva", rival="Choque B"))
            e.guardar("partidos.json", ps)
            e.generar()
            self.assertIn("Choque de horarios", e.html("/"))

    def test_partido_en_juego_y_esperando_resultado(self):
        ahora = datetime.now(AR)
        with Escenario() as e:
            ps = e.leer("partidos.json")
            ps.append(partido("vpn-test-ya", ahora - timedelta(minutes=10), rival="Jugando Ahora"))
            ps.append(partido("vpn-test-esp", ahora - timedelta(hours=5), rival="Sin Cargar"))
            e.guardar("partidos.json", ps)
            e.generar()
            self.assertIn("Jugando Ahora", e.html("/"))
            self.assertIn("Esperando resultado", e.html("/partido/vpn-test-esp/"))

    def test_temporada_nueva_del_juego(self):
        # Un año después: los partidos de hoy son de otra edición y la web no debe romperse
        with Escenario(ahora=datetime.now(AR) + timedelta(days=365)) as e:
            ps = e.leer("partidos.json")
            ps.append(partido("vpn-test-fut", datetime.now(AR) + timedelta(days=364), gf=1, gc=0,
                              stats=[stat("ByCrisMor09", goles=1, rating=8.0)]))
            e.guardar("partidos.json", ps)
            e.generar()

    def test_tabla_con_datos_incompletos(self):
        with Escenario() as e:
            ts = e.leer("tablas.json")
            f = ts[0]["filas"]
            f.append({"pos": len(f) + 1, "equipo": "Equipo Sin Datos", "es_vultur": False})
            f[0]["zona"] = "zona-desconocida"
            e.guardar("tablas.json", ts)
            e.generar()
            self.assertIn("Equipo Sin Datos", e.html("/tablas/"))

    def test_partido_postergado_y_rival_renombrado(self):
        with Escenario() as e:
            ps = e.leer("partidos.json")
            prox = [p for p in ps if p.get("gf") is None]
            if prox:
                prox[0]["fecha_utc"] = iso(datetime.now(AR) + timedelta(days=20))
                prox[0]["rival"]["nombre"] += " Renombrado"
            e.guardar("partidos.json", ps)
            e.generar()


@unittest.skipUnless(HAY_DATOS, "todavía no hay datos")
class NavegadorConCasosRaros(unittest.TestCase):
    """Junta varios casos raros en un mismo sitio y lo recorre con un navegador real: ninguna página
    puede tener errores de JavaScript."""

    def test_sin_errores_de_javascript(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright no está instalado")
        import functools
        import http.server
        import threading
        ahora = datetime.now(AR)
        with Escenario() as e:
            ps = e.leer("partidos.json")
            ps.append(partido("vpn-test-wo", ahora - timedelta(days=1), gf=3, gc=0, estado="wo", rival="Rival WO"))
            ps.append(partido("vpn-test-ya", ahora - timedelta(minutes=5), rival="Jugando Ahora"))
            ps.append(partido("vpn-test-medio", ahora - timedelta(days=2), gf=1, gc=None))
            ps.append(partido("lva-test-ch", ahora + timedelta(minutes=10), liga="lva", rival="Choque <b>B</b>"))
            for i in range(6):
                ps.append(partido(f"vpn-test-n{i}", ahora - timedelta(days=30 - i), gf=i, gc=1, rival=f"R{i}",
                                  stats=[stat("Nuevo<Jugador>/ñ", "XYZ" if i % 2 else None, rating=None if i == 3 else 5 + i),
                                         stat("Comillas'y\\\"raro", "PO", goles=i, rating=6.5)]))
            e.guardar("partidos.json", ps)
            e.guardar("destacados_lva.json", [{"liga": "lva", "competencia": "X", "stat": "goles", "pos": 1,
                                               "alias": "Nuevo<Jugador>/ñ", "valor": "9", "url_origen": ""}])
            e.generar()
            manejador = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(e.site))
            manejador.log_message = lambda *a: None
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manejador)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            errores = []
            rutas = ["/", "/calendario/", "/tablas/", "/plantel/", "/vitrina/", "/estado/", "/comparar/",
                     "/comparar/?a=nuevojugadorn&b=noexiste", "/jugador/nuevojugadorn/", "/partido/vpn-test-wo/",
                     "/partido/vpn-test-ya/", "/partido/vpn-test-medio/", "/partido/lva-test-ch/", "/no-existe.html"]
            try:
                with sync_playwright() as pw:
                    try:
                        b = pw.chromium.launch()
                    except Exception:
                        self.skipTest("falta el navegador de Playwright")
                    for ancho in (390, 1366):
                        pg = b.new_page(viewport={"width": ancho, "height": 900})
                        pg.on("pageerror", lambda ex, pg=pg: errores.append(f"{pg.url}: {ex}"))
                        for r in rutas:
                            pg.goto(base + r)
                            pg.wait_for_timeout(150)
                        # Usar los controles: pestañas, buscador, filtros y comparar
                        pg.goto(base + "/plantel/")
                        for bt in pg.locator("button[data-liga]").all():
                            if bt.is_visible():
                                bt.click()
                        pg.goto(base + "/comparar/")
                        for bt in pg.locator(".cmp-ligas button").all():
                            if bt.is_visible():
                                bt.click()
                        pg.goto(base + "/tablas/")
                        for bt in pg.locator("[role=tab]").all():
                            if bt.is_visible():
                                bt.click()
                        pg.goto(base + "/calendario/")
                        for bt in pg.locator(".vista-cal button").all():
                            if bt.is_visible():
                                bt.click()
                        pg.keyboard.press("/")
                        pg.keyboard.type("nuevo")
                        pg.wait_for_timeout(300)
                    b.close()
            finally:
                srv.shutdown()
            self.assertEqual(errores, [])


class TemporadasNuevas(unittest.TestCase):
    """Temporada nueva, ascenso o descenso: el robot los toma solo, sin cambiar la configuración."""

    def test_vpn_toma_la_temporada_en_curso_del_historial(self):
        from conectores import vpn
        config = [{"nombre": "4ta", "league_id": 2183, "league_slug": "liga-argentina-4ta-division", "season_id": 6449}]
        hist = {"seasons": [
            {"key": "7001", "kind": "league", "active": True, "seasonLabel": "Temporada 12", "competitionName": "Liga Argentina 3ra División",
             "competitionHref": "/uy/league/2146/liga-argentina-3ra-division/season/7001/standings"},
            {"key": "6236", "kind": "cup", "active": True, "competitionHref": "/uy/tournament/2235/copa/season/6236/stats"},
            {"key": "6449", "kind": "league", "active": False, "competitionHref": "/uy/league/2183/liga-argentina-4ta-division/season/6449/standings"}]}
        c = vpn.competencias_actuales(config, hist)
        self.assertEqual([(x["league_id"], x["season_id"], x["temporada"]) for x in c], [(2146, 7001, "Temporada 12")])
        # Entre temporadas (ninguna en curso) o sin historial: la de la configuración
        self.assertEqual(vpn.competencias_actuales(config, {"seasons": []}), config)
        self.assertEqual(vpn.competencias_actuales(config, None), config)

    def test_vpug_busca_temporada_y_division(self):
        from conectores import vpug

        def pedir(c, url):
            if url.endswith("/temporadas"):
                return [{"id": 7, "estado": "FINALIZADA"}, {"id": 8, "estado": "EN_CURSO"}]
            if url.endswith("/divisiones"):
                return [{"id": i} for i in (1, 2, 3, 4)]
            nos = "temporadaId=8&divisionId=2" in url  # ascendimos a Segunda
            return {"filas": [{"club": {"id": 141 if nos else 5}}]}
        with mock.patch.object(vpug, "pedir", pedir):
            t, d, _ = vpug.temporada_y_division(None, "api", 141, 7, 3)
        self.assertEqual((t, d), (8, 2))

        def caida(c, url):
            if url.endswith("/temporadas"):
                raise vpug.ErrorConector("HTTP 503")
            return {"filas": []}
        with mock.patch.object(vpug, "pedir", caida):
            t, d, _ = vpug.temporada_y_division(None, "api", 141, 7, 3)
        self.assertEqual((t, d), (7, 3))

    def test_ediciones_del_juego_siguen_solas(self):
        from datetime import date
        ed = build.ediciones([{"nombre": "FC 27", "desde": date(2026, 9, 25)}])
        build.EDICIONES[:] = ed
        self.assertEqual(build.edicion_de(date(2026, 12, 1)), "FC 27")
        self.assertEqual(build.edicion_de(date(2027, 10, 1)), "FC 28")
        self.assertEqual(build.edicion_de(date(2029, 1, 1)), "FC 29")


class FalsoConector:
    def __init__(self, salida=None, error=None):
        self.salida, self.error = salida, error

    def sincronizar(self, lcfg, club, previos):
        if self.error:
            raise self.error
        return self.salida(previos) if callable(self.salida) else self.salida


@unittest.skipUnless(HAY_DATOS, "todavía no hay datos")
class EscenariosRobot(unittest.TestCase):
    """El robot (sync.py) frente a ligas caídas, webs cambiadas y torneos que terminan."""

    def correr(self, e, conectores):
        cfg = sync.yaml.safe_load((RAIZ / "config" / "ligas.yaml").read_text(encoding="utf-8"))
        for k in cfg["ligas"]:
            cfg["ligas"][k]["activa"] = k in conectores
        with mock.patch.dict(sync.CONECTORES, conectores, clear=True), \
             mock.patch.object(sync.yaml, "safe_load", side_effect=[cfg]), \
             mock.patch.object(sync, "RAIZ", e.tmp):
            (e.tmp / "config").mkdir(exist_ok=True)
            (e.tmp / "config" / "ligas.yaml").write_text("x", encoding="utf-8")
            sync.main()

    def test_liga_caida_conserva_los_datos(self):
        with Escenario() as e:
            antes = [p for p in e.leer("partidos.json") if p["liga"] == "vpn"]
            self.correr(e, {"vpn": FalsoConector(error=RuntimeError("la web de la liga no responde"))})
            despues = [p for p in e.leer("partidos.json") if p["liga"] == "vpn"]
            self.assertEqual(len(antes), len(despues))
            self.assertIn("no responde", e.leer("estado.json")["ligas"]["vpn"]["error"])
            e.generar()
            self.assertIn("no responde", e.html("/estado/"))

    def test_web_de_la_liga_cambio_y_devuelve_casi_nada(self):
        with Escenario() as e:
            antes = len([p for p in e.leer("partidos.json") if p["liga"] == "lva"])
            self.correr(e, {"lva": FalsoConector({"partidos": [], "tablas": []})})
            self.assertEqual(antes, len([p for p in e.leer("partidos.json") if p["liga"] == "lva"]))
            self.assertTrue(e.leer("estado.json")["ligas"]["lva"]["error"])
            self.assertTrue(e.leer("tablas.json"))

    def test_resultado_nuevo_y_torneo_terminado(self):
        with Escenario() as e:
            previos_vpn = [p for p in e.leer("partidos.json") if p["liga"] == "vpn"]
            tablas_vpn = [t for t in e.leer("tablas.json") if t["liga"] == "vpn"]

            def salida(previos):
                ps = [dict(p) for p in previos.values()]
                for p in ps:
                    if p.get("gf") is None:
                        p.update(gf=2, gc=0, estado="finalizado")
                return {"partidos": ps, "tablas": []}  # la liga ya no publica la tabla
            self.correr(e, {"vpn": FalsoConector(salida)})
            ps = [p for p in e.leer("partidos.json") if p["liga"] == "vpn"]
            self.assertEqual(len(ps), len(previos_vpn))
            self.assertFalse([p for p in ps if p.get("gf") is None])
            if tablas_vpn:
                self.assertFalse([t for t in e.leer("tablas.json") if t["liga"] == "vpn"])
            e.generar()

    def test_tabla_no_publicada_con_partidos_pendientes_se_conserva(self):
        with Escenario() as e:
            ps = e.leer("partidos.json")
            tablas_vpn = [t for t in e.leer("tablas.json") if t["liga"] == "vpn"]
            if not tablas_vpn:
                self.skipTest("sin tabla de VPN")
            tid = tablas_vpn[0]["id"]
            ps.append(partido("vpn-test-pend", datetime.now(AR) + timedelta(days=3), comp=tid))
            e.guardar("partidos.json", ps)

            def salida(previos):
                return {"partidos": list(previos.values()), "tablas": []}
            self.correr(e, {"vpn": FalsoConector(salida)})
            self.assertTrue([t for t in e.leer("tablas.json") if t["id"] == tid])

    def test_vpug_temporada_nueva_no_cuenta_como_falla(self):
        # Empieza una temporada nueva de VPUG con pocos partidos: los de la anterior se conservan
        from conectores import vpug
        with Escenario() as e:
            antes = [p for p in e.leer("partidos.json") if p["liga"] == "vpug"]
            if len(antes) < 11:
                self.skipTest("pocos partidos de VPUG")

            def salida(previos):
                nuevo = partido("vpug-test-nueva", datetime.now(AR) + timedelta(days=5), liga="vpug", comp="vpug-8-3")
                ps = [nuevo] + [p for p in previos.values() if p.get("competencia_id") != "vpug-8-3"]
                return {"partidos": ps, "tablas": []}
            self.correr(e, {"vpug": FalsoConector(salida)})
            self.assertIsNone(e.leer("estado.json")["ligas"]["vpug"]["error"])
            self.assertEqual(len([p for p in e.leer("partidos.json") if p["liga"] == "vpug"]), len(antes) + 1)

    def test_equipo_nuevo_en_la_tabla_sin_flecha(self):
        with Escenario() as e:
            ts = e.leer("tablas.json")
            t = next((t for t in ts if t["liga"] == "lva"), None)
            if not t:
                self.skipTest("sin tabla de LVA")
            t["filas"].insert(0, {**t["filas"][0], "equipo": "Equipo Recién Llegado", "es_vultur": False})
            for i, f in enumerate(t["filas"]):
                f["pos"] = i + 1
            sync.calcular_movimientos({t["id"]: t})
            self.assertIsNone(t["filas"][0]["mov"])


if __name__ == "__main__":
    unittest.main()
