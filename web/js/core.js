/* ═══════════════════════════════════════════════════════════════════════
   core.js — état, client API, utilitaires, primitives graphiques
   ═══════════════════════════════════════════════════════════════════════ */

export const API = '/api/v1';

/* Stockage résilient : localStorage peut être indisponible (iframe sandbox,
   navigation privée, quota plein). On retombe sur une mémoire de session pour
   que l'application reste utilisable dans tous les cas. */
const _mem = new Map();
export const store = {
  get(key, fallback = null) {
    try {
      const v = window.localStorage.getItem(key);
      return v === null || v === undefined ? fallback : v;
    } catch {
      return _mem.has(key) ? _mem.get(key) : fallback;
    }
  },
  set(key, value) {
    _mem.set(key, String(value));
    try { window.localStorage.setItem(key, String(value)); } catch { /* mémoire seule */ }
  },
  remove(key) {
    _mem.delete(key);
    try { window.localStorage.removeItem(key); } catch { /* mémoire seule */ }
  },
};

/* ─────────────────────────── État global ─────────────────────────── */
export const S = {
  token: store.get('df.token'),
  user: null,
  wounds: [],
  analyses: [],
  dashboard: null,
  currentAnalysis: null,
  currentWoundId: Number(store.get('df.wound', 0)) || null,
  locale: store.get('df.locale', 'fr'),
  engine: null,
};

export function setToken(t) {
  S.token = t;
  if (t) store.set('df.token', t);
  else store.remove('df.token');
}

export function setWound(id) {
  S.currentWoundId = id;
  if (id) store.set('df.wound', String(id));
}

/* ─────────────────────────── Client API ─────────────────────────── */
export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

async function request(path, { method = 'GET', body, form, raw = false, signal } = {}) {
  const headers = {};
  if (S.token) headers.Authorization = `Bearer ${S.token}`;
  let payload;
  if (form) {
    payload = form; // FormData : ne jamais fixer Content-Type
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(API + path, { method, headers, body: payload, signal });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError('Serveur injoignable. Vérifiez que le backend est démarré.', 0, null);
  }

  if (!res.ok) {
    let detail = `Erreur ${res.status}`;
    let payload = null;
    try {
      payload = await res.json();
      detail = payload.detail?.message || payload.detail || detail;
      if (Array.isArray(payload.detail)) {
        const parts = payload.detail.map((d) => String(d.msg || d).replace(/^Value error, /i, ''));
        detail = `Formulaire incomplet — ${parts.join(' · ')}`;
      }
    } catch { /* corps non JSON */ }
    if (res.status === 401 && S.token) {
      setToken(null);
      window.dispatchEvent(new CustomEvent('df:logout'));
    }
    throw new ApiError(typeof detail === 'string' ? detail : 'Requête refusée.', res.status, payload);
  }

  if (raw) return res;
  if (res.status === 204) return null;
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : res.text();
}

export const api = {
  get: (p, o) => request(p, o),
  post: (p, body, o) => request(p, { ...o, method: 'POST', body }),
  patch: (p, body, o) => request(p, { ...o, method: 'PATCH', body }),
  del: (p, o) => request(p, { ...o, method: 'DELETE' }),
  form: (p, form, o) => request(p, { ...o, method: 'POST', form }),
  raw: (p, o) => request(p, { ...o, raw: true }),
};

/* ─────────────────────────── Utilitaires ─────────────────────────── */
export const h = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const icon = (name, size = 18) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true"><use href="#i-${name}"/></svg>`;

export const el = (sel, root = document) => root.querySelector(sel);
export const els = (sel, root = document) => [...root.querySelectorAll(sel)];

export const num = (v, d = 1) =>
  v === null || v === undefined || Number.isNaN(Number(v))
    ? '—'
    : new Intl.NumberFormat('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d }).format(Number(v));

export const pct = (v, d = 0) => (v === null || v === undefined ? '—' : `${num(Number(v) * 100, d)} %`);
export const pctRaw = (v, d = 0) => (v === null || v === undefined ? '—' : `${num(v, d)} %`);

export function dateFr(iso, opts = { day: '2-digit', month: 'short', year: 'numeric' }) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('fr-FR', opts);
}
export function timeFr(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}
export function relFr(iso) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  const days = Math.floor(diff / 86400);
  if (days === 1) return 'hier';
  if (days < 30) return `il y a ${days} jours`;
  return dateFr(iso);
}
export const todayLong = () =>
  new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

export const initials = (name = '') =>
  name.trim().split(/\s+/).slice(0, 2).map((w) => w[0] || '').join('').toUpperCase() || 'DF';

