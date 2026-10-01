// AIOS screen — só mostra. Todo dado vem de /api/snapshot (lido dos arquivos na hora).
"use strict";

const AREA_COLORS = ["#ff6a2b", "#5aa9ff", "#3ecf8e", "#c084fc", "#f5b942", "#ff5a8a", "#4dd4d4", "#a3e635"];
const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...kids) => {
  const n = Object.assign(document.createElement(tag), props);
  kids.forEach((k) => n.append(k));
  return n;
};

const state = { snap: null, view: "rings", area: null, query: "", selected: null, hover: null,
  nodes: [], links: [], areaColor: {}, sim: null };

// ------------------------------------------------------------------ dados

async function load() {
  try {
    const r = await fetch("/api/snapshot", { cache: "no-store" });
    state.snap = await r.json();
  } catch (e) {
    $("updated").textContent = "sem conexão com o servidor";
    return;
  }
  renderPanels();
  const g = state.snap.graph;
  const sig = g.generated_at + g.nodes.length;
  if (sig !== state.graphSig) { state.graphSig = sig; setupGraph(g); }
}

function renderPanels() {
  const s = state.snap;
  $("host").textContent = `host: ${s.host}`;
  $("updated").textContent = `lido dos arquivos às ${s.now.slice(11, 16)}`;

  $("agenda").replaceChildren(...(s.agenda.length ? s.agenda.map((e) =>
    el("li", {}, el("span", { className: "when", textContent: `${e.date.slice(8)}/${e.date.slice(5, 7)} ${e.time}` }), e.text))
    : [el("li", { className: "muted", textContent: "nada nos próximos 14 dias" })]));

  $("brief").textContent = s.brief.replace(/^---[\s\S]*?---\n/, "").replace(/^# .*\n/, "").trim() || "—";

  $("needs-count").textContent = s.needs_you.length;
  $("needs").replaceChildren(...s.needs_you.map((n) =>
    el("li", {}, el("b", { textContent: n.title }), el("span", { textContent: n.detail }))));

  $("routines").replaceChildren(...s.routines.map((r) => {
    let cls = "muted", label = !r.enabled ? "desligada" : !r.due_today ? "—" : r.due_passed ? "sem registro" : "mais tarde";
    if (r.enabled && r.due_passed && !r.ran_today) cls = "warn";
    if (r.status && r.ran_today) { cls = r.status === "ok" ? "ok" : "bad"; label = r.status === "ok" ? "ok" : r.status; }
    else if (r.status && r.status !== "ok") { cls = "warn"; label = r.status; }
    const run = el("button", { textContent: "▶", title: `rodar agora em ${r.host}` });
    run.onclick = () => enqueue("routine", r.name);
    return el("tr", { title: r.purpose },
      el("td", { textContent: r.schedule.split(" ").slice(0, 2).reverse().map((x) => x.padStart(2, "0")).join(":") }),
      el("td", { textContent: r.name }),
      el("td", { className: "muted", textContent: r.host }),
      el("td", { className: `st ${cls}`, textContent: label }),
      el("td", {}, run));
  }));

  const skills = s.graph.nodes.filter((n) => n.kind === "skill");
  $("skills").replaceChildren(...skills.map((k) => {
    const b = el("button", { title: k.summary }, k.title, el("small", { textContent: `${k.host || "mac"} · ${k.model || "padrão"}` }));
    b.onclick = () => enqueue("skill", k.title.slice(1));
    return b;
  }));
  $("queue-info").textContent = s.queue.length
    ? `${s.queue.length} na fila: ${s.queue.map((q) => `${q.name}@${q.host}`).join(", ")}`
    : "fila vazia — o botão grava um pedido; o runner do host executa no próximo tick (≤5 min)";
}

async function enqueue(kind, name) {
  if (!confirm(`Enfileirar ${kind} "${name}"?`)) return;
  const r = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json", "X-AIOS": "1" },
    body: JSON.stringify({ kind, name }) });
  const j = await r.json();
  alert(r.ok ? `Na fila para ${j.host}: ${j.queued}` : `Erro: ${j.error}`);
  load();
}

async function openFile(path) {
  const r = await fetch(`/api/file?path=${encodeURIComponent(path)}`);
  const j = await r.json();
  $("viewer-path").textContent = path;
  $("viewer-text").textContent = r.ok ? j.text : j.error;
  $("viewer").showModal();
}
$("viewer-close").onclick = () => $("viewer").close();

// ------------------------------------------------------------------ grafo

