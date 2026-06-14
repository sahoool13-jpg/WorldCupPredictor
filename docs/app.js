// Live dashboard — presentation only. Reads the committed latest.json the scheduled run writes.
// The fetch keeps the cache-buster (?t=<now>) + cache:"no-store" to beat the Pages CDN.
// Optional fields (movers, recent_results, upcoming, bracket, why) all degrade gracefully if absent.
"use strict";

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
const MOVE = 0.005;
const pct = (x) => (x * 100).toFixed(1) + "%";
const pp = (d) => (d > 0 ? "+" : "") + (d * 100).toFixed(2);
// "2026-06-14" -> "Sun 14 Jun" (UTC); falls back to the raw string if unparseable.
const fmtDate = (iso) => {
  const d = new Date(iso + "T00:00:00Z");
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
};
const el = (tag, cls, txt) => { const n = document.createElement(tag);
  if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; };

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
  if (Math.abs(d) < 1e-9) return el("span", "chip flat", "–");
  const up = d > 0;
  const c = el("span", "chip " + (up ? "rise" : "fall"), (up ? "▲ " : "▼ ") + Math.abs(d * 100).toFixed(1));
  if (Math.abs(d) >= MOVE) c.classList.add("big");
  return c;
}

// survival curve, reusing the per-round reach probabilities already in the payload
const PATH_STEPS = [["Advance", "R32"], ["Round of 16", "R16"], ["Quarter-final", "QF"],
                    ["Semi-final", "SF"], ["Final", "F"]];
function pathPanel(r) {
  const box = el("div", "path");
  const steps = PATH_STEPS.map(([lab, k]) => [lab, r.reach[k]]).concat([["Champion", r.title]]);
  steps.forEach(([lab, v]) => {
    const row = el("div", "pstep");
    row.appendChild(el("span", "plab", lab));
    const track = el("div", "ptrack"); const fill = el("span", "pfill");
    fill.style.width = (v * 100).toFixed(1) + "%"; track.appendChild(fill);
    row.appendChild(track);
    row.appendChild(el("span", "pval", pct(v)));
    box.appendChild(row);
  });
  if (r.status === "eliminated") box.prepend(el("p", "pnote", "Eliminated — no path forward."));
  if (r.why) box.appendChild(whyBlock(r.why));
  return box;
}

// "Why this %?" — the rating + goal model behind the number (payload `why`; degrades if absent)
function whyBlock(w) {
  const box = el("div", "why");
  box.appendChild(el("h4", "whyh", "Why this %?"));
  const rt = w.rating, g = w.goals;
  const grid = el("div", "wgrid");
  const cell = (k, v) => { const c = el("div", "wcell");
    c.appendChild(el("b", null, v)); c.appendChild(el("span", null, k)); grid.appendChild(c); };
  cell("rating", rt.blended);
  cell("attack λ", g.attack_lambda);
  cell("defence λ", g.defence_lambda);
  cell("form", (rt.form_delta > 0 ? "+" : "") + rt.form_delta);
  box.appendChild(grid);
  const note = `prior ${rt.prior} · live Elo ${rt.elo_live} · ${rt.n_played} played ` +
    `(weight ${(rt.w_live * 100).toFixed(0)}% live)`;
  box.appendChild(el("p", "wnote", note));
  if (g.host_edge) box.appendChild(el("span", "whost", "★ host edge applied"));
  return box;
}

