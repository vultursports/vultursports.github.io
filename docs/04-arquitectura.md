# 04 · Arquitectura (100 % gratis)

> **Plan original (19-nov-2026), conservado como historia.** Lo vigente está en el [README](../README.md) y en [00-decisiones.md](00-decisiones.md).

> Requisito: **costo $0, sin tarjeta de crédito, sin pruebas que vencen**.
> Por eso se descarta Railway (solo trae crédito de prueba) y cualquier servidor 24/7.

## Idea clave: sitio estático + robot programado
No hace falta un servidor prendido todo el día. Los datos de las ligas cambian unas pocas veces
por noche, así que alcanza con un **robot que corre cada 20-30 min, baja los datos, genera las
páginas HTML y las publica**. Todo eso lo da GitHub gratis.

```
GitHub (repo público "vultur-sports")
│
├─ GitHub Actions (cron)  ──►  python sync.py      ← baja LVA / VPN / VPUG / EA
│                               │
│                               ├─ datos/*.json     ← se commitean: la "base de datos" es el repo
│                               └─ python build.py  ← genera site/*.html + calendario.ics
│
└─ GitHub Pages  ──►  https://vultursports.github.io   ← lo que ve la gente
```

| Pieza | Servicio | Costo | Límite relevante |
|---|---|---|---|
| Código + datos | GitHub (repo **público**) | $0 | — |
| Robot programado | **GitHub Actions** | $0 | Ilimitado en repos públicos |
| Hosting | **GitHub Pages** | $0 | 1 GB, 100 GB/mes de tráfico (sobra) |
| Dominio | `vultursports.github.io` (organización gratis "vultursports") | $0 | Sin dominio propio |
| Escudos/fotos | En el mismo repo (`site/img/`) | $0 | Optimizar a WebP |

¿Por qué repo **público**? Los minutos de Actions son ilimitados y los datos ya son públicos en
las ligas. No se guarda ningún secreto.

## Stack
- **Python 3.12** (lo que ya usás) para el robot y para generar el sitio.
- **Jinja2** para las plantillas: es casi igual a los templates de Django.
- `httpx` para pedidos HTTP, `pyyaml` para la configuración, `icalendar` para el `.ics`.
- CSS propio y un poquito de JS (filtros, selector de liga). Sin frameworks pesados.
- Gráficos: SVG generado en Python o Chart.js por CDN (skill **dataviz**).
- Playwright **solo** si algún sitio bloquea los pedidos simples (también corre gratis en Actions).

## Estructura del repo
```
vultur-sport/
├── config/
│   ├── ligas.yaml          IDs de Vultur en cada liga
│   └── plantel.yaml        jugadores + alias por liga (se edita a mano)
├── datos/
│   ├── raw/{liga}/…json    respuesta cruda de cada liga (historial gratis vía git)
│   ├── partidos.json       todo normalizado
│   ├── tablas.json
│   ├── stats_jugadores.json
│   └── manual/             competencias "a veces", títulos, correcciones (YAML)
├── conectores/
│   ├── base.py  vpug.py  vpn.py  lva.py  ea.py
├── plantillas/             Jinja2 (base.html, inicio.html, calendario.html, …)
├── estaticos/              css, js, img
├── sync.py                 baja y normaliza
├── build.py                genera site/
├── tests/                  tests de conectores con JSON guardados
└── .github/workflows/
    ├── sync.yml            cron: sync + build + deploy
    └── deploy.yml          al hacer push manual
```

## Programación del robot (`sync.yml`)
```yaml
on:
  schedule:
    # Los partidos son siempre desde las 22:00 hora argentina (UTC-3, sin horario de verano).
    - cron: "*/20 1-5 * * *"   # cada 20 min de 22:00 a 02:59 AR (= 01:00–05:59 UTC)
    - cron: "0 12,19 * * *"    # 2 veces en el día (09:00 y 16:00 AR): fixture, tablas, cambios de horario
  workflow_dispatch: {}                    # botón "Run" manual desde GitHub o el celular
```
Pasos: checkout → `pip install` → `python sync.py` → `python build.py` → commit de `datos/` si
cambió → deploy de `site/` a Pages.

## Reglas del robot
- **Idempotente**: todo se guarda con clave `liga + id_externo`; correrlo 2 veces no duplica.
- **Educado**: timeouts, reintentos con espera, máx. 1 pedido/seg por sitio, solo nuestros datos.
- Los resultados y tablas oficiales mandan los de la liga; EA solo **enriquece**.
- Lo que está en `datos/manual/` pisa a lo automático (correcciones).
- Si una liga falla, queda marcado en la página `/estado`. El sitio sigue mostrando el
  último dato bueno con "actualizado hace X".

## ¿Y el "panel del mánager"?
Sin servidor no hay login, pero tampoco hace falta:
- Para editar, se modifican `config/plantel.yaml` o `datos/manual/*.yaml` **desde la web de
  GitHub** (funciona también desde el celular). Al guardar, el sitio se regenera solo en ~1 min.
- La página `/estado` (pública, sin datos sensibles) muestra la última sincronización de cada liga
  y los "alias sin vincular".

## Alternativas gratis (por si GitHub no convence)
| Opción | Nota |
|---|---|
| Cloudflare Pages en lugar de GitHub Pages | También gratis, más rápido; el robot sigue en Actions |
| Netlify / Vercel (plan free) | Sirven igual para el sitio estático |
| ❌ Render free / Koyeb | El servicio "duerme" y la base gratis de Render vence a los 30 días |
| ❌ PythonAnywhere free | Solo deja conectarse a una lista de sitios permitidos: las ligas no están |
| ❌ Supabase free | Pausa el proyecto tras 1 semana sin uso: un riesgo innecesario |

## Verificación
- Tests de cada conector con JSON guardados → si una liga cambia el formato, se ve al instante.
- Screenshots móvil/escritorio con Playwright; skills **impeccable**, **taste-skill**, **code-review**.
