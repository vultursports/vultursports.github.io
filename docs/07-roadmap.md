# 07 · Roadmap (todo con herramientas gratis)

> **Plan original (19-nov-2026), conservado como historia.** Lo vigente está en el [README](../README.md) y en [00-decisiones.md](00-decisiones.md).

## Fase 0 — Preparación (1-2 días)
- [ ] Crear la organización gratis **vultursports** en GitHub y el repo público (la web queda en `vultursports.github.io`).
- [ ] Responder las preguntas del doc 08 (escudo/colores, plantel con gamertags).
- [ ] Escribir a LVA, VPN y VPUG pidiendo permiso (mensaje modelo en el doc 08).
- [ ] Terminar de mapear endpoints: fixture y partido de VPUG, detalle de partido de VPN, LVA.
- [ ] Guardar JSON de ejemplo de cada liga en `tests/fixtures/`.

## Fase 1 — MVP "todo en un lugar" (1 semana)
- [ ] `conectores/vpug.py` y `conectores/vpn.py` + `sync.py` → `datos/partidos.json`, `tablas.json`.
- [ ] `conectores/lva.py` (según el permiso: datos directos o páginas públicas).
- [ ] `build.py` + plantillas: Inicio, Calendario (+ `calendario.ics`), Competencia, Partido.
- [ ] Workflow de GitHub Actions con cron + deploy a GitHub Pages.
- **Entregable**: un link gratis con fechas y tablas de las 3 ligas que se actualiza solo.

## Fase 2 — Jugadores y estadísticas (1-2 semanas)
- [ ] `plantel.yaml` + alias + página `/estado`.
- [ ] Stats por jugador (por liga y globales), ranking ajustado, comparador.
- [ ] Conector EA FC 27 (si la API de EA no bloquea a GitHub Actions).
- [ ] Pasada de diseño completa (taste-skill + impeccable), screenshots con Playwright.

## Fase 3 — Club pro (continuo)
- [ ] Palmarés, salón de la fama, temporadas históricas (YAML manual).
- [ ] Imagen Open Graph del próximo partido (generada con Pillow en el build) para que se vea al pegar el link en WhatsApp.
- [ ] Placas para Instagram (PNG generados en el build, descargables).
- [ ] PWA instalable.

## Primer paso sugerido
Arrancar por **VPUG + VPN + la página de Calendario**. En pocas horas ya resuelve lo principal
(ver todas las fechas juntas) y prueba que el esquema gratis funciona.