function renderOdds(rows) {
  const ol = document.getElementById("odds");
  ol.innerHTML = "";
  rows = Array.isArray(rows) ? rows : [];
  const max = rows.length ? rows[0].title : 1;
  rows.forEach((r, i) => {
    const li = el("li", "row" + (i === 0 && r.title > 0 ? " lead" : "") +
      (r.status === "eliminated" ? " eliminated" : ""));
    li.style.animationDelay = Math.min(i * 0.025, 0.8) + "s";

    const bar = el("div", "bar");
    bar.setAttribute("role", "button"); bar.tabIndex = 0;
    bar.setAttribute("aria-expanded", "false");
    bar.setAttribute("aria-label", `${r.team}, ${pct(r.title)} to win. Tap for path to the title.`);

    const fill = el("div", "fill");
    fill.style.setProperty("--w", (max > 0 ? (r.title / max) * 100 : 0).toFixed(1) + "%");
    bar.appendChild(fill);
    bar.appendChild(el("span", "rank", String(i + 1)));
    const fl = flag(r.team, "flag"); if (fl) bar.appendChild(fl);

    const name = el("span", "team");
    name.appendChild(document.createTextNode(r.team));
    if (r.group) name.appendChild(el("span", "grp", r.group));
    if (r.status === "through") name.appendChild(el("span", "badge through", "through"));
    else if (r.status === "eliminated") name.appendChild(el("span", "badge eliminated", "out"));
    bar.appendChild(name);

    const reach = el("div", "reach");
    [["Final", r.reach.F], ["SF", r.reach.SF], ["QF", r.reach.QF], ["R16", r.reach.R16], ["Adv", r.reach.R32]]
      .forEach(([lab, v]) => { const w = el("div"); w.appendChild(el("b", null, lab));
        w.appendChild(el("span", null, pct(v))); reach.appendChild(w); });
    bar.appendChild(reach);

    bar.appendChild(el("span", "pct", pct(r.title)));
    bar.appendChild(deltaChip(r.title_delta));
    bar.appendChild(el("span", "chev", "›"));

    const path = pathPanel(r);
    const toggle = () => { const open = li.classList.toggle("open");
      bar.setAttribute("aria-expanded", open ? "true" : "false"); };
    bar.addEventListener("click", toggle);
    bar.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });

    li.appendChild(bar); li.appendChild(path);
    ol.appendChild(li);
  });
  ol.setAttribute("aria-busy", "false");
}

function deriveMovers(odds) {
  const moved = odds.filter((r) => Math.abs(r.title_delta) >= 1e-9);
  const map = (rows) => rows.slice(0, 3).map((r) => ({ team: r.team, group: r.group, title_delta: r.title_delta }));
  return {
    risers: map(moved.filter((r) => r.title_delta > 0).sort((a, b) => b.title_delta - a.title_delta)),
    fallers: map(moved.filter((r) => r.title_delta < 0).sort((a, b) => a.title_delta - b.title_delta)),
  };
}

function moverList(items, kind) {
  const col = el("div", "mcol " + kind);
  col.appendChild(el("h3", "mhead", kind === "up" ? "▲ Rising" : "▼ Falling"));
  items.forEach((m) => {
    const row = el("div", "mrow");
    const fl = flag(m.team, "miniflag"); if (fl) row.appendChild(fl);
    const nm = el("span", "mteam"); nm.appendChild(document.createTextNode(m.team));
    if (m.group) nm.appendChild(el("span", "grp", m.group));
    row.appendChild(nm);
    row.appendChild(el("span", "mpp", pp(m.title_delta) + "pp"));
    col.appendChild(row);
  });
  return col;
}

function renderMovers(d) {
  const root = document.getElementById("movers");
  if (!root) return;
  const m = (d.movers && (d.movers.risers || d.movers.fallers)) ? d.movers : deriveMovers(d.title_odds);
  root.innerHTML = "";
  if (!m.risers.length && !m.fallers.length) {
    root.appendChild(el("div", "mempty",
      "No movement since the last update — odds are steady. The next refresh comes after the next completed match."));
    return;
  }
  if (m.risers.length) root.appendChild(moverList(m.risers, "up"));
  if (m.fallers.length) root.appendChild(moverList(m.fallers, "down"));
}

