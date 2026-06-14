// Live dashboard (plan.md §20.3). Reads the committed latest.json the scheduled Action writes.
// CACHE-BUST: Pages sits behind a CDN, so we append ?t=<now> to defeat stale cached JSON.
const MOVE = 0.005; // 0.5pp highlight threshold (D5)
const pct = (x) => (x * 100).toFixed(1) + "%";

function deltaCell(d) {
  const td = document.createElement("td");
  td.className = "num";
  if (Math.abs(d) < 1e-9) { td.textContent = "—"; td.classList.add("flat"); return td; }
  const up = d > 0;
  td.textContent = (up ? "▲" : "▼") + " " + (Math.abs(d) * 100).toFixed(2);
  td.classList.add(up ? "up" : "down");
  if (Math.abs(d) >= MOVE) td.classList.add("big");
  return td;
}

function renderOdds(rows) {
  const tb = document.querySelector("#odds tbody");
  tb.innerHTML = "";
  rows.forEach((r, i) => {
    const tr = document.createElement("tr");
    tr.classList.add(r.status); // through | eliminated | alive
    const cells = [String(i + 1), r.team, r.group || "—"];
    cells.forEach((c, k) => {
      const td = document.createElement("td");
      td.textContent = c;
      if (k === 1) td.className = "team";
      tr.appendChild(td);
    });
    const tp = document.createElement("td"); tp.className = "num strong"; tp.textContent = pct(r.title);
    tr.appendChild(tp);
    tr.appendChild(deltaCell(r.title_delta));
    ["F", "SF", "QF", "R16", "R32"].forEach((k) => {
      const td = document.createElement("td"); td.className = "num dim"; td.textContent = pct(r.reach[k]);
      tr.appendChild(td);
    });
    tb.appendChild(tr);
  });
}

function renderGroups(groups) {
  const root = document.querySelector("#groups");
  root.innerHTML = "";
  groups.forEach((g) => {
    const box = document.createElement("div"); box.className = "group";
    box.innerHTML = `<h3>Group ${g.group}</h3>`;
    const t = document.createElement("table");
    t.innerHTML = "<thead><tr><th>Team</th><th class='num'>P</th><th class='num'>Pts</th>" +
                  "<th class='num'>GD</th><th class='num'>GF</th></tr></thead>";
    const tb = document.createElement("tbody");
    g.table.forEach((row) => {
      const tr = document.createElement("tr"); tr.classList.add(row.status);
      tr.innerHTML = `<td class='team'>${row.team}</td><td class='num'>${row.pld}</td>` +
        `<td class='num strong'>${row.pts}</td><td class='num'>${row.gd > 0 ? "+" : ""}${row.gd}</td>` +
        `<td class='num'>${row.gf}</td>`;
      tb.appendChild(tr);
    });
    t.appendChild(tb); box.appendChild(t); root.appendChild(box);
  });
}

function renderReflected(meta) {
  const ul = document.querySelector("#reflected");
  ul.innerHTML = "";
  (meta.matches_reflected || []).forEach((m) => {
    const li = document.createElement("li");
    li.textContent = `${m.date}  [${m.group}]  ${m.home} ${m.hg}–${m.ag} ${m.away}`;
    ul.appendChild(li);
  });
  if (!meta.matches_reflected || !meta.matches_reflected.length)
    ul.innerHTML = "<li>No matches played yet.</li>";
}

async function load() {
  try {
    const res = await fetch("data/latest.json?t=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const d = await res.json();
    const upd = new Date(d.meta.generated_at);
    document.querySelector("#updated").textContent =
      `Last updated ${upd.toUTCString()} · reflects ${d.meta.n_played} played match(es) ` +
      `· ${d.meta.n_sims.toLocaleString()} sims (seed ${d.meta.seed})`;
    document.querySelector("#prov").textContent =
      `Source: ${d.meta.source.structure} structure + ${d.meta.source.results} results.`;
    renderOdds(d.title_odds);
    renderGroups(d.groups);
    renderReflected(d.meta);
  } catch (e) {
    document.querySelector("#updated").textContent = "Could not load latest.json (" + e.message + ").";
  }
}
load();