/* ─────────────────────────── Niveaux cliniques ─────────────────────────── */
export const LEVELS = {
  low: { cls: 'calm', label: 'Faible', short: 'calme' },
  moderate: { cls: 'watch', label: 'Modéré', short: 'à surveiller' },
  high: { cls: 'alert', label: 'Élevé', short: 'alerte' },
};
export const levelOf = (l) => LEVELS[l] || LEVELS.low;
export const pill = (level, text) => {
  const l = levelOf(level);
  return `<span class="pill ${l.cls}"><i class="dot"></i>${h(text || l.label)}</span>`;
};

export const TISSUES = [
  { key: 'necrosis', label: 'Nécrose', color: 'var(--t-necrosis)' },
  { key: 'fibrin', label: 'Fibrine', color: 'var(--t-fibrin)' },
  { key: 'granulation', label: 'Granulation', color: 'var(--t-granulation)' },
  { key: 'epithelial', label: 'Épithélialisation', color: 'var(--t-epithelial)' },
];

/* Rendu markdown minimal et sûr : le texte est échappé AVANT toute mise en forme. */
export function md(text) {
  const safe = h(text);
  return safe
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/`([^`]+)`/g, '<code style="font-family:var(--mono);font-size:11.5px;background:var(--surface-sink);padding:1px 5px;border-radius:4px">$1</code>')
    .replace(/^\s*[-•]\s+/gm, '· ')
    .replace(/\n{2,}/g, '</p><p style="margin:8px 0 0">')
    .replace(/\n/g, '<br>');
}

/* ─────────────────────────── Toasts & modale ─────────────────────────── */
export function toast(msg, kind = '') {
  const host = document.getElementById('toasts');
  const node = document.createElement('div');
  node.className = `toast ${kind}`;
  node.textContent = msg;
  host.appendChild(node);
  setTimeout(() => {
    node.style.transition = 'opacity .25s, transform .25s';
    node.style.opacity = '0';
    node.style.transform = 'translateY(6px)';
    setTimeout(() => node.remove(), 260);
  }, 4200);
}

export function modal({ title, body, confirm = 'Confirmer', cancel = 'Annuler', danger = false, onConfirm }) {
  const root = document.getElementById('modal-root');
  root.innerHTML = `
    <div class="modal-bg">
      <div class="modal" role="dialog" aria-modal="true">
        <h2 style="font-size:20px">${h(title)}</h2>
        <div class="mt-sm lede" style="font-size:13px">${body}</div>
        <div class="row mt-lg" style="justify-content:flex-end; gap:9px">
          <button class="btn ghost" data-close>${h(cancel)}</button>
          <button class="btn ${danger ? 'danger' : ''}" data-ok>${h(confirm)}</button>
        </div>
      </div>
    </div>`;
  const close = () => { root.innerHTML = ''; };
  el('.modal-bg', root)?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) close();
  });
  el('.modal', root)?.addEventListener('click', (e) => e.stopPropagation());
  els('[data-close]', root).forEach((b) => b.addEventListener('click', close));
  el('[data-ok]', root).addEventListener('click', async () => {
    const btn = el('[data-ok]', root);
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';
    try { await onConfirm?.(); close(); } catch (e) { toast(e.message, 'err'); btn.disabled = false; btn.textContent = confirm; }
  });
  return { close };
}

/* ─────────────────────────── Primitives graphiques ─────────────────────────── */
export function sparkline(values, { w = 78, height: H = 26, color = 'var(--sage)' } = {}) {
  const vals = (values || []).filter((v) => typeof v === 'number');
  if (vals.length < 2) return `<svg width="${w}" height="${H}"></svg>`;
  const mn = Math.min(...vals), mx = Math.max(...vals), span = mx - mn || 1;
  const pts = vals.map((v, i) => [3 + ((w - 6) * i) / (vals.length - 1), H - 3 - ((H - 6) * (v - mn)) / span]);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  return `<svg width="${w}" height="${H}" viewBox="0 0 ${w} ${H}" aria-hidden="true">
    <path d="${d}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${pts.at(-1)[0].toFixed(1)}" cy="${pts.at(-1)[1].toFixed(1)}" r="2.3" fill="${color}"/>
  </svg>`;
}

export function gauge(value, level = 'low', label = 'Risque') {
  const l = levelOf(level);
  const color = l.cls === 'alert' ? 'var(--alert)' : l.cls === 'watch' ? 'var(--watch)' : 'var(--calm)';
  const R = 54, C = 2 * Math.PI * R, arc = C * 0.75, on = arc * Math.max(0.015, Math.min(1, value));
  return `<div class="gauge">
    <svg width="132" height="132" viewBox="0 0 132 132">
      <g transform="rotate(135 66 66)">
        <circle cx="66" cy="66" r="${R}" fill="none" stroke="#ECE8DE" stroke-width="8"
          stroke-linecap="round" stroke-dasharray="${arc} 999"/>
        <circle cx="66" cy="66" r="${R}" fill="none" stroke="${color}" stroke-width="8"
          stroke-linecap="round" stroke-dasharray="${on} 999">
          <animate attributeName="stroke-dasharray" from="0 999" to="${on} 999"
            dur="900ms" fill="freeze" calcMode="spline" keySplines="0.22 0.61 0.36 1"/>
        </circle>
      </g>
    </svg>
    <div class="c"><div><div class="n" style="color:${color}">${Math.round(value * 100)}<span style="font-size:14px">%</span></div>
      <div class="l">${h(label)}</div></div></div>
  </div>`;
}

export function donut(parts, size = 126) {
  const total = parts.reduce((a, p) => a + p.v, 0) || 1;
  const R = 46, C = 2 * Math.PI * R;
  let off = 0;
  const segs = parts.map((p) => {
    const len = (C * p.v) / total;
    const s = `<circle cx="${size / 2}" cy="${size / 2}" r="${R}" fill="none" stroke="${p.color}"
      stroke-width="13" stroke-linecap="butt"
      stroke-dasharray="${Math.max(0, len - 2)} ${C - len + 2}" stroke-dashoffset="${-off}"/>`;
    off += len;
    return s;
  }).join('');
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true">
    <circle cx="${size / 2}" cy="${size / 2}" r="${R}" fill="none" stroke="#F1EEE5" stroke-width="13"/>
    <g transform="rotate(-90 ${size / 2} ${size / 2})">${segs}</g>
  </svg>`;
}

