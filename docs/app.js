// Live dashboard — presentation only. Reads the committed latest.json the scheduled run writes.
// The fetch keeps the cache-buster (?t=<now>) + cache:"no-store" to beat the Pages CDN.
"use strict";

// team name -> ISO 3166 code for flagcdn.com (gb-eng / gb-sct are subdivision flags)
const FLAGS = {
  "Mexico":"mx","South Africa":"za","South Korea":"kr","Czech Republic":"cz",
  "Canada":"ca","Bosnia & Herzegovina":"ba","Qatar":"qa","Switzerland":"ch",
  "Brazil":"br","Morocco":"ma","Haiti":"ht","Scotland":"gb-sct",
  "USA":"us","Paraguay":"py","Australia":"au","Turkey":"tr",
  "Germany":"de","Curaçao":"cw","Ivory Coast":"ci","Ecuador":"ec",
  "Netherlands":"nl","Japan":"jp","Sweden":"se","Tunisia":"tn",
  "Belgium":"be","Egypt":"eg","Iran":"ir","New Zealand":"nz",
  "Spain":"es","Cape Verde":"cv","Saudi Arabia":"sa","Uruguay":"uy",
  "France":"fr","Senegal":"sn","Iraq":"iq","Norway":"no",
  "Argentina":"ar","Algeria":"dz","Austria":"at","Jordan":"jo",
  "Portugal":"pt","DR Congo":"cd","Uzbekistan":"uz","Colombia":"co",
  "England":"gb-eng","Croatia":"hr","Ghana":"gh","Panama":"pa"
};
const MOVE = 0.005;                       // 0.5pp highlight threshold
const pct = (x) => (x * 100).toFixed(1) + "%";
const el = (tag, cls, txt) => { const n = document.createElement(tag);
  if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; };

// flag <img> that vanishes cleanly if it fails to load (no broken-image icon)
function flag(team, cls) {
  const code = FLAGS[team];
  if (!code) return null;
  const img = el("img", cls);
  img.src = `https://flagcdn.com/w40/${code}.png`;
  img.alt = ""; img.loading = "lazy"; img.decoding = "async";
  img.onerror = () => img.remove();
  return img;
}

function deltaChip(d) {
  const pp = d * 100;
  if (Math.abs(d) < 1e-9) return el("span", "chip flat", "–");
  const up = d > 0;
  const c = el("span", "chip " + (up ? "rise" : "fall"), (up ? "▲ " : "▼ ") + Math.abs(pp).toFixed(1));
  if (Math.abs(d) >= MOVE) c.classList.add("big");
  return c;
}

function renderOdds(rows) {
  const ol = document.getElementById("odds");
  ol.innerHTML = "";
  const max = rows.length ? rows[0].title : 1;
  rows.forEach((r, i) => {
    const li = el("li", "row" + (i === 0 && r.title > 0 ? " lead" : "") +
      (r.status === "eliminated" ? " eliminated" : ""));
    li.style.animationDelay = Math.min(i * 0.028, 0.9) + "s";

    const fill = el("div", "fill");
    fill.style.setProperty("--w", (max > 0 ? (r.title / max) * 100 : 0).toFixed(1) + "%");
    li.appendChild(fill);

    li.appendChild(el("span", "rank", String(i + 1)));
    const fl = flag(r.team, "flag"); if (fl) li.appendChild(fl);

    const name = el("span", "team");
    name.appendChild(document.createTextNode(r.team));
    if (r.group) name.appendChild(el("span", "grp", r.group));
    if (r.status === "through") name.appendChild(el("span", "badge through", "through"));
    else if (r.status === "eliminated") name.appendChild(el("span", "badge eliminated", "out"));
    li.appendChild(name);

    const reach = el("div", "reach");
    [["Final", r.reach.F], ["SF", r.reach.SF], ["QF", r.reach.QF], ["R16", r.reach.R16], ["Adv", r.reach.R32]]
      .forEach(([lab, v]) => { const w = el("div"); w.appendChild(el("b", null, lab));
        w.appendChild(el("span", null, pct(v))); reach.appendChild(w); });
    li.appendChild(reach);

    li.appendChild(el("span", "pct", pct(r.title)));
    li.appendChild(deltaChip(r.title_delta));
    ol.appendChild(li);
  });
  ol.setAttribute("aria-busy", "false");
}

function renderGroups(groups) {
  const root = document.getElementById("groups");
  root.innerHTML = "";
  groups.forEach((g) => {
    const box = el("div", "group");
    const h = el("h3"); h.appendChild(el("span", "lt", g.group));
    h.appendChild(document.createTextNode("Group " + g.group));
    box.appendChild(h);

    const t = el("table", "gt");
    t.innerHTML = "<thead><tr><th class='tl'>Team</th><th>P</th><th>GD</th><th>Pts</th></tr></thead>";
    const tb = el("tbody");
    g.table.forEach((row, i) => {
      const zone = i < 2 ? "z-through" : i === 2 ? "z-third" : "z-out";
      const tr = el("tr", zone + (row.status === "eliminated" ? " elim" : ""));
      const tdName = el("td", "tl");
      const mf = flag(row.team, "miniflag"); if (mf) tdName.appendChild(mf);
      tdName.appendChild(document.createTextNode(row.team));
      if (row.status === "through") tdName.appendChild(el("span", "tick", "✓"));
      tr.appendChild(tdName);
      tr.appendChild(el("td", null, String(row.pld)));
      tr.appendChild(el("td", null, (row.gd > 0 ? "+" : "") + row.gd));
      tr.appendChild(el("td", "pts", String(row.pts)));
      tb.appendChild(tr);
    });
    t.appendChild(tb); box.appendChild(t); root.appendChild(box);
  });
}

function renderResults(meta) {
  const ul = document.getElementById("results");
  ul.innerHTML = "";
  const ms = meta.matches_reflected || [];
  if (!ms.length) { ul.appendChild(el("li", "empty", "No matches played yet — all odds are pre-tournament.")); return; }
  ms.forEach((m) => {
    const li = el("li");
    const fh = flag(m.home, "miniflag"); if (fh) li.appendChild(fh);
    li.appendChild(el("span", "sc", `${m.home} ${m.hg}–${m.ag} ${m.away}`));
    const fa = flag(m.away, "miniflag"); if (fa) li.appendChild(fa);
    li.appendChild(el("span", "g", m.date + " · " + m.group));
    ul.appendChild(li);
  });
}

async function load() {
  const st = document.getElementById("status-text");
  try {
    const res = await fetch("data/latest.json?t=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const d = await res.json();
    const upd = new Date(d.meta.generated_at);
    const ago = Math.max(0, Math.round((Date.now() - upd.getTime()) / 60000));
    st.textContent = `Updated ${upd.toUTCString().replace("GMT", "UTC")} · ${ago} min ago · ` +
      `${d.meta.n_played} played · ${d.meta.n_sims.toLocaleString()} sims`;
    document.getElementById("prov").textContent =
      `Source: ${d.meta.source.structure} structure + ${d.meta.source.results} results · seed ${d.meta.seed}.`;
    renderOdds(d.title_odds);
    renderGroups(d.groups);
    renderResults(d.meta);
  } catch (e) {
    document.getElementById("status").classList.add("err");
    st.textContent = "Couldn't load the latest run (" + e.message + "). Try again shortly.";
  }
}
load();
