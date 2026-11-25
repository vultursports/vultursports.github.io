# Vultur Sports — web del club · versión 1.0

Web oficial de **Vultur Sports** (club argentino de Clubes Pro, EA FC, PC) que junta en un solo
lugar todo lo de las competencias donde juega: **VPN, LVA y VPUG**. Se actualiza sola y cuesta $0.

- Dirección: **https://vultursports.github.io**
- Cambios de cada versión: [CHANGELOG.md](CHANGELOG.md)
- Decisiones del club (mandan sobre todo lo demás): [docs/00-decisiones.md](docs/00-decisiones.md)
- Plan original (historia): `docs/01` a `docs/08`

## Qué muestra

| Sección | Contenido |
|---|---|
| **Inicio** | Próximo partido (o "Hoy jugamos") con la posición de cada equipo y cuenta regresiva; avisos de sancionados y choques de horario; "En vivo" cuando un integrante transmite en Twitch; partidos de la semana; últimos resultados; "Cómo vamos" en cada competencia con forma reciente |
| **Calendario** | Todos los partidos (próximos y jugados), filtro por liga y suscripción al calendario del celular (`calendario.ics`) |
| **Tablas** | Una tabla por competencia (selector o "Ver todas juntas" en la compu), con nuestra fila resaltada, flechas de subida/bajada y forma reciente. Cuando un torneo termina, queda su tabla final con nuestro puesto y números de cierre hasta que empieza el siguiente (y se corrige sola si la liga carga resultados atrasados) |
| **Plantel** | Filtro por liga y temporada (todo el historial), líderes (6 y "Ver más"), tabla de jugadores ordenable, "El 11 más usado" (cancha + banco, MVP), quién juega en cada puesto y jugadores destacados por las ligas |
| **Detalle de partido** | Resultado, estadísticas de los dos equipos, alineación con notas y MVP, nuestros jugadores; en los partidos por jugar, la previa (forma, historial contra el rival, nuestro 11 más usado en esa competencia) y los sancionados |
| **Jugador** | Dorsal, posición, totales, por liga, por temporada y sus partidos |
| **Rival** | Historial contra ese equipo en todas las ligas |
| **Vitrina** | Récords del club (todo el historial) y títulos (los de la LVA y VPN se detectan solos; los demás se cargan en `config/titulos.yaml`). Mientras no haya, una vitrina vieja con telarañas y datos reales de cada liga |
| **Estado** | Cuándo se actualizó cada liga y si falló (enlace en el pie) |

Todas las páginas dan el crédito a cada liga (logo, enlace oficial y redes) en "Nuestras competencias".

## De dónde sale cada dato

| Liga | Cómo se lee | Qué trae |
|---|---|---|
| **VPN** (virtualpronetwork.com) | Los datos públicos que carga su web | Fixture, tabla del grupo (con posición anterior), detalle de cada partido (goles, asistencias, MVP, nota, estadísticas por equipo, formación publicada), no habilitados e historial desde jul. 2024 |
| **LVA** (ligavirtualargentina.com) | Sus páginas públicas, con un navegador automático (Playwright) | Torneos activos y terminados ("Ver Finalizados"), tabla, estadísticas por jugador, sanciones |
| **VPUG** (vpugvirtualprouruguaygaming.com) | API pública + cuenta de jugador del club (secretos `VPUG_EMAIL` y `VPUG_PASSWORD`) | Tabla, rankings, fixture, detalle de partidos (goles, asistencias, nota, figura) y plantel (dorsal y posición) |
| **EA SPORTS FC** (proclubs.ea.com) | API pública no oficial, con un navegador visible (en GitHub, pantalla virtual xvfb) | Solo los partidos que coinciden con uno de nuestras competencias: tiros, pases, entradas y atajadas por jugador, estadísticas del equipo si la liga no las da, resultado provisorio. Guarda los últimos 10 partidos: cada pasada suma los nuevos |
| **Twitch** | decapi.me (gratis) | Si el canal de un integrante está en vivo |

