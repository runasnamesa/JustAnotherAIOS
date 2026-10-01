// AIOS screen — só mostra. Todo dado vem de /api/snapshot (lido dos arquivos na hora).
// Modo estático (`python -m aios export`): window.AIOS_STATIC traz o snapshot e os arquivos
// embutidos; os botões só simulam a fila, nada é executado.
"use strict";

const STATIC = window.AIOS_STATIC || null;
const AREA_COLORS = ["#ff6a2b", "#4f9dff", "#2fbf7f", "#b07cf5", "#e0a526", "#f0527f", "#2fb8b8", "#8cc63f"];
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
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
  if (STATIC) {
    state.snap ||= structuredClone(STATIC.snapshot);
  } else {
    try {
      const r = await fetch("/api/snapshot", { cache: "no-store" });
      state.snap = await r.json();
    } catch (e) {
      $("updated").textContent = "sem conexão com o servidor";
      return;
    }
  }
  renderPanels();
  const g = state.snap.graph;
  const sig = g.generated_at + g.nodes.length;
  if (sig !== state.graphSig) { state.graphSig = sig; setupGraph(g); }
}

function renderPanels() {
  const s = state.snap;
  $("host").textContent = `host: ${s.host}`;
  const stamp = `${s.now.slice(8, 10)}/${s.now.slice(5, 7)} ${s.now.slice(11, 16)}`;
  if (STATIC) {
    $("updated").replaceChildren(`snapshot de ${stamp}`, el("span", { className: "demo-flag", textContent: STATIC.label || "estático" }));
  } else {
    $("updated").textContent = `lido dos arquivos às ${s.now.slice(11, 16)}`;
  }

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
  $("queue-info").textContent = state.notice || (s.queue.length
    ? `${s.queue.length} na fila: ${s.queue.map((q) => `${q.name} → ${q.host}`).join(", ")}`
    : "Fila vazia. O botão grava um pedido; o runner do host executa no próximo ciclo (até 5 min).");
}

function hostFor(kind, name) {
  const s = state.snap;
  if (kind === "routine") return (s.routines.find((r) => r.name === name) || {}).host || "?";
  return (s.graph.nodes.find((n) => n.id === `skill:${name}`) || {}).host || "mac";
}

// confirmação dentro da página (o visualizador de artefatos não mostra confirm/alert)
function enqueue(kind, name) {
  const box = $("confirm");
  const what = kind === "routine" ? "a rotina" : "a skill";
  const go = el("button", { className: "go", textContent: "Enfileirar" });
  const cancel = el("button", { textContent: "Cancelar" });
  box.replaceChildren(el("span", { textContent: `Enfileirar ${what} ${name} para rodar em ${hostFor(kind, name)}?` }), go, cancel);
  box.hidden = false;
  cancel.onclick = () => { box.hidden = true; };
  go.onclick = async () => {
    box.hidden = true;
    state.notice = await sendRun(kind, name);
    renderPanels();
    setTimeout(() => { state.notice = ""; renderPanels(); }, 6000);
  };
  go.focus();
}

async function sendRun(kind, name) {
  if (STATIC) {
    const host = hostFor(kind, name);
    state.snap.queue.push({ kind, name, host, source: "screen" });
    return `Simulado: ${name} entrou na fila de ${host}. Nesta versão estática nada é executado.`;
  }
  try {
    const r = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json", "X-AIOS": "1" },
      body: JSON.stringify({ kind, name }) });
    const j = await r.json();
    load();
    return r.ok ? `Na fila de ${j.host}: ${j.queued}` : `Não enfileirado: ${j.error}`;
  } catch (e) {
    return "Não enfileirado: o servidor do painel não respondeu.";
  }
}

