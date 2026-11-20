# 06 · Pantallas y UX

> **Plan original (19-nov-2026), conservado como historia.** Lo vigente está en el [README](../README.md) y en [00-decisiones.md](00-decisiones.md).

Selector global arriba en todo el sitio: **[ Todas | LVA | VPN | VPUG | … ]** — cambia todas
las cifras de la página. Así se cumple "por separado y global" sin duplicar pantallas.

## Público
1. **Inicio**
   - Hero con escudo y **próximo partido** grande (cuenta regresiva, liga, rival, hora argentina).
   - "Esta semana": todos los partidos de la semana de todas las ligas.
   - Tarjetas por liga: posición actual, puntos, forma (✅✅❌✅✅), link a la tabla.
   - Último resultado + MVP. Ticker de novedades (fichajes, títulos, rachas) como ProFile.
2. **Calendario / Fixture** (horas siempre en hora argentina; los partidos arrancan desde las 22:00
   y se agrupan por "noche de juego", así un partido a las 00:30 queda en la noche en que empezó)
   - Vista lista (por día) y vista mes; colores por liga; filtro jugados/próximos.
   - Botón **"Agregar a mi calendario"** (feed `.ics` suscribible — se actualiza solo en Google
     Calendar / iPhone). Muy útil y barato de hacer.
3. **Competencias** → página por competencia: tabla completa (nuestra fila destacada), fixture,
   resultados, goleadores del club en esa competencia, zonas de ascenso/descenso, gráfico de
   evolución de posición.
4. **Partido**: resultado, rival, liga, goles/asistencias, MVP, ratings, stats EA si hay, link a la
   fuente oficial.
5. **Plantel**: tarjetas estilo carta FC (posición, rating, PJ, G, A, MVP), filtros por línea.
6. **Jugador**: foto, posiciones, stats por liga y total, últimos partidos, premios, sanciones.
7. **Estadísticas**: rankings internos (goleadores, asistidores, MVP, rating ajustado, vallas
   del arquero), comparador de 2 jugadores, récords del club.
8. **Historia / Palmarés**: títulos, temporadas pasadas por liga, salón de la fama.

## Mánager (sin login: es gratis y no hay servidor)
- Página pública `/estado`: última sincronización por liga, errores y alias sin vincular.
- Vincular alias, corregir partidos y cargar competencias manuales: se editan los YAML desde
  GitHub (ver doc 04).
- Avisos en la propia web (banner en Inicio): jugador suspendido para el próximo partido, choque
  de horarios entre ligas, partido sin resultado 24 h después.
- (Fase 3) Placas para Instagram generadas en el build.

## Dirección de diseño (a refinar con taste-skill / impeccable)
- Identidad **"buitre"**: oscuro, sobrio, agresivo; colores tomados del escudo de Vultur
  (el escudo está en VPN: `media.virtualpronetwork.com/teamlogos/56824d17…_original.png`).
- Tipografía condensada deportiva para cifras (tablas legibles en 360 px).
- Modo oscuro por defecto, claro opcional. Nada de plantilla genérica "IA".
- Placas compartibles con Open Graph: cuando se pega el link en WhatsApp se ve el próximo
  partido con escudos.

## Ideas extra
- PWA instalable ("Agregar a inicio").
- Marca "EN VIVO" cuando una liga pone el partido como `live` (con el retraso propio del robot).
- Descargar las stats en CSV (se generan en el build).
