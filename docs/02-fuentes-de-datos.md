# 02 · Fuentes de datos (liga por liga)

> **Plan original (19-nov-2026), conservado como historia.** Lo vigente está en el [README](../README.md) y en [00-decisiones.md](00-decisiones.md).

Relevado el 19-nov-2026 navegando cada sitio con Playwright y mirando qué pide cada página
a su servidor. **Buena noticia: las tres ligas tienen los datos en formato estructurado (JSON)**,
así que no hace falta "leer HTML a mano" en ningún caso.

Resumen:

| Liga | Tecnología del sitio | Cómo expone los datos | Dificultad | Estabilidad |
|---|---|---|---|---|
| VPUG | SPA + API propia en Render | **API REST pública** `vpug-liga-api.onrender.com/v1/...` | Baja | Media (Render gratis "duerme" → la 1ª llamada tarda) |
| VPN | Next.js + Cloudflare | JSON de páginas `/_next/data/<buildId>/...json` + `/api/...` | Media | Media (el buildId cambia en cada deploy; Cloudflare puede frenar bots) |
| LVA | Hostinger Horizons (React) + **Supabase** | Supabase REST (tablas `teams`, `players`, `matches`, `player_match_stats`, `tournaments`, `sanctions`, `team_of_the_week`...) | Baja-media | Alta |
| EA FC | API no oficial de Clubs | `proclubs.ea.com/api/fc/...` | Media | Baja-media (no documentada, puede cambiar con FC27) |

> ⚠️ **Antes de automatizar, pedir permiso a cada liga** (ver doc 08). Son comunidades chicas,
> a todos les conviene llevarse bien, y un "¿nos dejan leer su API para mostrar los datos de
> Vultur con link a ustedes?" suele salir bien. Incluso pueden darnos un acceso más cómodo.

---

## VPUG — Virtual Pro Uruguay Gaming
- Sitio: https://vpugvirtualprouruguaygaming.com/
- API: `https://vpug-liga-api.onrender.com/v1/`
- **Vultur Sports = club `id 141`**, división **Tercera** (`divisionId=3`), temporada `id 7` (2026 · T1, EN_CURSO).

Endpoints vistos:
| Endpoint | Devuelve |
|---|---|
| `GET /v1/temporadas` | temporadas (id, año, número, estado, mercadoAbierto) |
| `GET /v1/divisiones` | Primera(1), Segunda(2), Tercera(3), Cuarta(4) |
| `GET /v1/tabla?temporadaId=7&divisionId=3` | tabla: posición, club{id,nombre,escudo}, pj,g,e,p,gf,gc,dg,descuento,pts,zona + formato (ascensos/descensos) |
| `GET /v1/eliminatorias?temporadaId=&divisionId=` | cruces de playoffs |
| `GET /v1/actividad` | feed de novedades |

| `GET /v1/estadisticas/rankings?temporadaId=&divisionId=` | goleadores y asistidores (top) |

**Verificado el 19-nov:** `/partidos`, `/partidos/fixture`, `/clubes/:id` y `/estadisticas/semana`
responden "Token no enviado": son **solo para usuarios logueados**. Por la decisión de usar solo
datos públicos, de VPUG se muestran tabla y rankings, sin fixture.

Notas: los escudos están en Supabase Storage. El backend está en Render free → hacer
*retry* con espera la primera vez (cold start de ~30-60 s).

## VPN — Virtual Pro Network
- Sitio: https://virtualpronetwork.com/ (redirige por país: `/mx`, `/ar`, `/uy`…)
- **Vultur Sports = team `id 26691`**, permalink `vultur-sports`, short `VSP`, consola **PC**.
- Competencia actual: **Liga Argentina 4ta División** (league `2183`), **Temporada 11** (season `6449`).

