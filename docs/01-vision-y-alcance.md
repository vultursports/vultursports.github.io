# 01 · Visión y alcance

> **Plan original (19-nov-2026), conservado como historia.** Lo vigente está en el [README](../README.md) y en [00-decisiones.md](00-decisiones.md).

## Objetivo
Un solo link para mandar al grupo de WhatsApp donde cualquier jugador, staff o rival vea:
1. **Cuándo jugamos** (todas las ligas, en hora argentina, en un solo calendario).
2. **Cómo venimos** en cada competencia (tabla, posición, racha) y en global.
3. **Quién rinde** (estadísticas por jugador por liga y sumadas).
4. **Historia del club** (títulos, temporadas pasadas, récords, salón de la fama).

## Usuarios
| Usuario | Qué necesita |
|---|---|
| Jugador del plantel | Próximo partido, su ficha, sus números, si está suspendido |
| Mánager / staff (vos) | Ver todo de un vistazo, cargar lo que falte, armar convocatorias, detectar alertas |
| Rivales / fichajes / público | Vidriera profesional del club (sumar jugadores, sponsors) |

## Dentro del alcance (MVP)
- Agenda unificada de partidos (LVA + VPN + VPUG) con filtros por liga.
- Tablas de posiciones de cada competencia donde estamos.
- Resultados con detalle (goleadores, asistencias, MVP, rating cuando la liga lo da).
- Plantel con ficha de jugador y estadísticas por liga y globales.
- Corrección/vinculación de datos editando archivos YAML desde GitHub.
- Sincronización automática programada (GitHub Actions).
- **Costo $0**: nada pago, ni hosting, ni dominio, ni base de datos.

## Fuera del MVP (fases siguientes)
- Generador de placas para Instagram (resultado, MVP de la fecha, próximo partido).
- Mercado/fichajes, sponsors, tienda.
- Multi-club (ofrecerlo a otros clubes: ver doc 03).

## Principios
- **Nuestros datos, nuestra base**: todo se copia a nuestra BD; si una liga se cae o borra
  historial, nosotros lo conservamos.
- **Mobile first**: el 90 % lo va a ver desde el celular, abriendo un link de WhatsApp.
- **Cero carga manual cuando se pueda**; carga manual fácil cuando no se pueda.
- **Trazabilidad**: cada dato sabe de qué liga vino y cuándo se sincronizó.
