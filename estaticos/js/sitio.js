// Base común: cada parte del sitio se registra con VS.alCargar(fn). La función corre al abrir la página.
const VS = (window.VS = window.VS || { inits: [], timers: [] });
VS.alCargar = (fn) => { VS.inits.push(fn); fn(); };
VS.cadaTanto = (fn, ms) => VS.timers.push(setInterval(fn, ms));
// Preferencias de cada visitante (filtros, pestañas). Si el navegador no deja guardar, no pasa nada.
VS.guardar = (k, v) => { try { localStorage.setItem("vs:" + k, JSON.stringify(v)); } catch (e) { /* sin guardar */ } };
VS.recordar = (k) => { try { return JSON.parse(localStorage.getItem("vs:" + k)); } catch (e) { return null; } };
VS.esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
// "Noche" de juego en hora argentina: lo jugado hasta las 6 de la mañana cuenta para la noche anterior.
VS.nocheHoy = () => new Date(Date.now() - 9 * 36e5).toISOString().slice(0, 10);

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
      out.classList.toggle("jugando", ms <= 0);
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
    if (recordar) VS.guardar(tab.closest(".selector-comp") ? "tabla" : "cal-tab", tab.getAttribute("aria-controls"));
  };
  tabs.forEach((tab) => tab.addEventListener("click", () => elegir(tab, true)));
  // Abrir directo una competencia: tablas.html#comp-...
  const desdeUrl = location.hash && tabs.find((t) => "#" + t.getAttribute("aria-controls") === location.hash);
  const guardada = !desdeUrl && tabs.find((t) => [VS.recordar("tabla"), VS.recordar("cal-tab")].includes(t.getAttribute("aria-controls")));
  if (desdeUrl || guardada) elegir(desdeUrl || guardada, false);

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
  checks.forEach((c) => c.addEventListener("change", () => {
    VS.guardar("cal-ligas-off", checks.filter((x) => !x.checked).map((x) => x.value));
    aplicar();
    if (VS.dibujarMes) VS.dibujarMes();
  }));
  const apagadas = VS.recordar("cal-ligas-off") || [];
  if (apagadas.length && apagadas.length < checks.length) {
    checks.forEach((c) => (c.checked = !apagadas.includes(c.value)));
    aplicar();
  }
});

// "Hoy", "Mañana" y "Ayer" en los títulos de cada noche (se calcula en el navegador para que esté al día)
VS.alCargar(() => {
  const hoy = Date.parse(VS.nocheHoy());
  document.querySelectorAll(".noche[data-noche]").forEach((h) => {
    if (!h.dataset.txt) h.dataset.txt = h.textContent.trim();
    const rel = { 0: "Hoy", 1: "Mañana", "-1": "Ayer" }[Math.round((Date.parse(h.dataset.noche) - hoy) / 864e5)];
    const t = h.dataset.txt;
    h.textContent = rel ? `${rel}, ${t.charAt(0).toLowerCase()}${t.slice(1)}` : t;
  });
});

// Franja "Hoy jugamos" en todas las páginas (menos Inicio, que ya tiene la tarjeta del partido)
VS.alCargar(() => {
  const caja = document.getElementById("hoy-jugamos");
  if (!caja || caja.dataset.inicio === "si") return;
  const ps = JSON.parse(caja.dataset.partidos || "[]");
  const pintar = () => {
    const ahora = Date.now(), hoy = VS.nocheHoy();
    const lista = ps.filter((p) => p.noche === hoy && Date.parse(p.fin) > ahora);
    caja.hidden = !lista.length;
    if (!lista.length) return;
    caja.innerHTML = `<div class="hj-in"><b>Hoy jugamos</b>` + lista.map((p) => {
      const ya = Date.parse(p.inicio) <= ahora;
      return `<a href="${p.pagina}"${ya ? ' class="en-juego"' : ""}><span class="hj-hora">${ya ? "Se está jugando" : p.hora}</span> vs ${VS.esc(p.rival)} <small>${VS.esc(p.liga)}</small></a>`;
    }).join("") + `</div>`;
  };
  pintar();
  VS.cadaTanto(pintar, 60e3);
});