Cómo se obtiene:
1. Leer el `buildId` del HTML de la home (`<script id="__NEXT_DATA__">` → `buildId`).
2. Pedir los JSON de página:
   - Equipo: `/_next/data/{buildId}/uy/teams/vultur-sports.json?communitySlug=uy&id=vultur-sports`
     → `team`, `managers`, `general.summaries` (PJ, G, E, P, GF, GC, vallas, forma, posición),
       `nextMatch` (fecha, hora, rival, jornada), `tableSlice` (tabla resumida), `competitions`.
   - Tabla: `/_next/data/{buildId}/uy/league/2183/liga-argentina-4ta-division/season/6449/standings.json?...`
   - Partido: `/_next/data/{buildId}/uy/matches/{matchId}.json?communitySlug=uy&id={matchId}`
     (detalle, probablemente con estadísticas por jugador).
   - Ranking de jugadores: `/{community}/rankings/players.json`.
3. Si el `buildId` da 404 → volver a leerlo y reintentar (cambia en cada deploy de ellos).

Riesgo: Cloudflare. Ir despacio (1 pedido cada pocos segundos, solo lo nuestro), User-Agent
identificable, y cachear. Si nos bloquea: plan B con navegador real (Playwright) en el worker.

## LVA — Liga Virtual Argentina
- Sitio: https://ligavirtualargentina.com/ (hecho con Hostinger Horizons por "Mamboo")
- Datos en **Supabase** (`pqkgpkxajgnyqkcfqhsc.supabase.co`), tablas públicas de lectura que
  usa su propia web: `tournaments`, `teams`, `players`, `matches` (status: scheduled/live/approved),
  `player_match_stats` (goles, asistencias, MVP, rating, amarillas, rojas, posición jugada),
  `player_awards`, `sanctions`, `team_of_the_week`, `sponsors`.
- Vultur Sports juega **1ra Div – Legacy**; hoy 19/11 23:00 vs MARPLA FC (Fecha 15).
- Torneos visibles: Copa Argentina, 1ra Div Legacy, 2da Div Legacy.

Cómo se obtiene (en orden de preferencia):
1. **Pedir a la LVA** acceso o permiso explícito para leer su Supabase (es lo más limpio).
2. Si dicen que sí: consultas REST filtradas por nuestro `team_id` (partidos, stats por jugador,
   sanciones). Es la fuente más rica de las tres (trae **rating y MVP por jugador**).
3. Si no hay respuesta: leer las páginas públicas renderizadas (fixture, tabla, estadísticas)
   con Playwright, igual que un visitante.

## EA Sports FC — API de Clubs (no oficial)
Útil para lo que las ligas no traen (stats finas por partido: pases, tiros, atajadas, rating EA,
posiciones) y para **detectar partidos jugados** apenas terminan.
- Base (FC24-FC26): `https://proclubs.ea.com/api/fc/`
  - `clubs/search?platform=common-gen5&clubName=Vultur%20Sports` → `clubId`
  - `clubs/matches?platform=common-gen5&clubIds={id}&matchType=leagueMatch` (también `playoffMatch`, y los amistosos de liga privados que usan las ligas)
  - `members/stats?platform=common-gen5&clubId={id}`
  - `clubs/overallStats?platform=common-gen5&clubIds={id}`
- **Solo guarda los últimos ~5-10 partidos por tipo** → hay que consultar seguido y guardar todo
  nosotros (por eso el robot de GitHub Actions corre cada 20 min en horario de partidos,
  de 22:00 a 03:00 hora argentina).
- Pide headers tipo navegador y a veces bloquea IPs de datacenter. Verificar con FC27 en cuanto
  esté disponible (el path/plataforma puede cambiar).
- Esto es exactamente lo que hace ProFile para sus "estadísticas automáticas".

**Cruce EA ↔ ligas**: cada partido de liga se empareja con un partido de EA por
`rival + fecha/hora (±3 h)`; así un mismo partido tiene resultado oficial (liga) + stats finas (EA).

## Fuente manual (siempre disponible)
Panel admin para cargar/corregir: competencias "a veces" (copas relámpago, amistosos, torneos de
Discord), resultados sin API, títulos y premios.
