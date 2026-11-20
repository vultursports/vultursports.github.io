# 05 · Modelo de datos (archivos JSON/YAML en el repo)

> **Plan original (19-nov-2026), conservado como historia.** Lo vigente está en el [README](../README.md) y en [00-decisiones.md](00-decisiones.md).

No hay base de datos: los datos viven como archivos en el repo. Git nos da gratis el
**historial** (cada sync es un commit, así que se puede ver la tabla de cualquier día pasado).

El desafío central sigue siendo que **la misma persona aparece con nombres distintos en cada
liga**. Por eso existe `plantel.yaml` con alias.

## `config/plantel.yaml` (se edita a mano)
```yaml
jugadores:
  - id: juan
    nombre: Juan Pérez
    posicion: MC
    secundaria: MCO
    dorsal: 10
    activo: true
    foto: img/plantel/juan.webp
    alias:
      ea: JuanP_10
      lva: juanp10
      vpn: Juan Perez
      vpug: JuanP
```

## `datos/partidos.json` (lo genera el robot)
```json
{
  "id": "vpn-785611",
  "liga": "vpn",
  "competencia": "Liga Argentina 4ta División",
  "temporada": "T11",
  "jornada": "Jornada 10",
  "fecha_utc": "2026-11-26T02:00:00Z",
  "local": false,
  "rival": {"nombre": "Arabia Team", "escudo": "https://…"},
  "gf": null, "gc": null,
  "estado": "programado",
  "url_origen": "https://virtualpronetwork.com/uy/matches/785611",
  "ea_match_id": null,
  "stats": [
    {"jugador": "juan", "alias": "Juan Perez", "goles": 1, "asist": 0, "mvp": false,
     "rating": 7.4, "amarillas": 0, "rojas": 0, "posicion": "MC"}
  ]
}
```
Estados posibles: `programado | en_vivo | finalizado | suspendido | wo`.

## `datos/tablas.json`
Para cada competencia: filas `{pos, equipo, escudo, pj, g, e, p, gf, gc, dg, pts, zona, es_vultur}`
y `actualizado`. El gráfico de "evolución de posición" se arma con `datos/historial_posiciones.json`,
donde el robot agrega `{fecha, competencia, pos}` una vez por día.

## `datos/manual/*.yaml`
- `competencias.yaml`: torneos "a veces" (copas de Discord, relámpagos) con sus partidos.
- `titulos.yaml`: el palmarés.
- `premios.yaml`: MVP de la fecha, equipo de la semana, goleador.
- `correcciones.yaml`: `{id_partido: {gf: 2, gc: 1}}` para pisar un dato mal cargado por una liga.

## Estadísticas globales (las calcula `build.py`)
- **Por jugador**: PJ, goles, asistencias, G+A, MVP y rating medio, por liga y en total.
- **Por club**: récord G-E-P, GF/GC, vallas invictas, racha, % de victorias por liga.
- **Ranking justo**: `rating_ajustado = (rating·PJ + 6.5·k) / (PJ + k)` con k≈5. Así el que jugó
  1 partido con 10 no queda primero.

## Alias sin vincular
Cuando el robot encuentra un nombre que no está en `plantel.yaml`, lo lista en la página `/estado`
con una sugerencia del jugador más parecido (difflib). Para vincularlo, se agrega el alias en el
YAML desde GitHub.