async function openFile(path) {
  let text;
  if (STATIC) {
    text = STATIC.files[path] ?? "Este arquivo não foi incluído no snapshot.";
  } else {
    const r = await fetch(`/api/file?path=${encodeURIComponent(path)}`);
    const j = await r.json();
    text = r.ok ? j.text : j.error;
  }
  $("viewer-path").textContent = path;
  $("viewer-text").textContent = text;
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
  state.areaCount = {};
  g.nodes.forEach((n) => { if (n.kind === "note") state.areaCount[n.area] = (state.areaCount[n.area] || 0) + 1; });
  const runs = state.snap.runs_total ?? state.snap.recent_runs.length;
  $("stats").textContent = `${g.nodes.filter((n) => n.kind === "note" || n.kind === "router").length} arquivos · ${g.links.length} links · ${runs} execuções`;
  state.degree = {};
  state.links.forEach((l) => { state.degree[l.s.id] = (state.degree[l.s.id] || 0) + 1; state.degree[l.t.id] = (state.degree[l.t.id] || 0) + 1; });

  const all = el("button", { className: state.area ? "" : "on", textContent: "todas" });
  all.onclick = () => { state.area = null; setupChips(all); };
  $("areas").replaceChildren(all, ...areas.map((a) => {
    const b = el("button", {}, el("i", { style: `background:${state.areaColor[a]}` }), a, el("small", { textContent: ` ${state.areaCount[a] || 0}` }));
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
const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
state.motion = !REDUCED;
state.spin = 0;

// Anéis (de dentro para fora), como no vídeo: skills, memória (faixa de notas), rotinas, aplicações.
const RINGS = {
  hub: 0.2, skill: 0.31,
  memIn: 0.4, memOut: 0.74,
  routine: 0.85, app: 0.97,
};
const RING_LABELS = [
  ["SKILLS", RINGS.skill, "--ring-skill"], ["MEMÓRIA", RINGS.memOut, "--ring-memory"],
  ["ROTINAS", RINGS.routine, "--ring-routine"], ["APLICAÇÕES", RINGS.app, "--ring-app"],
];

function resize() {
  const r = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  W = r.width; H = r.height;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  layout();
}
window.addEventListener("resize", resize);

function areaSectors() {
  const areas = Object.keys(state.areaColor);
  const w = (2 * Math.PI) / Math.max(areas.length, 1);
  return Object.fromEntries(areas.map((a, i) => [a, { start: -Math.PI / 2 + i * w, width: w, mid: -Math.PI / 2 + (i + 0.5) * w }]));
}

// posição polar (raio relativo, ângulo) por tipo e setor de área; base de Anéis e Órbita 3D
function computePolar() {
  const sectors = areaSectors();
  const groups = {};
  state.nodes.forEach((n) => (groups[`${n.kind}|${n.area}`] ||= []).push(n));
  Object.entries(groups).forEach(([key, list]) => {
    const [kind, area] = key.split("|");
    const sec = sectors[area] || { start: -Math.PI / 2, width: 2 * Math.PI, mid: -Math.PI / 2 };
    const pad = sec.width * 0.06;
    list.sort((a, b) => a.id.localeCompare(b.id));
    if (kind === "root") { list.forEach((n) => { n.pr = 0; n.pa = 0; }); return; }
    if (kind === "router") { list.forEach((n) => { n.pr = RINGS.hub; n.pa = sec.mid; }); return; }
    if (kind === "note") {
      // várias fileiras dentro da faixa de memória, preenchendo o setor da área
      const rows = Math.max(1, Math.min(8, Math.ceil(Math.sqrt(list.length / 2))));
      const perRow = Math.ceil(list.length / rows);
      list.forEach((n, i) => {
        const row = i % rows, idx = Math.floor(i / rows);
        n.pr = RINGS.memIn + (RINGS.memOut - RINGS.memIn) * ((row + 0.5) / rows);
        n.pa = sec.start + pad + (sec.width - 2 * pad) * ((idx + 0.5 + (row % 2) * 0.5) / (perRow + 0.5));
      });
      return;
    }
    const ring = RINGS[kind] ?? RINGS.app;
    list.forEach((n, i) => { n.pr = ring; n.pa = sec.start + pad + (sec.width - 2 * pad) * ((i + 0.5) / list.length); });
  });
}

const geo = () => ({ cx: W / 2, cy: H / 2, R: Math.min(W, H) / 2 - 28 });

function layout() {
  if (!state.nodes.length || !W) return;
  computePolar();
  state.sim = null;
  state.nodes.forEach((n) => { n.off = false; n.z = 0; });
  ({ rings: place, orbit: placeOrbit, circle: layoutCircle, areas: layoutAreas,
     timeline: layoutTimeline, links: initForces })[state.view]();
}

function place() {
  const { cx, cy, R } = geo();
  state.nodes.forEach((n) => {
    const a = n.pa + (n.kind === "root" ? 0 : state.spin);
    n.x = cx + Math.cos(a) * R * n.pr; n.y = cy + Math.sin(a) * R * n.pr;
  });
}

// Órbita 3D: o mesmo disco dos anéis, inclinado e girando, com perspectiva
const TILT = 1.05;
function project(r, a, h) {
  const { cx, cy, R } = geo();
  const x = Math.cos(a) * r, z0 = Math.sin(a) * r;
  const y = h * Math.cos(TILT) - z0 * Math.sin(TILT), z = h * Math.sin(TILT) + z0 * Math.cos(TILT);
  const k = 2.4 / (2.4 - z);
  return { x: cx + x * R * 0.95 * k, y: cy + y * R * 0.95 * k, z, k };
}
function placeOrbit() {
  const lift = { root: 0, router: 0.05, note: 0, skill: 0.08, routine: 0.02, app: 0 };
  state.nodes.forEach((n, i) => {
    const h = (lift[n.kind] ?? 0) + (n.kind === "note" ? ((i * 37) % 11 - 5) * 0.012 : 0);
    const p = project(n.pr, n.pa + (n.kind === "root" ? 0 : state.spin), h);
    n.x = p.x; n.y = p.y; n.z = p.z; n.k = p.k;
  });
}

function layoutCircle() {
  const { cx, cy, R } = geo();
  const order = { router: 0, note: 1, skill: 2, routine: 3, app: 4 };
  const ring = state.nodes.filter((n) => n.kind !== "root")
    .sort((a, b) => a.area.localeCompare(b.area) || order[a.kind] - order[b.kind] || a.id.localeCompare(b.id));
  ring.forEach((n, i) => {
    const a = -Math.PI / 2 + (i / ring.length) * 2 * Math.PI;
    n.x = cx + Math.cos(a) * R * 0.9; n.y = cy + Math.sin(a) * R * 0.9; n.pa = a;
  });
  state.nodes.filter((n) => n.kind === "root").forEach((n) => { n.x = cx; n.y = cy; });
}

function layoutAreas() {
  const { cx, cy, R } = geo();
  const sectors = areaSectors();
  const byArea = {};
  state.nodes.forEach((n) => { if (n.kind !== "root") (byArea[n.area] ||= []).push(n); });
  const nAreas = Object.keys(sectors).length || 1;
  const step = Math.min(R * 0.95 * Math.sin(Math.PI / nAreas), R * 0.42);
  Object.entries(byArea).forEach(([area, list]) => {
    const sec = sectors[area] || { mid: 0 };
    const hx = cx + Math.cos(sec.mid) * R * 0.58, hy = cy + Math.sin(sec.mid) * R * 0.58;
    const rest = list.filter((n) => n.kind !== "router").sort((a, b) => a.kind.localeCompare(b.kind) || a.id.localeCompare(b.id));
    const c = Math.min(step * 0.85 / Math.sqrt(rest.length + 1), 11);
    list.filter((n) => n.kind === "router").forEach((n) => { n.x = hx; n.y = hy; });
    rest.forEach((n, i) => {  // espiral de girassol em volta da placa da área
      const r = c * Math.sqrt(i + 2.5), a = i * 2.39996;
      n.x = hx + Math.cos(a) * r; n.y = hy + Math.sin(a) * r;
    });
  });
  state.nodes.filter((n) => n.kind === "root").forEach((n) => { n.x = cx; n.y = cy; });
}

// Linha do tempo: 14 dias × áreas; cada nota no dia da última alteração, execuções numa faixa própria
function timelineFrame() {
  const end = new Date((state.snap?.now || new Date().toISOString()).slice(0, 10) + "T12:00:00");
  const days = [...Array(14)].map((_, i) => { const d = new Date(end); d.setDate(end.getDate() - 13 + i); return d.toISOString().slice(0, 10); });
  const rows = [...Object.keys(state.areaColor), "execuções"];
  const left = 92, right = 16, top = 34, bottom = 28;
  const colW = (W - left - right) / days.length, rowH = (H - top - bottom) / rows.length;
  return { days, rows, left, top, colW, rowH };
}
function layoutTimeline() {
  const f = timelineFrame();
  const stack = {};
  state.nodes.forEach((n) => {
    const di = f.days.indexOf(n.modified);
    const ri = f.rows.indexOf(n.area);
    if (n.kind !== "note" || di < 0 || ri < 0) { n.off = true; return; }
    const key = `${di}|${ri}`, k = (stack[key] = (stack[key] || 0) + 1) - 1;
    const perLine = Math.max(1, Math.floor((f.colW - 8) / 7));
    n.x = f.left + di * f.colW + 6 + (k % perLine) * 7;
    n.y = f.top + ri * f.rowH + 10 + Math.floor(k / perLine) * 7;
  });
}
function drawTimelineBackdrop() {
  const f = timelineFrame(), mono = css("--mono");
  ctx.font = `10px ${mono}`; ctx.textBaseline = "middle";
  f.rows.forEach((r, i) => {
    const y = f.top + i * f.rowH;
    ctx.fillStyle = r === "execuções" ? css("--ring-routine") : state.areaColor[r] || css("--muted");
    ctx.textAlign = "right"; ctx.fillText(r.toUpperCase(), f.left - 8, y + f.rowH / 2);
    ctx.strokeStyle = css("--graph-ring"); ctx.beginPath(); ctx.moveTo(f.left, y); ctx.lineTo(W - 16, y); ctx.stroke();
  });
  f.days.forEach((d, i) => {
    const x = f.left + i * f.colW;
    ctx.strokeStyle = css("--graph-ring"); ctx.setLineDash([1, 4]);
    ctx.beginPath(); ctx.moveTo(x, f.top); ctx.lineTo(x, H - 28); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = i === f.days.length - 1 ? css("--accent") : css("--muted"); ctx.textAlign = "left";
    ctx.fillText(`${d.slice(8)}/${d.slice(5, 7)}`, x + 4, f.top - 12);
  });
  // execuções: um traço por run, cor pelo status
  const ri = f.rows.length - 1, per = {};
  (state.snap?.run_history || []).forEach((r) => {
    const di = f.days.indexOf(r.at.slice(0, 10));
    if (di < 0) return;
    const k = (per[di] = (per[di] || 0) + 1) - 1;
    const perLine = Math.max(1, Math.floor((f.colW - 8) / 6));
    const x = f.left + di * f.colW + 6 + (k % perLine) * 6, y = f.top + ri * f.rowH + 8 + Math.floor(k / perLine) * 9;
    ctx.fillStyle = r.status === "ok" ? css("--ok") : css("--bad");
    ctx.fillRect(x, y, 3, 7);
  });
  ctx.textBaseline = "alphabetic";
}

function initForces() {
  const { cx, cy, R } = geo();
  state.nodes.forEach((n, i) => {
    const a = (i / state.nodes.length) * 2 * Math.PI;
    n.x = cx + Math.cos(a) * R * 0.6 + (Math.random() - 0.5) * 20;
    n.y = cy + Math.sin(a) * R * 0.6 + (Math.random() - 0.5) * 20;
    n.vx = n.vy = 0;
  });
  state.sim = { alpha: 1 };
}

function drawOrbitBackdrop() {
  ctx.lineWidth = 1;
  [[RINGS.memOut, "--graph-ring"], [RINGS.routine, "--graph-ring"], [RINGS.app, "--ring-app"]].forEach(([r, token]) => {
    ctx.strokeStyle = css(token); ctx.globalAlpha = token === "--ring-app" ? 0.5 : 1;
    ctx.beginPath();
    for (let i = 0; i <= 96; i++) { const p = project(r, (i / 96) * 2 * Math.PI, 0); ctx[i ? "lineTo" : "moveTo"](p.x, p.y); }
    ctx.stroke(); ctx.globalAlpha = 1;
  });
}

function drawAreasBackdrop() {
  const { cx, cy, R } = geo();
  Object.entries(areaSectors()).forEach(([area, sec]) => {
    const x = cx + Math.cos(sec.mid) * R * 0.58, y = cy + Math.sin(sec.mid) * R * 0.58;
    const g = ctx.createRadialGradient(x, y, 0, x, y, R * 0.36);
    g.addColorStop(0, state.areaColor[area] + "30"); g.addColorStop(1, state.areaColor[area] + "00");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, R * 0.36, 0, Math.PI * 2); ctx.fill();
  });
}

function stepForces() {
  const sim = state.sim;
  if (!sim || sim.alpha < 0.01) return;
  const N = state.nodes, cx = W / 2, cy = H / 2;
  for (let i = 0; i < N.length; i++) for (let j = i + 1; j < N.length; j++) {
    const a = N[i], b = N[j];
    let dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy || 1;
    const f = (500 / d2) * sim.alpha, d = Math.sqrt(d2);
    dx /= d; dy /= d;
    a.vx -= dx * f; a.vy -= dy * f; b.vx += dx * f; b.vy += dy * f;
  }
  state.links.forEach((l) => {
    const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.hypot(dx, dy) || 1;
    const f = ((d - 50) / d) * 0.04 * sim.alpha;
    l.s.vx += dx * f; l.s.vy += dy * f; l.t.vx -= dx * f; l.t.vy -= dy * f;
  });
  N.forEach((n) => {
    n.vx += (cx - n.x) * 0.006 * sim.alpha; n.vy += (cy - n.y) * 0.006 * sim.alpha;
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
  return !n.off && areaOk && qOk;
}

function color(n) { return n.kind === "root" ? css("--accent") : state.areaColor[n.area] || css("--muted"); }

function radius(n) {
  return { root: 13, router: 7, note: 2.4, skill: 4, routine: 4.2, app: 4.5 }[n.kind] ?? 3;
}

function shape(n, r) {
  ctx.beginPath();
  if (n.kind === "root") {
    for (let i = 0; i < 6; i++) { const a = Math.PI / 6 + (i * Math.PI) / 3; ctx[i ? "lineTo" : "moveTo"](n.x + Math.cos(a) * r, n.y + Math.sin(a) * r); }
    ctx.closePath();
  } else if (n.kind === "skill") {
    ctx.moveTo(n.x, n.y - r); ctx.lineTo(n.x + r, n.y); ctx.lineTo(n.x, n.y + r); ctx.lineTo(n.x - r, n.y); ctx.closePath();
  } else if (n.kind === "routine") {
    ctx.moveTo(n.x, n.y - r); ctx.lineTo(n.x + r, n.y + r * 0.8); ctx.lineTo(n.x - r, n.y + r * 0.8); ctx.closePath();
  } else if (n.kind === "app") {
    ctx.rect(n.x - r * 0.8, n.y - r * 0.8, r * 1.6, r * 1.6);
  } else {
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
  }
}

function pill(text, x, y, fg, font) {
  ctx.font = font;
  const w = ctx.measureText(text).width + 12;
  ctx.fillStyle = css("--panel");
  ctx.globalAlpha = 0.92;
  ctx.beginPath(); ctx.roundRect(x - w / 2, y - 9, w, 18, 4); ctx.fill();
  ctx.globalAlpha = 1;
  ctx.fillStyle = fg; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, x, y + 0.5);
  ctx.textBaseline = "alphabetic";
}

function drawRingsBackdrop(cx, cy, R, sectors) {
  // nuvens de cor por área, atrás da faixa de memória
  Object.entries(sectors).forEach(([area, sec]) => {
    const a = sec.mid + state.spin, rr = R * (RINGS.memIn + RINGS.memOut) / 2;
    const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr;
    const g = ctx.createRadialGradient(x, y, 0, x, y, R * 0.42);
    g.addColorStop(0, state.areaColor[area] + "2e"); g.addColorStop(1, state.areaColor[area] + "00");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, R * 0.42, 0, Math.PI * 2); ctx.fill();
  });
  // textura: fileiras pontilhadas na faixa de memória e no miolo
  ctx.fillStyle = css("--graph-ring");
  for (let k = 0.1; k <= RINGS.memOut + 0.001; k += 0.03) {
    const r = R * k, n = Math.floor((2 * Math.PI * r) / 7);
    for (let i = 0; i < n; i++) {
      const a = (i / n) * 2 * Math.PI + state.spin * (k > RINGS.memIn ? 1 : 0.5);
      ctx.fillRect(cx + Math.cos(a) * r, cy + Math.sin(a) * r, 1, 1);
    }
  }
  // anéis de rotinas e aplicações
  ctx.strokeStyle = css("--graph-ring"); ctx.lineWidth = 1;
  [RINGS.routine, RINGS.app].forEach((k) => { ctx.beginPath(); ctx.arc(cx, cy, R * k, 0, Math.PI * 2); ctx.stroke(); });
  // arcos de status das rotinas, como no vídeo (verde ok, vermelho falhou)
  const st = Object.fromEntries((state.snap?.routines || []).map((r) => [`routine:${r.name}`, r]));
  state.nodes.filter((n) => n.kind === "routine").forEach((n) => {
    const r = st[n.id];
    const c = !r || !r.status ? css("--muted") : r.status === "ok" ? css("--ok") : css("--bad");
    ctx.strokeStyle = c; ctx.lineWidth = 2; ctx.globalAlpha = 0.8;
    ctx.beginPath(); ctx.arc(cx, cy, R * RINGS.routine + 5, n.pa + state.spin - 0.09, n.pa + state.spin + 0.09); ctx.stroke();
    ctx.globalAlpha = 1;
  });
  RING_LABELS.forEach(([text, k, token]) => pill(text, cx, cy - R * k, css(token), `600 10px ${css("--mono")}`));
}

function draw() {
  const v = state.view;
  if ((v === "rings" || v === "orbit") && state.motion) state.spin += v === "orbit" ? 0.002 : 0.0006;
  if (v === "rings") place(); else if (v === "orbit") placeOrbit(); else if (v === "links") stepForces();
  ctx.clearRect(0, 0, W, H);
  const { cx, cy, R } = geo();
  const sectors = areaSectors();
  if (state.nodes.length) {
    if (v === "rings") drawRingsBackdrop(cx, cy, R, sectors);
    else if (v === "orbit") drawOrbitBackdrop();
    else if (v === "areas") drawAreasBackdrop();
    else if (v === "timeline") drawTimelineBackdrop();
    else if (v === "circle") { ctx.strokeStyle = css("--graph-ring"); ctx.beginPath(); ctx.arc(cx, cy, R * 0.9, 0, Math.PI * 2); ctx.stroke(); }
  }

  const sel = state.selected || state.hover;
  const accent = css("--accent"), linkC = css("--graph-link");
  const halo = css("--graph-halo"), labelC = css("--graph-label"), mono = css("--mono");
  const near = sel ? new Set(state.links.filter((l) => l.s === sel || l.t === sel).flatMap((l) => [l.s, l.t])) : null;

  // arestas: no Anéis só raiz→placas e as do ponto em foco; no Links, todas
  state.links.forEach((l) => {
    if (l.s.off || l.t.off) return;
    const focus = sel && (l.s === sel || l.t === sel);
    const spine = l.s.kind === "root" && l.t.kind === "router";
    const showAll = v === "links" || v === "circle";
    if (!showAll && !focus && !(spine && v !== "timeline")) return;
    if (!(visible(l.s) && visible(l.t)) && !focus) return;
    ctx.strokeStyle = focus ? accent : spine ? accent + "88" : linkC;
    ctx.lineWidth = focus ? 1.4 : 1;
    ctx.beginPath(); ctx.moveTo(l.s.x, l.s.y);
    if (v === "circle") ctx.quadraticCurveTo(cx, cy, l.t.x, l.t.y); else ctx.lineTo(l.t.x, l.t.y);
    ctx.stroke();
  });

  const order = { note: 0, skill: 1, routine: 1, app: 1, router: 2, root: 3 };
  const drawList = state.nodes.filter((n) => !n.off);
  if (v === "orbit") drawList.sort((a, b) => a.z - b.z); else drawList.sort((a, b) => order[a.kind] - order[b.kind]);
  drawList.forEach((n) => {
    const on = visible(n) && (!near || near.has(n) || n === sel);
    const depth = v === "orbit" ? Math.max(0.35, Math.min(1, 0.55 + n.z * 0.6)) : 1;
    ctx.globalAlpha = (on ? 1 : 0.14) * depth;
    const c = color(n), r = (radius(n) + (n === state.hover ? 1.5 : 0)) * (v === "orbit" ? n.k : 1);
    if (n.kind === "root") {
      ctx.shadowColor = accent; ctx.shadowBlur = 18;
      shape(n, r); ctx.fillStyle = css("--bg"); ctx.fill();
      ctx.lineWidth = 2.5; ctx.strokeStyle = accent; ctx.stroke(); ctx.shadowBlur = 0;
      pill("CLAUDE.md", n.x, n.y + r + 14, labelC, `600 10px ${mono}`);
    } else if (n.kind === "router") {
      ctx.shadowColor = c; ctx.shadowBlur = 14;
      ctx.beginPath(); ctx.arc(n.x, n.y, r + 3, 0, Math.PI * 2); ctx.lineWidth = 2; ctx.strokeStyle = c; ctx.stroke();
      ctx.beginPath(); ctx.arc(n.x, n.y, r - 2, 0, Math.PI * 2); ctx.fillStyle = c; ctx.fill(); ctx.shadowBlur = 0;
      const count = state.areaCount[n.area] || 0;
      const right = n.x >= cx - 4;
      ctx.textAlign = right ? "left" : "right";
      const tx = n.x + (right ? r + 8 : -(r + 8));
      ctx.fillStyle = labelC; ctx.font = `600 10px ${mono}`; ctx.fillText(n.area.toUpperCase(), tx, n.y - 1);
      ctx.fillStyle = c; ctx.font = `10px ${mono}`; ctx.fillText(String(count), tx, n.y + 11);
    } else {
      shape(n, r); ctx.fillStyle = c;
      if (n.kind === "note") { ctx.globalAlpha *= 0.9; ctx.fill(); }
      else { ctx.fill(); ctx.lineWidth = 1; ctx.strokeStyle = css("--bg"); ctx.stroke(); }
    }
    if (n === sel && n.kind !== "root") {
      ctx.globalAlpha = 1; ctx.beginPath(); ctx.arc(n.x, n.y, r + 4, 0, Math.PI * 2);
      ctx.strokeStyle = halo; ctx.lineWidth = 1.5; ctx.stroke();
    }
    if (on && n === state.hover && n.kind !== "root" && n.kind !== "router") {
      ctx.globalAlpha = 1; pill(n.title, n.x, n.y - r - 12, labelC, `10px ${mono}`);
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
    : node.id.startsWith("skill:") ? `.claude/commands/${node.id.slice(6)}.md`
    : node.id.startsWith("app:") ? node.path : node.id;
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
$("motion").classList.toggle("on", state.motion);
$("motion").addEventListener("click", () => { state.motion = !state.motion; $("motion").classList.toggle("on", state.motion); });

function tickClock() {
  const d = new Date();
  $("clock").textContent = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  $("date").textContent = d.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
}

tickClock(); setInterval(tickClock, 15000);
resize(); load(); if (!STATIC) setInterval(load, 30000);
requestAnimationFrame(draw);
