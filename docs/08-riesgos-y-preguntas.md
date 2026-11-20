# 08 · Riesgos, ética y preguntas abiertas

> **Plan original (19-nov-2026), conservado como historia.** Lo vigente está en el [README](../README.md) y en [00-decisiones.md](00-decisiones.md).

## Riesgos
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Una liga cambia su web/API | Se corta esa liga | Snapshots crudos + tests con fixtures + alerta tras 3 fallos + carga manual |
| VPN/Cloudflare bloquea | Sin datos VPN | Pocos pedidos, caché, permiso de VPN, plan B Playwright |
| VPUG en Render "dormido" | Sync lento | Reintento con espera de 60 s |
| API EA cambia con FC27 o bloquea IPs de Railway | Sin stats finas | Es "enriquecimiento", el sitio funciona sin ella |
| Mismo jugador con nombres distintos | Stats partidas | Modelo de alias + vinculación manual asistida |
| Horarios en distintas zonas (MX, AR, UY) | Fechas mal | Guardar todo en UTC y mostrar siempre en hora argentina (GMT-3). Partidos siempre desde las 22:00 AR |
| Partido después de medianoche (ej. 00:30) | Aparece en el "día siguiente" | Agrupar por **"noche de juego"**: todo lo que va de 22:00 a 05:59 cuenta como la fecha en que empezó la noche |
| Choque de partidos entre ligas | Partido perdido | Alerta automática de solapamiento |
| El cron de GitHub Actions se atrasa (5-30 min en horas pico) | El resultado tarda un poco más en aparecer | Aceptable; botón "Run workflow" para forzarlo |
| GitHub desactiva los cron tras 60 días sin actividad en el repo | El sitio deja de actualizarse | Los commits automáticos de datos cuentan como actividad (verificar en la fase 1); si no alcanza, un *keepalive* mensual |
| Cloudflare de VPN o la API de EA bloquean las IPs de GitHub | Falta esa fuente | Mismo plan B: Playwright en el Action; EA es opcional |
| GitHub cambia sus planes gratis | Habría que mudarse | Todo es HTML estático: se pasa a Cloudflare Pages o Netlify en minutos |

## Ética / buena vecindad
- Leer **solo** datos públicos y **solo** lo que es de Vultur (y la tabla de nuestras competencias).
- No usar credenciales ni accesos que la liga no nos haya dado. Para la LVA (Supabase) en
  particular: **pedir permiso antes** de conectarnos directo.
- Siempre mostrar "Fuente: LVA/VPN/VPUG" con link a la página oficial.
- Frecuencia baja de consultas.

### Mensaje modelo para las ligas
> Hola! Somos Vultur Sports (jugamos en su liga en ___). Estamos armando la web del club para
> que el plantel vea en un solo lugar las fechas y resultados de todas las competencias que
> jugamos. ¿Les parece bien que leamos de su página/API los datos de nuestros partidos y la tabla
> de nuestra división (unas pocas consultas por hora), siempre con link y crédito a ustedes? Si
> tienen una forma preferida de compartir esos datos, la usamos. ¡Gracias!

## Preguntas para vos
1. **Escudo y colores** oficiales en buena calidad (o tomo el de VPN). ¿Hay manual de marca?
2. **Dirección web**: ¿`vultursports.github.io` está bien? (gratis; un dominio propio cuesta plata)
   ¿Alguien del club tiene cuenta de GitHub para crear la organización?
3. **Plantel**: lista de jugadores con gamertag de EA y nombre que usa cada uno en cada liga.
4. **Nombre exacto del club en EA FC 27** y plataforma (VPN dice PC) para la API de EA.
5. **"Otras ligas a veces"**: ¿cuáles? (copas de Discord, relámpagos…). ¿Tienen web o van manual?
6. **Público**: en la versión gratis todo el sitio es público. ¿Hay algo que no quieran mostrar?
7. **Historial**: ¿quieren cargar títulos/temporadas anteriores? ¿Desde qué FIFA/FC?
8. **¿Multi-club** a futuro (ofrecerlo a otros clubes) o solo Vultur?
9. ¿Redes del club (Instagram, Discord, Twitch) para enlazar y para las placas?
