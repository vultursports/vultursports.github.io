// Plantel: estadísticas filtradas por liga y temporada, calculadas en el navegador.
(() => {
  const nodo = document.getElementById("datos-plantel");
  if (!nodo) return;
  const D = JSON.parse(nodo.textContent);
  const tbody = document.querySelector("#tabla-plantel tbody");
  const ths = [...document.querySelectorAll("#tabla-plantel thead th[data-campo]")];
  const selT = document.getElementById("temporada");
  const botones = [...document.querySelectorAll(".filtros-plantel [data-liga]")];
  const lideres = document.getElementById("lideres");
  const vacio = document.getElementById("plantel-vacio");
  let liga = "todas", orden = { campo: "nota", asc: false };
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

  function enAlcance(lg, temp) {
    const t = selT.value;
    if (liga !== "todas" && lg !== liga) return false;
    if (t === "actual" && !D.actuales.includes(temp)) return false;
    if (t.startsWith("t:") && temp !== t.slice(2)) return false;
    return true;
  }

  function calcular() {
    const filas = {};
    for (const [jid, lg, temp, ed, g, a, mvp, nota, pos] of D.ap) {
      if (!enAlcance(lg, temp)) continue;
      const f = (filas[jid] ||= { id: jid, pj: 0, g: 0, a: 0, mvp: 0, notas: [], pos: {} });
      f.pj++; f.g += g; f.a += a; f.mvp += mvp;
      if (nota != null) f.notas.push(nota);
      const p = normPos(pos);
      if (p) f.pos[p] = (f.pos[p] || 0) + 1;
    }
    return Object.values(filas).map((f) => ({
      ...f, ga: f.g + f.a,
      nota: f.notas.length ? f.notas.reduce((x, y) => x + y, 0) / f.notas.length : null,
      // Nota ajustada: suma partidos "neutros" para que no gane alguien con muy pocos partidos
      aj: f.notas.length ? (f.notas.reduce((x, y) => x + y, 0) + D.notaBase * D.pesoBase) / (f.notas.length + D.pesoBase) : null,
    }));
  }

  function lider(filas, campo, titulo, unidad) {
    let cand = filas.filter((f) => (campo === "nota" ? f.nota != null && f.pj >= D.minimoNota : f[campo] > 0));
    // Mejor nota: el promedio más alto con el mínimo de partidos; en empate, el que jugó más
    cand.sort((x, y) => campo === "nota" ? (y.nota - x.nota) || (y.pj - x.pj) : (y[campo] - x[campo]) || (x.pj - y.pj));
    const f = cand[0];
    if (!f) return `<article class="lider"><h2>${titulo}</h2><p class="vacio">Sin datos.</p></article>`;
    const j = D.jugadores[f.id];
    const valor = campo === "nota" ? n1(f.nota) : f[campo];
    return `<article class="lider"><h2>${titulo}</h2><a href="${j.pagina}">${avatar(j, 44)}<span class="lider-nombre">${esc(j.alias)}</span></a>
      <p class="lider-valor"><b>${valor}</b> ${unidad} en ${f.pj} PJ</p></article>`;
  }

  // El 11 más usado: formación más repetida y, para cada puesto, quien más veces lo ocupó
  function once(filas) {
    const porPartido = {};
    for (const [jid, lg, temp, , , , , , pos, pid] of D.ap) {
      if (!enAlcance(lg, temp) || !pos) continue;
      (porPartido[pid] ||= []).push(normPos(pos));
    }
    const conteo = {}, partidosDe = {};
    for (const [pid, ps] of Object.entries(porPartido)) {
      if (ps.length < 10) continue;  // partidos con datos incompletos no cuentan
      const k = ps.slice().sort().join(",");
      conteo[k] = (conteo[k] || 0) + 1;
      (partidosDe[k] ||= []).push(pid);
    }
    const top = Object.entries(conteo).sort((a, b) => b[1] - a[1])[0];
    if (!top) return null;
    const slots = top[0].split(",").map((p, i) => ({ i, pos: p }));
    const total = Object.values(conteo).reduce((a, b) => a + b, 0);
    // Asignación: primero los pares (jugador, puesto) con más partidos; cada jugador y puesto una sola vez
    const pares = [];
    for (const f of filas) for (const s of slots) if (f.pos[s.pos]) pares.push([f.pos[s.pos], f, s]);
    pares.sort((a, b) => b[0] - a[0] || b[1].pj - a[1].pj);
    const usado = new Set(), asignado = {};
    for (const [, f, s] of pares) {
      if (usado.has(f.id) || asignado[s.i]) continue;
      usado.add(f.id); asignado[s.i] = f;
    }
    // Puestos sin dueño: el jugador libre con más partidos
    for (const s of slots) {
      if (asignado[s.i]) continue;
      const libre = filas.filter((f) => !usado.has(f.id)).sort((a, b) => b.pj - a.pj)[0];
      if (libre) { usado.add(libre.id); asignado[s.i] = libre; }
    }
    // Nombre de la formación: el que publicó la liga en esos partidos (no se calcula). Si la liga no lo publica, no hay nombre.
    const nombres = {};
    for (const pid of partidosDe[top[0]] || []) if (D.form[pid]) nombres[D.form[pid]] = (nombres[D.form[pid]] || 0) + 1;
    const formacion = (Object.entries(nombres).sort((a, b) => b[1] - a[1])[0] || [""])[0];
    const banco = filas.filter((f) => !usado.has(f.id)).sort((a, b) => b.pj - a.pj).slice(0, 9);
    return { slots, asignado, formacion, veces: top[1], total, banco };
  }

  function dibujarOnce(filas) {
    const cancha = document.getElementById("cancha");
    const bancoEl = document.getElementById("banco");
    const etiqueta = document.getElementById("once-formacion");
    const o = once(filas);
    if (!o) { cancha.innerHTML = `<p class="vacio">Sin alineaciones para esta selección.</p>`; bancoEl.innerHTML = ""; etiqueta.textContent = ""; return; }
    etiqueta.textContent = (o.formacion ? `${o.formacion} · ` : "") + `usada en ${o.veces} de ${o.total} partidos`;
    // Repartir horizontalmente a los que comparten puesto (por ejemplo, dos DFC)
    const porPos = {};
    o.slots.forEach((s) => (porPos[s.pos] ||= []).push(s));
    const html = [];
    // MVP del 11: el de mejor nota (ajustada por partidos, con el mínimo de partidos de "Mejor nota")
    const candidatos = Object.values(o.asignado).filter((f) => f.nota != null && f.pj >= D.minimoNota);
    const mvp = candidatos.sort((a, b) => (b.nota - a.nota) || (b.pj - a.pj))[0];
    for (const [pos, lista] of Object.entries(porPos)) {
      const [bx, by] = LUGAR[pos] || [50, 50];
      const paso = lista.length === 2 ? 34 : 26;
      lista.forEach((s, k) => {
        const x = bx + (k - (lista.length - 1) / 2) * paso;
        const f = o.asignado[s.i];
        if (!f) return;
        const j = D.jugadores[f.id];
        const esMvp = mvp && f.id === mvp.id;
        html.push(`<a role="listitem" class="ficha-cancha${esMvp ? " es-mvp" : ""}" style="left:${x}%;top:${by}%" href="${j.pagina}"${esMvp ? ' title="Mejor nota del 11"' : ""}>
          ${avatar(j, 34)}${esMvp ? '<b class="fc-mvp">MVP</b>' : ""}<span class="fc-nombre">${esc(j.alias)}</span>
          <span class="fc-datos">${pos}${f.nota != null ? ` · <b>${n1(f.nota)}</b>` : ""}</span>
          <span class="fc-datos">${f.pj} PJ${f.g ? ` · ${f.g} G` : ""}${f.a ? ` · ${f.a} A` : ""}</span></a>`);
      });
    }
    cancha.innerHTML = `<div class="lineas" aria-hidden="true"><i class="medio"></i><i class="circulo"></i><i class="area arriba"></i><i class="area abajo"></i></div>` + html.join("");
    bancoEl.innerHTML = o.banco.map((f) => {
      const j = D.jugadores[f.id];
      const pos = Object.entries(f.pos).sort((a, b) => b[1] - a[1])[0];
      return `<li><a href="${j.pagina}">${avatar(j, 28)}<span class="bn-nombre">${esc(j.alias)}</span>
        <span class="bn-datos">${pos ? pos[0] + " · " : ""}${f.pj} PJ${f.nota != null ? ` · ${n1(f.nota)}` : ""}</span></a></li>`;
    }).join("") || `<li class="vacio">Sin suplentes con partidos.</li>`;
  }

  function dibujar() {
    // Si se eligió una temporada puntual, la liga queda fija en la de esa temporada
    const opt = selT.selectedOptions[0];
    if (opt && opt.dataset.liga) {
      liga = opt.dataset.liga;
    }
    botones.forEach((b) => b.setAttribute("aria-pressed", b.dataset.liga === liga));

    const filas = calcular();
    dibujarOnce(filas);
    lideres.innerHTML = [
      lider(filas, "g", "Goleador", "goles"), lider(filas, "a", "Asistidor", "asistencias"),
      lider(filas, "mvp", "Más veces MVP", "MVP"), lider(filas, "nota", "Mejor nota", "de promedio"),
    ].join("");
    const { campo, asc } = orden;
    filas.sort((x, y) => {
      const a = x[campo] ?? -1, b = y[campo] ?? -1;
      return (asc ? a - b : b - a) || (y.pj - x.pj);
    });
    tbody.innerHTML = filas.map((f) => {
      const j = D.jugadores[f.id];
      return `<tr><th scope="row" class="eq"><a class="eqi" href="${j.pagina}">${avatar(j, 26)}<span>${esc(j.alias)}</span>${j.pos ? `<small class="pos">${esc(j.pos)}</small>` : ""}</a></th>
        <td>${f.pj}</td><td>${f.g || ""}</td><td>${f.a || ""}</td><td class="opc">${f.ga || ""}</td><td>${f.mvp || ""}</td><td>${n1(f.nota)}</td></tr>`;
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
    orden = { campo: th.dataset.campo, asc: orden.campo === th.dataset.campo ? !orden.asc : false };
    dibujar();
  }));
  dibujar();
})();
