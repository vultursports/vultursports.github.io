// Base común: cada parte del sitio se registra con VS.alCargar(fn). La función corre al abrir la página.
const VS = (window.VS = window.VS || { inits: [], timers: [] });
VS.alCargar = (fn) => { VS.inits.push(fn); fn(); };
VS.cadaTanto = (fn, ms) => VS.timers.push(setInterval(fn, ms));

// Próximo partido: cada tarjeta muestra la cuenta regresiva; cuando un partido empieza, su tarjeta dice
// "Se está jugando" hasta que empieza el siguiente de esa noche (o 30 minutos si es el último, data-fin)
// y después la página pasa sola al siguiente partido.
// En las listas, un partido que ya empezó y no tiene resultado muestra "?" con "Ver detalles".
VS.alCargar(() => {
  const EN_JUEGO = 30 * 60e3; // por si falta data-fin
  const tarjetas = [...document.querySelectorAll(".tarjeta-proximo")];
  const vacia = document.querySelector(".proximo.vacio");
  const tick = () => {
    const ahora = Date.now();
    const fin = (t) => (t.dataset.fin ? new Date(t.dataset.fin).getTime() : new Date(t.dataset.inicio).getTime() + EN_JUEGO);
    const actual = tarjetas.find((t) => fin(t) > ahora);
    tarjetas.forEach((t) => (t.hidden = t !== actual));
    if (vacia) vacia.hidden = Boolean(actual);
    if (actual) {
      const out = actual.querySelector(".cuenta");
      const ms = new Date(actual.dataset.inicio).getTime() - ahora;
      if (ms <= 0) out.textContent = "Se está jugando";
      else {
        const d = Math.floor(ms / 864e5), h = Math.floor(ms / 36e5) % 24, m = Math.floor(ms / 6e4) % 60;
        out.textContent = d > 0 ? `Faltan ${d} d ${h} h` : h > 0 ? `Faltan ${h} h ${String(m).padStart(2, "0")} min` : `Faltan ${m} min`;
      }
    }
    document.querySelectorAll("li.partido[data-inicio], .proximo-titulo [data-inicio]").forEach((el) => {
      const empezo = new Date(el.dataset.inicio).getTime() <= ahora;
      const antes = el.querySelector(".antes"), pend = el.querySelector(".pendiente, .pendiente-txt");
      if (antes) antes.hidden = empezo;
      if (pend) pend.hidden = !empezo;
    });
  };
  tick();
  VS.cadaTanto(tick, 30e3);
});

// En vivo en Twitch: se consulta si algún canal del club está transmitiendo y, solo en ese caso,
// se muestra el reproductor oficial de Twitch. (Prueba: agregar ?vivo=nombre_de_canal a la URL.)
VS.alCargar(() => {
  const caja = document.querySelector(".en-vivo");
  if (!caja) return;
  const prueba = new URLSearchParams(location.search).get("vivo");
  const canales = prueba ? [{ canal: prueba, jugador: prueba }] : JSON.parse(caja.dataset.canales || "[]");
  let mostrando = null;
  const revisar = async () => {
    for (const { canal, jugador } of canales) {
      let vivo = false;
      try {
        const r = await fetch(`https://decapi.me/twitch/uptime/${encodeURIComponent(canal)}`);
        const t = (await r.text()).toLowerCase();
        vivo = r.ok && !t.includes("offline") && !t.includes("error") && !t.includes("not found");
      } catch (e) { vivo = false; }
      if (vivo) {
        if (mostrando !== canal) {
          mostrando = canal;
          caja.querySelector(".envivo-quien").textContent = `${jugador || canal} está transmitiendo ahora.`;
          caja.querySelector(".envivo-link").href = `https://www.twitch.tv/${canal}`;
          caja.querySelector(".envivo-video").innerHTML =
            `<iframe src="https://player.twitch.tv/?channel=${encodeURIComponent(canal)}&parent=${location.hostname}&muted=true" title="Transmisión de ${canal} en Twitch" allowfullscreen></iframe>`;
          caja.hidden = false;
        }
        return;
      }
    }
    if (mostrando) { caja.hidden = true; caja.querySelector(".envivo-video").innerHTML = ""; mostrando = null; }
  };
  revisar();
  VS.cadaTanto(revisar, 120e3);
});

// Calendario: pestañas Próximos/Jugados y filtro por liga
VS.alCargar(() => {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const elegir = (tab, recordar) => {
    tabs.forEach((t) => {
      const activo = t === tab;
      t.setAttribute("aria-selected", activo);
      document.getElementById(t.getAttribute("aria-controls")).hidden = !activo;
    });
    if (recordar && tab.closest(".selector-comp")) history.replaceState(null, "", "#" + tab.getAttribute("aria-controls"));
  };
  tabs.forEach((tab) => tab.addEventListener("click", () => elegir(tab, true)));
  // Abrir directo una competencia: tablas.html#comp-...
  const desdeUrl = location.hash && tabs.find((t) => "#" + t.getAttribute("aria-controls") === location.hash);
  if (desdeUrl) elegir(desdeUrl, false);

  // Tablas ordenables (Jugadores)
  document.querySelectorAll("table.ordenable:not(#tabla-plantel)").forEach((tabla) => {
    const ths = [...tabla.querySelectorAll("thead th")];
    ths.forEach((th, i) => {
      const b = th.querySelector("button");
      if (!b) return;
      b.addEventListener("click", () => {
        const asc = th.getAttribute("aria-sort") === "descending";
        ths.forEach((x) => x.removeAttribute("aria-sort"));
        th.setAttribute("aria-sort", asc ? "ascending" : "descending");
        const cuerpo = tabla.tBodies[0];
        const val = (tr) => parseFloat(tr.children[i].dataset.v || "0");
        [...cuerpo.rows].sort((a, b2) => (asc ? val(a) - val(b2) : val(b2) - val(a))).forEach((tr) => cuerpo.appendChild(tr));
      });
    });
  });

  const checks = [...document.querySelectorAll(".filtros input")];
  if (!checks.length) return;
  const aplicar = () => {
    const on = new Set(checks.filter((c) => c.checked).map((c) => c.value));
    document.querySelectorAll(".partido[data-liga]").forEach((li) => { li.hidden = !on.has(li.dataset.liga); });
    // Ocultar el título de la noche si no le queda ningún partido visible
    document.querySelectorAll(".noche").forEach((h) => {
      const ul = h.nextElementSibling;
      h.hidden = ul && ![...ul.children].some((li) => !li.hidden);
      if (ul) ul.hidden = h.hidden;
    });
  };
  checks.forEach((c) => c.addEventListener("change", aplicar));
});