function setupGraph(g) {
  const areas = [...new Set(g.nodes.map((n) => n.area).filter((a) => a !== "root"))].sort();
  state.areaColor = Object.fromEntries(areas.map((a, i) => [a, AREA_COLORS[i % AREA_COLORS.length]]));
  const byId = {};
  state.nodes = g.nodes.map((n) => (byId[n.id] = { ...n, x: 0, y: 0, vx: 0, vy: 0 }));
  state.links = g.links.filter((l) => byId[l.source] && byId[l.target])
    .map((l) => ({ ...l, s: byId[l.source], t: byId[l.target] }));
  state.degree = {};
  state.links.forEach((l) => { state.degree[l.s.id] = (state.degree[l.s.id] || 0) + 1; state.degree[l.t.id] = (state.degree[l.t.id] || 0) + 1; });

  const all = el("button", { className: state.area ? "" : "on", textContent: "todas" });
  all.onclick = () => { state.area = null; setupChips(all); };
  $("areas").replaceChildren(all, ...areas.map((a) => {
    const b = el("button", {}, el("i", { style: `background:${state.areaColor[a]}` }), a);
    b.onclick = () => { state.area = state.area === a ? null : a; setupChips(state.area ? b : all); };
    if (state.area === a) b.className = "on";
    return b;
  }));
  layout();
}

function setupChips(active) {
  [...$("areas").children].forEach((b) => b.classList.toggle("on", b === active));
}

const canvas = $("graph");
const ctx = canvas.getContext("2d");
let W = 0, H = 0;

function resize() {
  const r = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  W = r.width; H = r.height;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  layout();
}
window.addEventListener("resize", resize);

function layout() {
  if (!state.nodes.length || !W) return;
  const cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 24;
  if (state.view === "rings") {
    // anel por tipo; setor angular por área
    const ring = { root: 0, router: 0.32, note: 0.62, routine: 0.84, skill: 0.98 };
    const areas = Object.keys(state.areaColor);
    const groups = {};
    state.nodes.forEach((n) => (groups[`${n.kind}|${n.area}`] ||= []).push(n));
    Object.entries(groups).forEach(([key, list]) => {
      const [kind, area] = key.split("|");
      const ai = Math.max(0, areas.indexOf(area));
      const sector = (2 * Math.PI) / Math.max(areas.length, 1);
      list.forEach((n, i) => {
        if (kind === "root") { n.x = cx; n.y = cy; return; }
        const a = -Math.PI / 2 + ai * sector + sector * ((i + 1) / (list.length + 1));
        n.x = cx + Math.cos(a) * R * ring[kind]; n.y = cy + Math.sin(a) * R * ring[kind];
      });
    });
    state.sim = null;
  } else {
    state.nodes.forEach((n, i) => {
      const a = (i / state.nodes.length) * 2 * Math.PI;
      n.x = cx + Math.cos(a) * R * 0.6 + (Math.random() - 0.5) * 20;
      n.y = cy + Math.sin(a) * R * 0.6 + (Math.random() - 0.5) * 20;
      n.vx = n.vy = 0;
    });
    state.sim = { alpha: 1 };
  }
}

function stepForces() {
  const sim = state.sim;
  if (!sim || sim.alpha < 0.01) return;
  const N = state.nodes, cx = W / 2, cy = H / 2;
  for (let i = 0; i < N.length; i++) for (let j = i + 1; j < N.length; j++) {
    const a = N[i], b = N[j];
    let dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy || 1;
    const f = (900 / d2) * sim.alpha, d = Math.sqrt(d2);
    dx /= d; dy /= d;
    a.vx -= dx * f; a.vy -= dy * f; b.vx += dx * f; b.vy += dy * f;
  }
  state.links.forEach((l) => {
    const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.hypot(dx, dy) || 1;
    const f = ((d - 70) / d) * 0.04 * sim.alpha;
    l.s.vx += dx * f; l.s.vy += dy * f; l.t.vx -= dx * f; l.t.vy -= dy * f;
  });
  N.forEach((n) => {
    n.vx += (cx - n.x) * 0.004 * sim.alpha; n.vy += (cy - n.y) * 0.004 * sim.alpha;
    if (n.kind === "root") { n.x = cx; n.y = cy; n.vx = n.vy = 0; return; }
    n.vx *= 0.82; n.vy *= 0.82; n.x += n.vx; n.y += n.vy;
    n.x = Math.max(12, Math.min(W - 12, n.x)); n.y = Math.max(12, Math.min(H - 12, n.y));
  });
  sim.alpha *= 0.985;
}

function visible(n) {
  const q = state.query;
  const areaOk = !state.area || n.area === state.area || n.kind === "root";
  const qOk = !q || `${n.id} ${n.title} ${n.summary || ""}`.toLowerCase().includes(q);
  return areaOk && qOk;
}

function color(n) { return n.kind === "root" ? "#ffffff" : state.areaColor[n.area] || "#888"; }

