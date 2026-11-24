// Plantel: estadísticas filtradas por liga y temporada, calculadas en el navegador.
VS.alCargar(() => {
  const nodo = document.getElementById("datos-plantel");
  if (!nodo) return;
  const D = JSON.parse(nodo.textContent);
  const tbody = document.querySelector("#tabla-plantel tbody");
  const ths = [...document.querySelectorAll("#tabla-plantel thead th[data-campo]")];
  const selT = document.getElementById("temporada");
  const botones = [...document.querySelectorAll(".filtros-plantel [data-liga]")];
  const lideres = document.getElementById("lideres");
  const vacio = document.getElementById("plantel-vacio");
  let liga = "todas", orden = { campo: "pos", asc: true }, verMasLideres = false;
  // Copia de todas las temporadas (por liga) para rearmar la lista según la liga elegida
  const grupos = [...selT.querySelectorAll("optgroup")].map((g) => ({
    label: g.label, opciones: [...g.querySelectorAll("option")].map((o) => ({ value: o.value, text: o.textContent, liga: o.dataset.liga })),
  }));
  function rearmarTemporadas() {
    const actual = selT.value;
    selT.querySelectorAll("optgroup").forEach((g) => g.remove());
    for (const g of grupos) {
      const ops = g.opciones.filter((o) => liga === "todas" || o.liga === liga);
      if (!ops.length) continue;
      const og = document.createElement("optgroup");
      og.label = g.label;
      for (const o of ops) {
        const op = new Option(o.text, o.value);
        op.dataset.liga = o.liga;
        og.appendChild(op);
      }
      selT.appendChild(og);
    }
    // Si la temporada elegida ya no está en la lista, volver a "Temporada actual"
    selT.value = [...selT.options].some((o) => o.value === actual) ? actual : "actual";
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const avatar = (j, t) => `<span class="avatar${j.dorsal ? "" : " sin-dorsal"}" style="--t: ${t}px" aria-hidden="true">${esc(j.dorsal || (j.alias || "?")[0].toUpperCase())}</span>`;
  const n1 = (x) => (x == null ? "" : x.toFixed(1));

  // Códigos de posición unificados entre ligas y su lugar en la cancha (x: izquierda→derecha, y: arriba = ataque)
  const ALIAS_POS = { PO: "POR", GK: "POR", LTD: "LD", LTI: "LI", CAD: "LD", CAI: "LI" };
  const normPos = (p) => ALIAS_POS[p] || p || "";
  const LUGAR = {
    POR: [50, 91], DFC: [50, 76], LD: [86, 71], LI: [14, 71], MCD: [50, 61], MC: [50, 47], MD: [86, 44],
    MI: [14, 44], MCO: [50, 31], DC: [50, 11], DD: [70, 13], DI: [30, 13], ED: [87, 17], EI: [13, 17], SD: [50, 22],
  };

  const ORDEN_POS = ["POR", "DFC", "LI", "LD", "MCD", "MC", "MI", "MD", "MCO", "EI", "ED", "SD", "DI", "DD", "DC"];
  const posPrincipal = (f) => (Object.entries(f.pos).sort((a, b) => b[1] - a[1])[0] || [""])[0];
  const ordenPos = (f) => { const i = ORDEN_POS.indexOf(posPrincipal(f)); return i < 0 ? 99 : i; };

  function enAlcance(lg, temp) {
    const t = selT.value;
    if (liga !== "todas" && lg !== liga) return false;
    if (t === "actual" && !D.actuales.includes(temp)) return false;
    if (t.startsWith("t:") && temp !== t.slice(2)) return false;
    return true;
  }

  function calcular() {
    const filas = {};
    for (const [jid, lg, temp, ed, g, a, mvp, nota, pos, , vi, ta, tr, ea] of D.ap) {
      if (!enAlcance(lg, temp)) continue;
      const f = (filas[jid] ||= { id: jid, pj: 0, g: 0, a: 0, mvp: 0, vi: 0, ta: 0, tr: 0, notas: [], pos: {},
        eapj: 0, tiros: 0, pases: 0, pasesInt: 0, ent: 0, entInt: 0, ataj: 0 });
      f.pj++; f.g += g; f.a += a; f.mvp += mvp; f.vi += vi || 0; f.ta += ta || 0; f.tr += tr || 0;
      if (ea) {
        f.eapj++; f.tiros += ea[0]; f.pases += ea[1]; f.pasesInt += ea[2]; f.ent += ea[3]; f.entInt += ea[4]; f.ataj += ea[5];
      }
      if (nota != null) f.notas.push(nota);
      const p = normPos(pos);
      if (p) f.pos[p] = (f.pos[p] || 0) + 1;
    }
    return Object.values(filas).map((f) => ({
      ...f, ga: f.g + f.a,
      // Porcentajes de EA: solo con el mínimo de partidos con esos datos
      pp: f.eapj >= D.eaMinimo && f.pasesInt ? (100 * f.pases) / f.pasesInt : null,
      tiros: f.eapj ? f.tiros : null, ent: f.eapj ? f.ent : null,
      nota: f.notas.length ? f.notas.reduce((x, y) => x + y, 0) / f.notas.length : null,
      // Nota ajustada: suma partidos "neutros" para que no gane alguien con muy pocos partidos
      aj: f.notas.length ? (f.notas.reduce((x, y) => x + y, 0) + D.notaBase * D.pesoBase) / (f.notas.length + D.pesoBase) : null,
    }));
  }

  const EA_CAMPOS = new Set(["tiros", "pp", "ent", "ataj"]);
  // Datos de EA: en la temporada actual solo si siguen llegando (si la API se vence, no se muestran
  // números viejos como actuales); en temporadas pasadas o todo el historial, siempre.
  const conEA = (filas) => (selT.value !== "actual" || D.eaVigente) && filas.some((f) => f.eapj > 0);

  function lider(filas, campo, titulo, unidad) {
    let cand = filas.filter((f) => (campo === "nota" ? f.nota != null && f.pj >= D.minimoNota : f[campo] > 0));
    if (campo === "pp") cand = filas.filter((f) => f.pp != null);
    // Mejor nota: el promedio más alto con el mínimo de partidos; en empate, el que jugó más
    // Vallas invictas: en empate va primero el que más jugó de arquero
    const arq = (f) => f.pos.POR || 0;
    cand.sort((x, y) => campo === "nota" || campo === "pp" ? (y[campo] - x[campo]) || (y.pj - x.pj)
      : (y[campo] - x[campo]) || (campo === "vi" ? arq(y) - arq(x) : 0) || (x.pj - y.pj));
    const f = cand[0];
    if (!f) return `<article class="lider"><h2>${titulo}</h2><p class="vacio">Sin datos.</p></article>`;
    const j = D.jugadores[f.id];
    const valor = campo === "nota" ? n1(f.nota) : campo === "pp" ? `${Math.round(f.pp)}%` : f[campo];
    const pj = EA_CAMPOS.has(campo) ? f.eapj : f.pj;
    return `<article class="lider${EA_CAMPOS.has(campo) ? " lider-ea" : ""}"><h2>${titulo}</h2><a href="${j.pagina}">${avatar(j, 44)}<span class="lider-nombre">${esc(j.alias)}</span></a>
      <p class="lider-valor"><b>${valor}</b> ${unidad}${campo === "pj" ? "" : ` en ${pj} PJ`}</p></article>`;
  }

  // El 11 más usado: formación más repetida y, para cada puesto, quien más veces lo ocupó
  function once(filas) {
    // VPN: se usa la "Alineación habitual" oficial que el club carga en VPN (temporada en curso)
    const t = selT.value;
    if (D.oficial && liga === "vpn" && (t === "actual" || (t.startsWith("t:") && D.actuales.includes(t.slice(2))))) {
      const porId = Object.fromEntries(filas.map((f) => [f.id, f]));
      const slots = [], asignado = {}, usado = new Set();
      D.oficial.jugadores.forEach((j, i) => {
        if (!D.jugadores[j.id]) return;  // jugador sin ficha en la web
        slots.push({ i, pos: j.pos });
        asignado[i] = porId[j.id] || { id: j.id, pj: 0, g: 0, a: 0, nota: null, pos: {} };
        usado.add(j.id);
      });
      const banco = filas.filter((f) => !usado.has(f.id)).sort((a, b) => b.pj - a.pj).slice(0, 9);
      return { slots, asignado, formacion: D.oficial.formacion, oficial: true, banco };
    }
    const porPartido = {};
    for (const [jid, lg, temp, , , , , , pos, pid] of D.ap) {
      if (!enAlcance(lg, temp) || !pos) continue;
      (porPartido[pid] ||= []).push(normPos(pos));
    }
    // Misma regla que once_mas_usado() en build.py (la previa de los partidos): si se cambia una, cambiar la otra
    const conteo = {}, partidosDe = {}, ultima = {};
    for (const [pid, ps] of Object.entries(porPartido)) {
      if (ps.length < 10) continue;  // partidos con datos incompletos no cuentan
      const k = ps.slice().sort().join(",");
      conteo[k] = (conteo[k] || 0) + 1;
      (partidosDe[k] ||= []).push(pid);
      const f = D.fecha[pid] || "";
      if (!ultima[k] || f > ultima[k]) ultima[k] = f;
    }
    // Empate en cantidad de partidos: gana la formación usada más recientemente
    const top = Object.entries(conteo).sort((a, b) => b[1] - a[1] || (ultima[b[0]] > ultima[a[0]] ? 1 : ultima[b[0]] < ultima[a[0]] ? -1 : 0))[0];
    if (!top) return null;
    const slots = top[0].split(",").map((p, i) => ({ i, pos: p }));
    const total = Object.values(conteo).reduce((a, b) => a + b, 0);
    // Asignación: primero los pares (jugador, puesto) con más partidos; cada jugador y puesto una sola vez
    const pares = [];
    for (const f of filas) for (const s of slots) if (f.pos[s.pos]) pares.push([f.pos[s.pos], f, s]);
    const cmpId = (x, y) => (x.id < y.id ? -1 : x.id > y.id ? 1 : 0);
    pares.sort((a, b) => b[0] - a[0] || b[1].pj - a[1].pj || cmpId(a[1], b[1]) || a[2].i - b[2].i);
    const usado = new Set(), asignado = {};
    for (const [, f, s] of pares) {
      if (usado.has(f.id) || asignado[s.i]) continue;
      usado.add(f.id); asignado[s.i] = f;
    }
    // Puestos sin dueño: el jugador libre con más partidos
    for (const s of slots) {
      if (asignado[s.i]) continue;
      const libre = filas.filter((f) => !usado.has(f.id)).sort((a, b) => b.pj - a.pj || cmpId(a, b))[0];
      if (libre) { usado.add(libre.id); asignado[s.i] = libre; }
    }
    // Nombre de la formación: el que publicó la liga en esos partidos (no se calcula). Si la liga no lo publica, no hay nombre.
    const nombres = {};
    for (const pid of partidosDe[top[0]] || []) if (D.form[pid]) nombres[D.form[pid]] = (nombres[D.form[pid]] || 0) + 1;
    const formacion = (Object.entries(nombres).sort((a, b) => b[1] - a[1])[0] || [""])[0];
    const banco = filas.filter((f) => !usado.has(f.id)).sort((a, b) => b.pj - a.pj).slice(0, 9);
    return { slots, asignado, formacion, veces: top[1], total, banco };
  }

  // x de cada jugador (misma regla que build.py): si una línea tiene un puesto repetido
  // (p. ej. dos LI), toda la línea se reparte a lo ancho para que nadie quede fuera ni encimado.
  const LINEA = { LI: "def", DFC: "def", LD: "def", MI: "med", MC: "med", MD: "med", EI: "del", DI: "del", DC: "del", DD: "del", ED: "del" };
  const BANDAS = new Set(["LI", "LD", "MI", "MD", "EI", "ED"]);
  function posicionesX(slots) {
    const xs = new Map();
    const grupos = {};
    slots.forEach((s) => {
      xs.set(s, (LUGAR[s.pos] || [50])[0]);
      (grupos[LINEA[s.pos] || s.pos] ||= []).push(s);
    });
    for (const g of Object.values(grupos)) {
      if (g.length === new Set(g.map((s) => s.pos)).size) continue;
      g.sort((a, b) => (LUGAR[a.pos] || [50])[0] - (LUGAR[b.pos] || [50])[0]);
      const n = g.length;
      const lado = g.some((s) => BANDAS.has(s.pos));
      const paso = Math.min(n === 2 ? 34 : 26, 76 / (n - 1));
      g.forEach((s, k) => xs.set(s, lado ? 14 + (k * 72) / (n - 1) : 50 + (k - (n - 1) / 2) * paso));
    }
    return xs;
  }

  function dibujarOnce(filas) {
    const cancha = document.getElementById("cancha");
    const bancoEl = document.getElementById("banco");
    const etiqueta = document.getElementById("once-formacion");
    const o = once(filas);
    if (!o) { cancha.innerHTML = `<p class="vacio">Sin alineaciones para esta selección.</p>`; bancoEl.innerHTML = ""; etiqueta.textContent = ""; return; }
    etiqueta.textContent = o.oficial ? `${o.formacion}, alineación habitual que publica el club en VPN`
      : (o.formacion ? `${o.formacion}, ` : "") + `usada en ${o.veces} de ${o.total} partidos`;
    // Repartir horizontalmente a los que comparten puesto (por ejemplo, dos DFC)
    const porPos = {};
    o.slots.forEach((s) => (porPos[s.pos] ||= []).push(s));
    const html = [];
    // MVP del 11: el de mejor nota (ajustada por partidos, con el mínimo de partidos de "Mejor nota")
    const candidatos = Object.values(o.asignado).filter((f) => f.nota != null && f.pj >= D.minimoNota);
    const mvp = candidatos.sort((a, b) => (b.nota - a.nota) || (b.pj - a.pj))[0];
    const xDe = posicionesX(o.slots);
    for (const [pos, lista] of Object.entries(porPos)) {
      const [, by] = LUGAR[pos] || [50, 50];
      lista.forEach((s) => {
        const x = xDe.get(s);
        const f = o.asignado[s.i];
        if (!f) return;
        const j = D.jugadores[f.id];
        const esMvp = mvp && f.id === mvp.id;
        html.push(`<a role="listitem" class="ficha-cancha${esMvp ? " es-mvp" : ""}" style="left:${x}%;top:${by}%" href="${j.pagina}"${esMvp ? ' title="Mejor nota del 11"' : ""}>
          ${avatar(j, 34)}${esMvp ? '<b class="fc-mvp">MVP</b>' : ""}<span class="fc-nombre">${esc(j.alias)}</span>
          <span class="fc-datos">${pos}${f.nota != null ? ` <b>${n1(f.nota)}</b>` : ""}</span>
          <span class="fc-datos">${f.pj} PJ${f.g ? `, ${f.g} G` : ""}${f.a ? `, ${f.a} A` : ""}</span></a>`);
      });
    }
    cancha.innerHTML = `<div class="lineas" aria-hidden="true"><i class="medio"></i><i class="circulo"></i><i class="area arriba"></i><i class="area abajo"></i></div>` + html.join("");
    bancoEl.innerHTML = o.banco.map((f) => {
      const j = D.jugadores[f.id];
      const pos = Object.entries(f.pos).sort((a, b) => b[1] - a[1])[0];
      return `<li><a href="${j.pagina}">${avatar(j, 28)}<span class="bn-nombre">${esc(j.alias)}</span>
        <span class="bn-datos">${pos ? pos[0] + ", " : ""}${f.pj} PJ${f.nota != null ? `, nota ${n1(f.nota)}` : ""}</span></a></li>`;
    }).join("") || `<li class="vacio">Sin suplentes con partidos.</li>`;
  }

  // Quién juega en cada puesto: hasta 3 jugadores por posición (los que más partidos jugaron ahí)
  // Lugares del mapa: más separados que en el 11 porque cada puesto lleva hasta 3 nombres
  const MAPA = { POR: [50, 93], DFC: [50, 77], LD: [84, 71], LI: [16, 71], MCD: [50, 61], MC: [50, 46], MD: [84, 45], MI: [16, 45],
    MCO: [50, 31], SD: [50, 20], DC: [50, 8], DD: [83, 11], DI: [17, 11], ED: [84, 23], EI: [16, 23] };
  function dibujarMapa(filas) {
    const mapa = document.getElementById("mapa");
    if (!mapa) return;
    const porPos = {};
    for (const f of filas) for (const [p, n] of Object.entries(f.pos)) (porPos[p] ||= []).push([n, f]);
    const html = [];
    for (const [pos, lista] of Object.entries(porPos)) {
      if (!MAPA[pos]) continue;
      const [x, y] = MAPA[pos];
      lista.sort((a, b) => b[0] - a[0] || b[1].pj - a[1].pj);
      const total = lista.reduce((s, [n]) => s + n, 0);
      html.push(`<div role="listitem" class="mapa-pos-item" style="left:${x}%;top:${y}%"><b class="mp-pos">${pos}</b>` +
        lista.slice(0, 3).map(([n, f]) => { const j = D.jugadores[f.id];
          return `<a href="${j.pagina}"><span>${esc(j.alias)}</span><small>${n}</small></a>`; }).join("") +
        (lista.length > 3 ? `<small class="mp-mas">+${lista.length - 3} más</small>` : "") +
        `<span class="sr">${total} partidos en total</span></div>`);
    }
    mapa.innerHTML = html.length
      ? `<div class="lineas" aria-hidden="true"><i class="medio"></i><i class="circulo"></i><i class="area arriba"></i><i class="area abajo"></i></div>` + html.join("")
      : `<p class="vacio">Sin posiciones para esta selección.</p>`;
  }

  // Destacados: solo los tops de la liga (y temporada) elegidas; si no queda ninguno, se oculta
  const destSec = document.getElementById("destacados");
  function dibujarDestacados() {
    if (!destSec) return;
    const t = selT.value.startsWith("t:") ? selT.value.slice(2) : null;
    destSec.querySelectorAll(".dest-top").forEach((li) => {
      li.hidden = !((liga === "todas" || li.dataset.liga === liga) && (!t || li.dataset.temp === t));
    });
    destSec.querySelectorAll(".dest-fila").forEach((f) => { f.hidden = !f.querySelector(".dest-top:not([hidden])"); });
    destSec.hidden = !destSec.querySelector(".dest-fila:not([hidden])");
  }

  function dibujar() {
    // Si se eligió una temporada puntual, la liga queda fija en la de esa temporada
    const opt = selT.selectedOptions[0];
    if (opt && opt.dataset.liga) {
      liga = opt.dataset.liga;
    }
    botones.forEach((b) => b.setAttribute("aria-pressed", b.dataset.liga === liga));
    VS.guardar("plantel", { liga, temporada: selT.value });

    const filas = calcular();
    dibujarOnce(filas);
    dibujarDestacados();
    const ea = conEA(filas);
    // 6 a la vista y el resto con "Ver más". Sin datos de EA, sus lugares los ocupan Mejor nota y Más partidos.
    const L = {
      g: () => lider(filas, "g", "Goleador", "goles"), a: () => lider(filas, "a", "Asistidor", "asistencias"),
      mvp: () => lider(filas, "mvp", "Más veces MVP", "MVP"), nota: () => lider(filas, "nota", "Mejor nota", "de promedio"),
      vi: () => lider(filas, "vi", "Más vallas invictas", "vallas invictas"), pj: () => lider(filas, "pj", "Más partidos", "partidos"),
      tiros: () => lider(filas, "tiros", "Más tiros", "tiros"), pp: () => lider(filas, "pp", "Mejor pase", "de pases completados"),
      ent: () => lider(filas, "ent", "Más entradas ganadas", "entradas"), ataj: () => lider(filas, "ataj", "Más atajadas", "atajadas"),
    };
    const vista = ea ? ["g", "a", "mvp", "pp", "ent", "vi"] : ["g", "a", "mvp", "nota", "pj", "vi"];
    const resto = ea ? ["nota", "pj", "tiros", "ataj"] : [];
    lideres.innerHTML = vista.map((k) => L[k]()).join("") + (resto.length
      ? `<div class="lideres-mas" id="lideres-mas"${verMasLideres ? "" : " hidden"}>${resto.map((k) => L[k]()).join("")}</div>
         <button type="button" class="ver-mas lideres-btn" aria-expanded="${verMasLideres}" aria-controls="lideres-mas">${verMasLideres ? "Ver menos" : "Ver más"}</button>`
      : "");
    const btnMas = lideres.querySelector(".lideres-btn");
    if (btnMas) btnMas.addEventListener("click", () => {
      verMasLideres = !verMasLideres;
      document.getElementById("lideres-mas").hidden = !verMasLideres;
      btnMas.textContent = verMasLideres ? "Ver menos" : "Ver más";
      btnMas.setAttribute("aria-expanded", verMasLideres);
    });
    document.querySelectorAll("#tabla-plantel .col-ea").forEach((th) => (th.hidden = !ea));
    document.getElementById("nota-ea").hidden = !ea;
    if (!ea && EA_CAMPOS.has(orden.campo)) orden = { campo: "pos", asc: true };
    dibujarMapa(filas);
    const { campo, asc } = orden;
    filas.sort((x, y) => {
      // Posición: de arquero a delantero (la que más jugó en la selección); en cada puesto, el que más jugó primero
      const a = campo === "pos" ? ordenPos(x) : x[campo] ?? -1, b = campo === "pos" ? ordenPos(y) : y[campo] ?? -1;
      return (asc ? a - b : b - a) || (y.pj - x.pj);
    });
    tbody.innerHTML = filas.map((f) => {
      const j = D.jugadores[f.id];
      return `<tr><th scope="row" class="eq"><a class="eqi" href="${j.pagina}">${avatar(j, 26)}<span>${esc(j.alias)}</span>${(posPrincipal(f) || j.pos) ? `<small class="pos">${esc(posPrincipal(f) || j.pos)}</small>` : ""}</a></th>
        <td>${f.pj}</td><td>${f.g || ""}</td><td>${f.a || ""}</td><td class="opc">${f.ga || ""}</td><td>${f.mvp || ""}</td><td>${f.vi || ""}</td><td class="opc">${f.ta || f.tr ? `${f.ta}/${f.tr}` : ""}</td><td>${n1(f.nota)}</td>${ea ? `<td class="col-ea">${f.tiros ?? ""}</td><td class="col-ea">${f.pp != null ? Math.round(f.pp) + "%" : ""}</td><td class="col-ea">${f.ent ?? ""}</td>` : ""}</tr>`;
    }).join("");
    vacio.hidden = filas.length > 0;
    ths.forEach((th) => (th.dataset.campo === campo ? th.setAttribute("aria-sort", asc ? "ascending" : "descending") : th.removeAttribute("aria-sort")));
  }

  botones.forEach((b) => b.addEventListener("click", () => {
    liga = b.dataset.liga;
    rearmarTemporadas();
    dibujar();
  }));
  selT.addEventListener("change", dibujar);
  ths.forEach((th) => th.querySelector("button").addEventListener("click", () => {
    orden = { campo: th.dataset.campo, asc: orden.campo === th.dataset.campo ? !orden.asc : th.dataset.campo === "pos" };
    dibujar();
  }));
  // Volver a la liga y temporada que el visitante eligió la última vez
  const previo = VS.recordar("plantel");
  if (previo && botones.some((b) => b.dataset.liga === previo.liga)) {
    liga = previo.liga;
    rearmarTemporadas();
    if ([...selT.options].some((o) => o.value === previo.temporada)) selT.value = previo.temporada;
  }
  dibujar();
});
