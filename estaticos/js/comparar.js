// Comparar jugadores: dos jugadores lado a lado, con barras enfrentadas por cada número.
VS.alCargar(() => {
  const nodo = document.getElementById("datos-comparar");
  if (!nodo) return;
  const D = JSON.parse(nodo.textContent);
  const porId = Object.fromEntries(D.map((j) => [j.id, j]));
  const selA = document.getElementById("cmp-a"), selB = document.getElementById("cmp-b");
  const botones = [...document.querySelectorAll(".cmp-ligas [data-liga]")];
  const cont = document.getElementById("comparacion");
  const esc = VS.esc;
  let liga = "todas";

  const q = new URLSearchParams(location.search);
  const previo = VS.recordar("comparar") || {};
  const valido = (id) => id && porId[id];
  const masPJ = [...D].sort((a, b) => b.ligas.todas.pj - a.ligas.todas.pj).map((j) => j.id);
  selA.value = [q.get("a"), previo.a, masPJ[0]].find(valido);
  selB.value = [q.get("b"), previo.b, masPJ.find((id) => id !== selA.value)].find((id) => valido(id) && id !== selA.value) || masPJ[1];

  const FILAS = [
    ["Partidos", (s) => s.pj],
    ["Goles", (s) => s.goles],
    ["Asistencias", (s) => s.asistencias],
    ["Goles + asistencias", (s) => s.ga],
    ["Goles por partido", (s) => (s.pj ? s.goles / s.pj : null), 2],
    ["Asistencias por partido", (s) => (s.pj ? s.asistencias / s.pj : null), 2],
    ["MVP", (s) => s.mvp],
    ["Vallas invictas", (s) => s.vallas],
    ["Nota promedio", (s) => s.nota, 2],
  ];
  const fmt = (v, dec) => (v == null ? "–" : dec ? v.toFixed(dec) : String(v));

  function dibujar() {
    const a = porId[selA.value], b = porId[selB.value];
    botones.forEach((x) => x.setAttribute("aria-pressed", x.dataset.liga === liga));
    VS.guardar("comparar", { a: a.id, b: b.id });
    const u = new URL(location.href);
    u.searchParams.set("a", a.id); u.searchParams.set("b", b.id);
    history.replaceState(null, "", u);
    const sa = a.ligas[liga], sb = b.ligas[liga];
    const cab = (j, lado) => `<a class="cmp-jug cmp-${lado}" href="${j.pagina}"><span class="avatar${j.dorsal ? "" : " sin-dorsal"}" style="--t: 44px" aria-hidden="true">${esc(j.dorsal || (j.alias || "?")[0].toUpperCase())}</span><b>${esc(j.alias)}</b>${j.pos ? `<small>${esc(j.pos)}</small>` : ""}</a>`;
    let html = `<div class="cmp-cab">${cab(a, "a")}${cab(b, "b")}</div>`;
    if (!sa && !sb) {
      cont.innerHTML = html + `<p class="vacio">Ninguno de los dos jugó en esta liga.</p>`;
      return;
    }
    html += `<table class="tabla cmp-tabla"><caption class="sr">${esc(a.alias)} contra ${esc(b.alias)}</caption><thead><tr><th scope="col">${esc(a.alias)}</th><th scope="col">Dato</th><th scope="col">${esc(b.alias)}</th></tr></thead><tbody>`;
    for (const [nombre, f, dec] of FILAS) {
      const va = sa ? f(sa) : null, vb = sb ? f(sb) : null;
      const max = Math.max(va || 0, vb || 0);
      const pa = max ? (100 * (va || 0)) / max : 0, pb = max ? (100 * (vb || 0)) / max : 0;
      const gana = va != null && vb != null && va !== vb ? (va > vb ? "a" : "b") : "";
      html += `<tr><td class="cmp-v${gana === "a" ? " gana" : ""}">${fmt(va, dec)}<span class="cmp-barra a" style="--p:${pa}%"></span></td>` +
        `<th scope="row">${nombre}</th>` +
        `<td class="cmp-v${gana === "b" ? " gana" : ""}">${fmt(vb, dec)}<span class="cmp-barra b" style="--p:${pb}%"></span></td></tr>`;
    }
    html += `</tbody></table>`;
    if (liga !== "todas" && (!sa || !sb)) html += `<p class="nota-cmp">${esc((!sa ? a : b).alias)} no jugó en esta liga.</p>`;
    cont.innerHTML = html;
  }

  [selA, selB].forEach((s) => s.addEventListener("change", dibujar));
  botones.forEach((x) => x.addEventListener("click", () => { liga = x.dataset.liga; dibujar(); }));
  dibujar();
});