export function areaChart(points, { w = 640, height: H = 190, color = 'var(--sage)', risk = null } = {}) {
  if (!points || points.length < 2) {
    return `<div class="center tiny" style="padding:34px 0">Pas encore assez de mesures pour tracer une courbe.</div>`;
  }
  const pad = { t: 14, r: 12, b: 24, l: 34 };
  const vals = points.map((p) => p.v);
  const max = Math.max(...vals) * 1.12 || 1, min = 0;
  const iw = w - pad.l - pad.r, ih = H - pad.t - pad.b;
  const X = (i) => pad.l + (iw * i) / (points.length - 1);
  const Y = (v) => pad.t + ih - (ih * (v - min)) / (max - min);

  // courbe lissée (Catmull-Rom → Bézier)
  const pts = points.map((p, i) => [X(i), Y(p.v)]);
  let d = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  const areaD = `${d} L${pts.at(-1)[0]} ${pad.t + ih} L${pts[0][0]} ${pad.t + ih} Z`;

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const y = pad.t + ih - ih * f;
    const val = min + (max - min) * f;
    return `<line x1="${pad.l}" y1="${y}" x2="${w - pad.r}" y2="${y}" stroke="#EDE9E0" stroke-width="1"/>
      <text x="${pad.l - 7}" y="${y + 3.5}" text-anchor="end" font-size="9" fill="#98A5A0"
        font-family="Inter,system-ui">${num(val, 0)}</text>`;
  }).join('');

  const riskLine = risk && risk.length > 1
    ? `<path d="M${risk.map((r, i) => `${X(i)} ${Y(r * max)}`).join(' L')}"
        fill="none" stroke="var(--alert)" stroke-width="1.2" stroke-dasharray="3 3" opacity=".55"/>`
    : '';

  const dots = pts.map((p, i) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.1"
      fill="#fff" stroke="${color}" stroke-width="1.9"><title>${h(points[i].label || '')} :
      ${num(points[i].v, 2)} cm²</title></circle>`).join('');

  const labels = points.map((p, i) => `<text x="${X(i)}" y="${H - 7}" text-anchor="middle" font-size="8.5"
      fill="#98A5A0" font-family="Inter,system-ui">${h(p.label || '')}</text>`).join('');

  return `<svg viewBox="0 0 ${w} ${H}" width="100%" style="display:block" role="img" aria-label="Évolution de la surface">
    ${gridLines}${riskLine}
    <path d="${areaD}" fill="url(#gradArea)"/>
    <path d="${d}" fill="none" stroke="${color}" stroke-width="2.1" stroke-linecap="round"/>
    ${dots}${labels}
    <defs><linearGradient id="gradArea" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${color}" stop-opacity=".16"/>
      <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs>
  </svg>`;
}

/* ─────────────────────────── Divers ─────────────────────────── */
export async function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result);
    fr.onerror = reject;
    fr.readAsDataURL(file);
  });
}

export function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export const wait = (ms) => new Promise((r) => setTimeout(r, ms));
