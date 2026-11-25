# Cambios

## 1.0 — 25/11/2026

Primera versión oficial de la web de Vultur Sports (https://vultursports.github.io), después de una
semana de trabajo (19 al 25 de noviembre de 2026).

**Qué tiene**

- **Inicio:** próximo partido con cuenta regresiva y posición de cada equipo, avisos de sancionados
  y choques de horario, "En vivo" cuando alguien transmite en Twitch, partidos de la semana, últimos
  resultados y "Cómo vamos" en cada competencia.
- **Calendario:** todos los partidos, filtro por liga, vista de mes en la compu y suscripción al
  calendario del celular.
- **Tablas:** una por competencia o todas juntas, con flechas y forma reciente. Al terminar un
  torneo queda la tabla final con nuestro puesto y números de cierre hasta que empieza el siguiente.
- **Plantel, jugadores y rivales:** estadísticas de todo el historial, líderes, "El 11 más usado",
  ficha de cada jugador e historial contra cada rival.
- **Partidos:** resultado, estadísticas de los dos equipos, alineación con notas y MVP; la previa
  de los que faltan jugar.
- **Vitrina:** récords del club y títulos.
- **Estado:** cuándo se actualizó cada liga y si alguna falló.

**Cómo se mantiene**

- Datos de VPN, LVA, VPUG y EA SPORTS FC, sin cargar nada a mano. Se actualiza sola cada hora.
- Temporadas, ascensos, ediciones nuevas del juego y torneos terminados se toman solos.
- Si una liga falla, se conservan los datos anteriores y queda marcado en Estado; lo "actual" se
  apaga solo si una fuente deja de dar datos.
- Pruebas automáticas antes de cada publicación.