// Barra superior: se esconde al bajar y vuelve al subir. Botón para volver arriba en páginas largas.
(() => {
  const cab = document.getElementById("cabecera"), arriba = document.getElementById("arriba");
  let ultimo = scrollY, pendiente = false;
  addEventListener("scroll", () => {
    if (pendiente) return;
    pendiente = true;
    requestAnimationFrame(() => {
      const y = scrollY;
      if (cab && Math.abs(y - ultimo) > 6) {
        cab.classList.toggle("oculta", y > ultimo && y > 140 && !document.querySelector("dialog[open]"));
        ultimo = y;
      }
      if (arriba) arriba.hidden = y < innerHeight * 1.5;
      pendiente = false;
    });
  }, { passive: true });
  if (arriba) arriba.addEventListener("click", () => scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }));
})();

// Buscador de jugadores y rivales (atajo en la computadora: tecla /)
(() => {
  const dlg = document.getElementById("buscador"), btn = document.getElementById("btn-buscar");
  if (!dlg || !btn) return;
  if (!dlg.showModal) { btn.hidden = true; return; }
  const inp = document.getElementById("buscar-txt"), res = document.getElementById("buscar-res");
  const norm = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");
  let datos = null;
  const cargar = () => datos || (datos = fetch("/buscar.json").then((r) => r.json())
    .then((l) => l.map((x) => ({ ...x, k: [x.n, ...(x.o || [])].map(norm) })))
    .catch(() => { datos = null; return []; }));
  const pintar = async () => {
    const q = norm(inp.value), l = await cargar();
    if (!q) { res.innerHTML = ""; return; }
    const empieza = (x) => (x.k.some((k) => k.startsWith(q)) ? 0 : 1);
    const hallados = l.filter((x) => x.k.some((k) => k.includes(q)))
      .sort((a, b) => empieza(a) - empieza(b) || (a.t === b.t ? a.n.localeCompare(b.n) : a.t === "Jugador" ? -1 : 1)).slice(0, 12);
    res.innerHTML = hallados.length
      ? hallados.map((x) => `<li><a href="${x.u}"><span>${VS.esc(x.n)}</span><small>${x.t}</small></a></li>`).join("")
      : `<li class="sin-res">No encontramos «${VS.esc(inp.value)}».</li>`;
  };
  const abrir = () => { dlg.showModal(); inp.select(); cargar(); };
  btn.addEventListener("click", abrir);
  inp.addEventListener("input", pintar);
  inp.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const a = res.querySelector("a");
    if (a) location.href = a.href;
  });
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !dlg.open && !/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) { e.preventDefault(); abrir(); }
  });
})();

// Compartir partido o jugador (WhatsApp, etc.); si el navegador no puede, copia el enlace
VS.alCargar(() => {
  document.querySelectorAll(".compartir").forEach((b) => {
    if (!navigator.share && !(navigator.clipboard && window.isSecureContext)) return;
    b.hidden = false;
    b.addEventListener("click", async () => {
      if (navigator.share) {
        try { await navigator.share({ title: document.title, url: location.href }); } catch (e) { /* cancelado */ }
        return;
      }
      try {
        await navigator.clipboard.writeText(location.href);
        b.textContent = "Enlace copiado";
        setTimeout(() => (b.textContent = "Compartir"), 2000);
      } catch (e) { /* sin permiso */ }
    });
  });
});

// Tablas: en la computadora, ver todas las competencias juntas (se recuerda la elección)
VS.alCargar(() => {
  const b = document.getElementById("ver-todas");
  if (!b) return;
  const pag = b.closest(".pagina");
  const paneles = [...pag.querySelectorAll('.comp[role="tabpanel"]')];
  const tabs = [...pag.querySelectorAll('.selector-comp [role="tab"]')];
  const poner = (on) => {
    b.setAttribute("aria-pressed", on);
    b.textContent = on ? "Ver de a una" : "Ver todas juntas";
    pag.classList.toggle("todas-juntas", on);
    const sel = tabs.find((t) => t.getAttribute("aria-selected") === "true") || tabs[0];
    paneles.forEach((p) => (p.hidden = !on && p.id !== sel.getAttribute("aria-controls")));
  };
  b.addEventListener("click", () => {
    const on = b.getAttribute("aria-pressed") !== "true";
    poner(on);
    VS.guardar("tablas-juntas", on);
  });
  if (VS.recordar("tablas-juntas") && matchMedia("(min-width: 1000px)").matches) poner(true);
});