function shape(n, r) {
  ctx.beginPath();
  if (n.kind === "root") {
    for (let i = 0; i < 6; i++) { const a = Math.PI / 6 + (i * Math.PI) / 3; ctx[i ? "lineTo" : "moveTo"](n.x + Math.cos(a) * r, n.y + Math.sin(a) * r); }
    ctx.closePath();
  } else if (n.kind === "router") {
    ctx.moveTo(n.x, n.y - r); ctx.lineTo(n.x + r, n.y); ctx.lineTo(n.x, n.y + r); ctx.lineTo(n.x - r, n.y); ctx.closePath();
  } else if (n.kind === "routine") {
    ctx.moveTo(n.x, n.y - r); ctx.lineTo(n.x + r, n.y + r * 0.8); ctx.lineTo(n.x - r, n.y + r * 0.8); ctx.closePath();
  } else if (n.kind === "skill") {
    ctx.rect(n.x - r * 0.8, n.y - r * 0.8, r * 1.6, r * 1.6);
  } else {
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
  }
}

function radius(n) {
  if (n.kind === "root") return 16;
  return (n.kind === "router" ? 7 : 4.5) + Math.min(4, (state.degree[n.id] || 0) * 0.5);
}

function draw() {
  stepForces();
  ctx.clearRect(0, 0, W, H);
  const cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 24;
  if (state.view === "rings") {
    ctx.strokeStyle = "#34343c"; ctx.setLineDash([2, 5]);
    [0.32, 0.62, 0.84, 0.98].forEach((k) => { ctx.beginPath(); ctx.arc(cx, cy, R * k, 0, Math.PI * 2); ctx.stroke(); });
    ctx.setLineDash([]);
  }
  const sel = state.selected;
  const near = sel ? new Set(state.links.filter((l) => l.s === sel || l.t === sel).flatMap((l) => [l.s, l.t])) : null;
  state.links.forEach((l) => {
    const on = visible(l.s) && visible(l.t);
    const hl = sel && (l.s === sel || l.t === sel);
    ctx.strokeStyle = hl ? "#ff6a2b" : on ? (l.kind === "link" ? "#ffffff22" : "#ff6a2b33") : "#ffffff08";
    ctx.lineWidth = hl ? 1.6 : 1;
    ctx.beginPath(); ctx.moveTo(l.s.x, l.s.y); ctx.lineTo(l.t.x, l.t.y); ctx.stroke();
  });
  state.nodes.forEach((n) => {
    const on = visible(n) && (!near || near.has(n) || n === sel);
    ctx.globalAlpha = on ? 1 : 0.12;
    shape(n, radius(n));
    ctx.fillStyle = n.kind === "root" ? "#ff6a2b" : color(n);
    ctx.fill();
    if (n === state.hover || n === sel) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke(); }
    if (on && (n.kind === "root" || n.kind === "router" || n === state.hover)) {
      ctx.fillStyle = "#e8e6e3"; ctx.font = "10px ui-monospace, Menlo, monospace"; ctx.textAlign = "center";
      const label = n.kind === "router" ? n.area.toUpperCase() : n.kind === "root" ? "CLAUDE.md" : n.title;
      ctx.fillText(label, n.x, n.y + radius(n) + 12);
    }
  });
  ctx.globalAlpha = 1;
  requestAnimationFrame(draw);
}

function pick(ev) {
  const r = canvas.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
  let best = null, bd = 14;
  state.nodes.forEach((n) => { const d = Math.hypot(n.x - x, n.y - y); if (d < bd && visible(n)) { bd = d; best = n; } });
  return { node: best, x, y };
}

canvas.addEventListener("mousemove", (ev) => {
  const { node, x, y } = pick(ev);
  state.hover = node;
  const tip = $("tip");
  tip.hidden = !node;
  if (node) { tip.textContent = `${node.title} — ${node.summary || node.id}`; tip.style.left = `${x + 12}px`; tip.style.top = `${y + 12}px`; }
  canvas.style.cursor = node ? "pointer" : "default";
});

canvas.addEventListener("click", (ev) => {
  const { node } = pick(ev);
  state.selected = node;
  const info = $("info");
  info.hidden = !node;
  if (!node) return;
  const path = node.id.startsWith("routine:") ? "pulse/routines.toml"
    : node.id.startsWith("skill:") ? `.claude/commands/${node.id.slice(6)}.md` : node.id;
  const extra = node.kind === "routine" ? `${node.host} · ${node.schedule}` : node.hops != null ? `${node.hops} salto(s) do CLAUDE.md` : "";
  const open = el("button", { textContent: "abrir" });
  open.onclick = () => openFile(path);
  info.replaceChildren(el("b", { textContent: node.title }), el("div", { className: "muted", textContent: node.summary || "" }),
    el("code", { textContent: `${path}${extra ? " · " + extra : ""}` }), el("div", {}, open));
});

$("views").addEventListener("click", (ev) => {
  const v = ev.target.dataset.view;
  if (!v) return;
  state.view = v;
  [...$("views").children].forEach((b) => b.classList.toggle("on", b.dataset.view === v));
  layout();
});
$("search").addEventListener("input", (ev) => { state.query = ev.target.value.trim().toLowerCase(); });

function tickClock() {
  const d = new Date();
  $("clock").textContent = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  $("date").textContent = d.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
}

tickClock(); setInterval(tickClock, 15000);
resize(); load(); setInterval(load, 30000);
requestAnimationFrame(draw);