Reglas importantes (detalle en `docs/00-decisiones.md`): nunca se inventa información; los nombres de
formación solo vienen de VPN; jugadores y rivales con nombres distintos se unen solos cuando el nombre
base coincide (ante la duda, quedan separados); hora argentina; español neutro.

## Cómo funciona

```
GitHub Actions (cada hora en punto, todo el día, con un disparador externo en cron-job.org;
                el cron de GitHub queda de respaldo, y también corre con cada cambio subido)
  → python sync.py      baja los datos de cada liga a datos/
  → python build.py     genera la web en site/ (HTML estático)
  → pruebas automáticas (si fallan, no se publica)
  → publica site/ en GitHub Pages
```

Las temporadas cerradas, los escudos procesados y las formaciones se guardan y no se vuelven a pedir
(un torneo recién terminado se sigue leyendo hasta que la liga aprueba todos sus resultados).
Si una liga falla o devuelve de golpe muchos menos datos, se conservan los anteriores y queda marcado
en la página de Estado.

## Correrlo en la PC

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m playwright install chromium
# Cuenta de VPUG (opcional): archivo .env con VPUG_EMAIL=... y VPUG_PASSWORD=...  (no se sube a GitHub)
.venv/Scripts/python.exe sync.py          # baja los datos
.venv/Scripts/python.exe build.py         # genera site/
cd site && ../.venv/Scripts/python.exe -m http.server 8077   # abrir http://127.0.0.1:8077
```

- Pruebas rápidas (se corren antes de cada publicación): `.venv/Scripts/python.exe -m unittest discover -s tests -v`
- Pruebas de escenarios (liga caída, torneo terminado, temporada nueva, FC nuevo; unos 3 minutos):
  `.venv/Scripts/python.exe -m unittest discover -s tests -p "prueba_*.py" -v`
- Prueba visual con sancionados inventados (no toca la web real): `python herramientas/demo_sanciones.py` → `site-demo/`
- Probar el recuadro de Twitch: abrir `/?vivo=un_canal_que_este_en_vivo`

## Mantenimiento

La web no necesita que nadie cargue datos. Lo único con fecha:

- **Disparador de cada hora** (cron-job.org, cuenta del club): usa un token de GitHub de este repo
  (solo permiso de Actions) que **vence el 26/11/2027**. Antes de esa fecha, crear uno nuevo y
  cambiarlo en el encabezado `Authorization` del job. Si vence, la web sigue actualizándose con el
  cron de GitHub, pero con menos frecuencia.

## Ajustes a mano (archivos YAML)

| Archivo | Para qué |
|---|---|
| `config/ligas.yaml` | IDs del club en cada liga, redes de las ligas, canales de Twitch, ediciones del juego, dirección del sitio |
| `config/plantel.yaml` | Unir nombres de un mismo jugador, ocultar a alguien, mostrar otro nombre |
| `config/rivales.yaml` | Unir o separar rivales |
| `config/titulos.yaml` | Títulos que no salen de las ligas (copas relámpago, torneos de Discord) |

## Estructura

```
conectores/   vpn.py, lva.py, vpug.py (lectura de cada liga), ea.py (datos extra de EA) y base.py
sync.py       actualiza datos/            build.py    genera site/
jugadores.py  estadísticas por jugador    rivales.py  historial por rival (une por nombre y escudo)
extras.py     jugador de la noche, hitos, récords y control cruzado con EA
escudos.py    recorta y guarda escudos    og.py       imagen para compartir en WhatsApp
plantillas/   HTML (Jinja2)               estaticos/  css, js y logos de las ligas
recursos/     tipografías para og.png     datos/      todo lo descargado (la "base de datos")
tests/        pruebas automáticas         docs/       decisiones y plan original
herramientas/ demo de sanciones (site-demo/) y generador de la telaraña de la Vitrina
```