// Calendario: vista de mes (computadora). Respeta el filtro de ligas.
VS.alCargar(() => {
  const cont = document.getElementById("vista-mes"), nodo = document.getElementById("datos-cal");
  if (!cont || !nodo) return;
  const ps = JSON.parse(nodo.textContent);
  const botones = [...document.querySelectorAll(".vista-cal [data-vista]")];
  const seg = document.getElementById("seg-lista");
  const listas = ["lista-proximos", "lista-jugados"].map((id) => document.getElementById(id));
  const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
  const DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
  const pad = (n) => String(n).padStart(2, "0");
  const hoy0 = VS.nocheHoy();
  let mes = [+hoy0.slice(0, 4), +hoy0.slice(5, 7) - 1];
  const dibujar = () => {
    if (cont.hidden) return;
    const [a, m] = mes, hoy = VS.nocheHoy();
    const on = new Set([...document.querySelectorAll(".filtros input")].filter((c) => c.checked).map((c) => c.value));
    const porDia = {};
    ps.forEach((p) => { if (on.has(p.liga)) (porDia[p.noche] = porDia[p.noche] || []).push(p); });
    const vacias = (new Date(Date.UTC(a, m, 1)).getUTCDay() + 6) % 7, dias = new Date(Date.UTC(a, m + 1, 0)).getUTCDate();
    let celdas = '<div class="dia-mes fuera"></div>'.repeat(vacias);
    for (let d = 1; d <= dias; d++) {
      const iso = `${a}-${pad(m + 1)}-${pad(d)}`, lista = porDia[iso] || [];
      celdas += `<div class="dia-mes${iso === hoy ? " hoy" : ""}"><span class="dm-num">${d}</span>` + lista.map((p) =>
        `<a class="dm-p liga-${p.liga}${p.res ? " r-" + p.res : ""}" href="${p.pagina}" title="${VS.esc(p.corto)} · ${p.hora} vs ${VS.esc(p.rival)}">` +
        `<span class="dm-h">${p.res ? `${p.gf}–${p.gc}` : p.hora}</span><span class="dm-r">${VS.esc(p.rival)}</span></a>`).join("") + `</div>`;
    }
    cont.innerHTML = `<div class="mes-enc"><button type="button" data-d="-1" aria-label="Mes anterior">‹</button>` +
      `<h2>${MESES[m]} ${a}</h2><button type="button" data-d="1" aria-label="Mes siguiente">›</button></div>` +
      `<div class="grilla-mes">${DIAS.map((x) => `<div class="dm-dia">${x}</div>`).join("")}${celdas}</div>`;
    cont.querySelectorAll("[data-d]").forEach((b) => b.addEventListener("click", () => {
      let [a2, m2] = mes;
      m2 += +b.dataset.d;
      if (m2 < 0) { m2 = 11; a2--; }
      if (m2 > 11) { m2 = 0; a2++; }
      mes = [a2, m2];
      dibujar();
    }));
  };
  VS.dibujarMes = dibujar;
  const poner = (v) => {
    const enMes = v === "mes";
    botones.forEach((b) => b.setAttribute("aria-pressed", b.dataset.vista === v));
    cont.hidden = !enMes;
    if (seg) seg.hidden = enMes;
    const sel = seg && seg.querySelector('[aria-selected="true"]');
    listas.forEach((l) => (l.hidden = enMes || Boolean(sel && l.id !== sel.getAttribute("aria-controls"))));
    dibujar();
  };
  botones.forEach((b) => b.addEventListener("click", () => { poner(b.dataset.vista); VS.guardar("cal-vista", b.dataset.vista); }));
  if (VS.recordar("cal-vista") === "mes" && matchMedia("(min-width: 760px)").matches) poner("mes");
});
