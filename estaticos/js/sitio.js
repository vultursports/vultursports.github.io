// Cuenta regresiva del próximo partido
(() => {
  const t = document.querySelector("[data-cuenta]");
  const out = document.querySelector(".cuenta");
  if (!t || !out) return;
  const fin = new Date(t.dataset.cuenta).getTime();
  const tick = () => {
    const ms = fin - Date.now();
    if (ms <= 0) { out.textContent = ms > -45 * 60e3 ? "Se está jugando" : ""; return; }
    const d = Math.floor(ms / 864e5), h = Math.floor(ms / 36e5) % 24, m = Math.floor(ms / 6e4) % 60;
    out.textContent = d > 0 ? `Faltan ${d} d ${h} h` : `Faltan ${h} h ${String(m).padStart(2, "0")} min`;
  };
  tick();
  setInterval(tick, 30e3);
})();

// En vivo en Twitch: se consulta si algún canal del club está transmitiendo y, solo en ese caso,
// se muestra el reproductor oficial de Twitch. (Prueba: agregar ?vivo=nombre_de_canal a la URL.)
(() => {
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
  setInterval(revisar, 120e3);
})();

// Calendario: pestañas Próximos/Jugados y filtro por liga
(() => {
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
})();
