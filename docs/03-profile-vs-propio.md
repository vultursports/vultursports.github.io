# 03 · ¿Qué es ProFile? ¿Nos sirve? Alternativas

> **Plan original (19-nov-2026), conservado como historia.** Lo vigente está en el [README](../README.md) y en [00-decisiones.md](00-decisiones.md).

## Qué es ProFile (profileclubs.online)
- Servicio **brasileño** que vende "sitio exclusivo + estadísticas automáticas" para clubes de
  EA FC Clubs. Se contrata hablando con un "consultor" (precio a medida, no publicado).
- Técnicamente es una app hecha con **Base44** (constructor de apps con IA, no-code). Cada club es
  un subdominio (`pueblomanya.profileclubs.online`) y lee entidades `Player`, `Match`, `Trophy`,
  `HallOfFame`, `Settings`.
- Funciones: plantel con rating/partidos/goles/asistencias/MoM, calendario, títulos, salón de la
  fama, "ranking inteligente" (pondera rating por cantidad de partidos), colores del escudo,
  área del mánager, "ProMarket" (vidriera de jugadores).
- Las estadísticas automáticas salen de la **API de EA** (ver doc 02).

## Lo que ProFile **no** resuelve (y es tu problema principal)
- **No lee las ligas** (LVA, VPN, VPUG). Sus "títulos" y "fecha 5" se cargan a mano.
- No hay tablas de posiciones de cada liga, ni fixture oficial unificado.
- No sos dueño de los datos ni del dominio; dependés de un tercero y de Base44.

→ Sirve como **inspiración de diseño y funciones**, no como solución.

## Alternativas evaluadas

| Opción | Pros | Contras | Veredicto |
|---|---|---|---|
| **ProFile** | Listo en 30 min, lindo | Pago, no integra ligas, sin control | ❌ No resuelve lo central |
| Base44 / Lovable / Horizons (lo que usan LVA y ProFile) | Rápido para prototipar | Los conectores y tareas programadas se complican; lock-in | ⚠️ Solo para mockups |
| Notion / Google Sheets + embeds | Gratis | Carga manual, feo en el celu | ❌ |
| Proclubshead / ProClubs World / footballgpt | Stats EA gratis | Genéricos, sin ligas, no es "nuestra" página | ⚠️ Referencia |
| Sitio propio Django + Railway | Integra todo, mismo stack que InPass | **Cuesta ~US$5/mes** | ❌ Descartado (tiene que ser gratis) |
| **Sitio estático propio (Python) + GitHub Actions + GitHub Pages** | **$0**, integra todo, datos nuestros con historial en git, no hay servidor que mantener | Sin login (se edita por GitHub); el robot no corre a la hora exacta | ✅ **Recomendado** |

## Bonus: oportunidad
Si funciona para Vultur, el mismo sistema puede ofrecerse a **otros clubes de LVA/VPN/VPUG**
(como ProFile pero **con integración real de ligas rioplatenses**). Con el esquema gratis alcanza
con que cada club haga un *fork* del repo y cambie `config/`.
