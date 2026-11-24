# 00 · Decisiones confirmadas (20-nov-2026)

Este documento **manda sobre el resto**: si algo de otro doc contradice esto, vale lo de acá.

| Tema | Decisión |
|---|---|
| Costo | **$0**. Nada pago, ni hosting, ni dominio |
| Dirección | **https://vultursports.github.io** (organización gratis `vultursports` en GitHub) |
| Hosting / robot | GitHub Pages + GitHub Actions (repo público) |
| Avisos / Discord | **No.** Solo la página |
| Horario | Somos un **club argentino**: partidos siempre **desde las 22:00 hora argentina**. Todo se muestra en hora argentina y se agrupa por "noche de juego" |
| Fuentes | **Solo datos públicos**, lo que ve cualquier visitante. No se pide permiso ni se usan accesos internos |
| LVA | Se leen sus **páginas públicas** con un navegador automático (Playwright en GitHub Actions) |
| VPUG / VPN | Se usan los datos que sus propias páginas cargan públicamente, despacio y solo lo de Vultur y nuestras tablas |
| VPUG con cuenta | Excepción aprobada por el usuario: el fixture y los partidos de VPUG solo se ven con cuenta de jugador (cualquier jugador, no hace falta admin). El robot inicia sesión con una cuenta del club. Las credenciales van en `.env` (local, no se sube) y en los **secretos de GitHub** `VPUG_EMAIL` / `VPUG_PASSWORD`, nunca en el código. Recomendado cambiar la contraseña porque se escribió en el chat |
| Competencias | **Solo LVA, VPN y VPUG.** Copas y torneos sueltos quedan para más adelante |
| API de EA FC | **Solo para completar** (cambio del 22/11/2026): de EA se toman únicamente los partidos que coinciden con uno de nuestras competencias (misma hora y marcador; si hubo varios intentos seguidos contra el mismo rival porque se reinició el partido, vale el último completo). El resultado oficial es SIEMPRE el de la competencia, aunque EA diga otro (resultado técnico, sanción). Suma tiros, pases, entradas y atajadas por jugador, estadísticas del equipo cuando la liga no las publica, resultado provisorio hasta que la liga lo carga. Lo de la liga manda siempre y lo de EA no suma en los totales del plantel |
| Datos actuales | **Nunca información vieja donde va lo actual** (22/11/2026): todo lo que muestra un estado actual (por ejemplo, la Precisión del jugador) se calcula con datos recientes y desaparece solo si la fuente deja de responder. Lo de partidos terminados se guarda y se muestra siempre |
| Historial | Temporada actual y de acá en adelante (se acumula solo) |
| Plantel | **Automático**: el robot junta los nombres de cada liga, sugiere quién es quién y el mánager confirma o corrige en `config/plantel.yaml` |
| Escudo y colores | Se toman del perfil de **VPN** (alta calidad) |
| Idioma | **Español neutro**: nada de voseo ni expresiones rioplatenses |
| Logos de ligas | Se usan los **logos oficiales** de LVA, VPN y VPUG (tomados de sus webs) en lugar de las siglas en texto |
| Colores de ligas | El **color principal de cada liga**, tomado de su web: VPN azul (`#0e66b2`, aclarado a `#2f86d6` para fondo oscuro), VPUG celeste claro (`#bcdcf7`, el de las letras de su logo; su identidad es azul marino y celeste. El naranja de su web es un especial de Halloween que nunca cambiaron). LVA usa su **dorado** `#dace96` (su segundo color oficial), porque su azul `#396896` no se distingue del de VPN. Las victorias y el MVP van en el dorado del pico del escudo (`#c9a24a`), como pidió el usuario |
| Plantel | La sección se llama **Plantel** (no "Jugadores"): líderes, tabla ordenable por liga y ficha de cada jugador. Foto, dorsal y posición salen del plantel oficial en VPUG |
| Twitch | Cuando un integrante transmite (hoy: Corona_ruso, `coronaruso`), aparece "En vivo" en Inicio con el reproductor oficial de Twitch. El estado se consulta con decapi.me (gratis). Los canales se configuran en `config/ligas.yaml` → `club.transmisiones` |
| W.O. | Un partido que la liga da por aprobado antes de su fecha (equipo dado de baja) se marca "por W.O." |
| Orden de ligas | Siempre **VPN, LVA, VPUG** (selectores, filtros, fichas y créditos) |
| Vista previa al compartir | Imagen automática (`og.png`, 1200x630) con el próximo partido o los partidos de la noche, generada en cada actualización. Usa la dirección `club.url_sitio` de `config/ligas.yaml` |
| Avisos | En Inicio: sanciones vigentes de Vultur (LVA: página pública de sanciones; VPN: no habilitados del próximo partido; VPUG no las publica para jugadores) y choques de horario (menos de 30 min entre ligas distintas). Prueba visual: `python demo_sanciones.py` → `site-demo/` |
| Rivales | Página por rival con el historial en todas las ligas. Se unen solos si el **nombre base coincide** (sin eSports/eSp/FC, acentos ni mayúsculas) y el escudo se parece. **Ante la duda, separados**: un escudo igual con nombres sin relación no se une, y un equipo Reserva/Cantera/2 nunca se une con el principal. Uniones y separaciones a mano en `config/rivales.yaml` |
| Temporadas e historial | Se muestra **todo lo disponible** (el espacio no es problema): VPN desde jul 2024 (10 temporadas, ~180 partidos); VPUG solo tiene su T1; la LVA no publica torneos viejos. **Nunca se borra**: lo viejo queda guardado y se elige en el filtro |
| Filtro del Plantel | **Solo por liga**: "Temporada actual" (la que está en curso en cada liga, se ve al entrar), "Todo el historial" y cada temporada agrupada por liga (VPN T11, T10…, VPUG T1, LVA por torneo). Sin atajos por edición del juego (FC 26, FC 27…) |
| Partido | Posición en la tabla de cada equipo en "Hoy jugamos"; "Ver detalles" debajo de cada resultado; estadísticas del partido por equipo (tiros, pases, entradas, atajadas) cuando la liga las publica (VPN y VPUG) |
| El 11 más usado (Plantel) | Según el filtro de liga y temporada: la alineación más repetida (si dos empatan, la usada más recientemente) y, para cada puesto, quien más veces lo ocupó (sin repetir jugadores). Dorsal, posición, nota, PJ, goles y asistencias; MVP (mejor nota ajustada) marcado sobre el dorsal; banco con los siguientes. **El nombre de la formación nunca se calcula**: solo se muestra el que publica la liga (hoy solo VPN) |
| Posiciones | Salen de lo que publica cada liga (EA registra el puesto de cada partido); solo se unifican los códigos (LTD→LD, PO→POR). En la ficha y el plantel se muestra la posición más jugada en los últimos 20 partidos |
| Formaciones | Solo se muestra el nombre que publica VPN. Para la LVA y VPUG, el que VPN le dio a la misma alineación (partido de VPN más cercano en fecha); si no hay, sin nombre. Nunca se inventa. **Corrección del club**: en la 4-1-2-1-2, VPN registra los volantes como MD/MI pero son dos MC; la web los muestra como MC. Y en formaciones de dos puntas (sin DC), VPN llama DD/DI a los delanteros: se muestran como dos DC |
| Accesibilidad | Sin el enlace oculto "Ir al contenido" (pedido del usuario) |
| W.O. | Cuentan como cualquier resultado ("victoria es victoria") en récords, rachas y forma; solo se marcan "por W.O." |
| Vitrina | Sección propia. Títulos automáticos de la LVA (torneos con Vultur campeón) y de la vitrina oficial de VPN, más los cargados en `config/titulos.yaml`. Hoy: 0 títulos verificados en las tres ligas → vitrina vieja con telarañas (guiño cómico) con datos reales por liga |
| Página de estado | `estado.html`, enlazada en el pie: última actualización por liga, fallas y totales |
| Próximo partido en juego | La tarjeta muestra "Se está jugando" 15 minutos desde el inicio y después pasa sola al siguiente partido (lo hace el navegador con la hora real) |
| Esta semana | Los partidos de la noche quedan en la lista hasta que termina el día; si ya empezó y no hay resultado, "?" en gris con "Ver detalles" |
| Zonas de las tablas | Las que publica cada liga: VPN (líder, playoffs), LVA (Ascenso/Campeón, Clasifican, Descenso, con sus nombres) y VPUG (ascenso, reducido, descenso), con leyenda |
| Redes del club | No van (el club no tiene) |
| **Créditos a las ligas** | **Obligatorio.** Que no parezca que les sacamos la información: cada competencia aparece con su **nombre completo, logo, link a su web y sus redes**. En cada tabla, partido y estadística va "Fuente: LVA/VPN/VPUG →" con link a la página oficial. Habrá una sección "Nuestras competencias" en Inicio y en el pie de todas las páginas |
| Imágenes | Escudos de rivales, logos de ligas y escudo propio **tomados de las páginas de las ligas**, siempre con crédito |
| Cuenta de GitHub | **noahbyte0** (Claude la maneja con `gh`). El repo `vultur-sport` se crea al publicar. La organización `vultursports` (nombre libre) la tiene que crear el usuario desde la web: GitHub no deja crearla por comandos |
| Estilo | **Oscuro y agresivo**: fondo oscuro, colores del escudo, tipografía deportiva condensada, estilo transmisión de eSports |
| Público | **Plantel y vidriera por igual**: Inicio práctico (próximo partido, tablas) + secciones de club (plantel, estadísticas) |

## Primera versión (todo esto entra)
1. **Calendario unificado** + `.ics` para suscribirse desde el celular.
2. **Tablas de posiciones** de cada competencia, con Vultur destacado.
3. **Resultados y detalle de partido** (goleadores, asistencias, MVP, rating si la liga lo da).
4. **Estadísticas de jugadores** por liga y en total (ranking con rating ajustado).

## Queda afuera por ahora
Discord y avisos, copas sueltas, palmarés histórico, redes, placas para Instagram,
multi-club.