function renderResults(d) {
  const ul = document.getElementById("results");
  ul.innerHTML = "";
  let rr = Array.isArray(d.recent_results) ? d.recent_results
    : (d.meta.matches_reflected || []).slice(-5).reverse()
        .map((m) => ({ date: m.date, home: m.home, away: m.away, home_goals: m.hg, away_goals: m.ag }));
  if (!rr.length) { ul.appendChild(el("li", "empty", "No matches played yet — odds are pre-tournament.")); return; }
  rr.forEach((m) => {
    const li = el("li");
    const fh = flag(m.home, "miniflag"); if (fh) li.appendChild(fh);
    li.appendChild(el("span", "sc", `${m.home} ${m.home_goals}–${m.away_goals} ${m.away}`));
    const fa = flag(m.away, "miniflag"); if (fa) li.appendChild(fa);
    const dt = el("span", "g", fmtDate(m.date)); dt.title = m.date;
    li.appendChild(dt);
    ul.appendChild(li);
  });
}

function renderUpcoming(d) {
  const ul = document.getElementById("upcoming");
  if (!ul) return;
  ul.innerHTML = "";
  const ups = Array.isArray(d.upcoming) ? d.upcoming : [];
  if (!ups.length) {
    ul.appendChild(el("li", "empty", "No scheduled fixtures ahead — the bracket takes over next."));
    return;
  }
  ups.forEach((m) => {
    const li = el("li", "uprow");
    const teams = el("div", "uteams");
    const hw = el("span", "uteam");
    const fh = flag(m.home, "miniflag"); if (fh) hw.appendChild(fh);
    hw.appendChild(document.createTextNode(m.home));
    const aw = el("span", "uteam away");
    aw.appendChild(document.createTextNode(m.away));
    const fa = flag(m.away, "miniflag"); if (fa) aw.appendChild(fa);
    teams.appendChild(hw); teams.appendChild(el("span", "uvs", "v")); teams.appendChild(aw);
    li.appendChild(teams);

    const bar = el("div", "ubar");
    bar.title = `Win ${pct(m.p_home)} · Draw ${pct(m.p_draw)} · Win ${pct(m.p_away)}`;
    const seg = (v, cls) => { const s = el("span", "useg " + cls);
      s.style.width = (v * 100).toFixed(1) + "%"; return s; };
    bar.appendChild(seg(m.p_home, "uh"));
    bar.appendChild(seg(m.p_draw, "ud"));
    bar.appendChild(seg(m.p_away, "ua"));
    li.appendChild(bar);

    const meta = el("div", "umeta");
    meta.appendChild(el("span", "uprob", pct(m.p_home) + " / " + pct(m.p_draw) + " / " + pct(m.p_away)));
    const sc = m.scoreline;
    meta.appendChild(el("span", "uscore", `likeliest ${sc.home_goals}–${sc.away_goals}`));
    const dt = el("span", "g", (m.group ? "Grp " + m.group + " · " : "") + fmtDate(m.date));
    dt.title = m.date;
    meta.appendChild(dt);
    li.appendChild(meta);
    ul.appendChild(li);
  });
}

function renderGroups(groups) {
  const root = document.getElementById("groups");
  root.innerHTML = "";
  (Array.isArray(groups) ? groups : []).forEach((g) => {
    const box = el("div", "group");
    const h = el("h3"); h.appendChild(el("span", "lt", g.group));
    h.appendChild(document.createTextNode("Group " + g.group));
    box.appendChild(h);
    const t = el("table", "gt");
    t.innerHTML = "<thead><tr><th class='tl' scope='col'>Team</th><th scope='col'>P</th>" +
      "<th scope='col'>GD</th><th scope='col'>Pts</th></tr></thead>";
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
    renderMovers(d);
    renderUpcoming(d);
    renderGroups(d.groups);
    renderResults(d);
  } catch (e) {
    document.getElementById("status").classList.add("err");
    st.textContent = "Couldn't load the latest run (" + e.message + "). Try again shortly.";
  }
}
load();
