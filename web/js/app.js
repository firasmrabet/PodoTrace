/* ═══════════════════════════════════════════════════════════════════════
   app.js — coquille, routage, cycle de session
   ═══════════════════════════════════════════════════════════════════════ */
import { S, api, setToken, icon, h, toast, initials, el, els } from './core.js';

const views = {};
let shellMounted = false;
let activeViewKey = null;

/* ─────────────────── Chargement paresseux des vues ─────────────────── */
const loaders = {
  accueil: () => import('./views/home.js'),
  capture: () => import('./views/capture.js'),
  resultat: () => import('./views/result.js'),
  historique: () => import('./views/history.js'),
  assistant: () => import('./views/chat.js'),
  centres: () => import('./views/map.js'),
  patients: () => import('./views/patients.js'),
  reglages: () => import('./views/settings.js'),
};

/* ─────────────────── Navigation ─────────────────── */
function navItems() {
  const isPro = S.user?.role === 'practitioner';
  const items = [
    { id: 'accueil', label: 'Accueil', icon: 'home' },
    { id: 'historique', label: 'Trajectoire', icon: 'chart' },
    { id: 'assistant', label: 'Assistant', icon: 'chat' },
    { id: 'centres', label: 'Centres de soin', icon: 'map' },
  ];
  if (isPro) items.push({ id: 'patients', label: 'Mes patients', icon: 'users' });
  items.push({ id: 'reglages', label: 'Profil & données', icon: 'user' });
  return items;
}

export function go(id, params = {}) {
  const qs = new URLSearchParams(params).toString();
  location.hash = `#/${id}${qs ? '?' + qs : ''}`;
}

export function reauth() {
  disposeActiveView();
  shellMounted = false;
  document.getElementById('root').innerHTML = '';
  boot();
}

function disposeActiveView() {
  if (activeViewKey) views[activeViewKey]?.dispose?.();
  activeViewKey = null;
}

/* ─────────────────── Coquille applicative ─────────────────── */
function mountShell() {
  const items = navItems();
  document.getElementById('root').innerHTML = `
    <div class="app">
      <aside class="rail">
        <div class="brand">
          <div class="mark">${icon('foot', 21)}</div>
          <div>
            <div class="nm">PodoTrace</div>
            <div class="sb">Pied diabétique</div>
          </div>
        </div>
        <nav id="rail-nav" aria-label="Navigation principale"></nav>
        <div class="spacer"></div>
        <div class="foot">
          <button class="nav-item" id="go-settings" style="padding:8px 10px">
            <div class="avatar">${h(initials(S.user?.full_name))}</div>
            <div style="min-width:0">
              <div style="font-size:12px; font-weight:600; color:var(--ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis">
                ${h(S.user?.full_name || S.user?.email || 'Compte')}</div>
              <div class="tiny" style="margin-top:1px">${S.user?.role === 'practitioner' ? 'Praticien' : 'Patient'}</div>
            </div>
          </button>
          <div class="tiny" style="padding:10px 10px 0; line-height:1.5">
            Outil d'aide en phase de validation clinique.<br>Ne remplace pas un avis médical.
          </div>
        </div>
      </aside>
      <div class="main">
        <main id="view" tabindex="-1"></main>
      </div>
      <nav class="tabbar" id="tabbar" aria-label="Navigation mobile"></nav>
    </div>`;

  const railNav = el('#rail-nav');
  const tabbar = el('#tabbar');
  items.forEach((it) => {
    const b = document.createElement('button');
    b.className = 'nav-item';
    b.dataset.id = it.id;
    b.innerHTML = `${icon(it.icon, 17)}<span>${it.label}</span>`;
    b.addEventListener('click', () => go(it.id));
    railNav.appendChild(b);
  });
  items.slice(0, 5).forEach((it) => {
    const b = document.createElement('button');
    b.dataset.id = it.id;
    b.innerHTML = `${icon(it.icon, 19)}<span>${it.label.split(' ')[0]}</span>`;
    b.addEventListener('click', () => go(it.id));
    tabbar.appendChild(b);
  });
  el('#go-settings').addEventListener('click', () => go('reglages'));
  shellMounted = true;
}

function markActive(id) {
  els('#rail-nav .nav-item').forEach((b) => b.classList.toggle('on', b.dataset.id === id));
  els('#tabbar button').forEach((b) => b.classList.toggle('on', b.dataset.id === id));
}

/* ─────────────────── Routage ─────────────────── */
function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '') || 'accueil';
  const [path, qs] = raw.split('?');
  return { id: path || 'accueil', params: Object.fromEntries(new URLSearchParams(qs || '')) };
}

let rendering = false;
let routeStamp = 0;

async function renderRoute() {
  if (!S.user) return;
  const stamp = ++routeStamp;                 // navigation la plus récente
  const { id, params } = parseHash();
  const key = loaders[id] ? id : 'accueil';
  if (activeViewKey !== key) {
    disposeActiveView();
    activeViewKey = key;
  }
  if (!shellMounted) mountShell();
  markActive(key);

  const view = el('#view');
  if (!view) return;
  if (!rendering) view.innerHTML = `<div class="loading-page"><div class="spinner dark"></div><span class="small">Chargement…</span></div>`;
  rendering = true;
  try {
    if (!views[key]) views[key] = await loaders[key]();
    if (stamp !== routeStamp) return;         // une autre route a pris la main
    await views[key].default(view, params);
    if (stamp !== routeStamp) return;
    view.firstElementChild?.classList.add('view');
  } catch (err) {
    if (err?.name === 'AbortError') return;
    if (stamp !== routeStamp) return;
    console.error(err);
    view.innerHTML = `<div class="page"><div class="card" style="border-color:#EBD5D8; background:#FBF3F4">
      <h2 style="font-size:18px">Impossible d'afficher cette page</h2>
      <p class="lede" style="margin-top:8px">${h(err.message || 'Erreur inattendue')}</p>
      <button class="btn ghost mt" onclick="location.reload()">Recharger</button>
    </div></div>`;
  } finally {
    rendering = false;
    window.scrollTo({ top: 0, behavior: 'instant' });
  }
}

/* ─────────────────── Démarrage ─────────────────── */
async function boot() {
  if (S.token) {
    try {
      S.user = await api.get('/auth/me');
    } catch {
      setToken(null);
      S.user = null;
    }
  }
  if (!S.user) {
    disposeActiveView();
    const { renderAuth } = await import('./views/auth.js');
    shellMounted = false;
    renderAuth(document.getElementById('root'));
    return;
  }
  mountShell();
  if (!location.hash) location.hash = '#/accueil';
  await renderRoute();
}

window.addEventListener('hashchange', () => { if (S.user) renderRoute(); });
window.addEventListener('df:logout', async () => {
  disposeActiveView();
  S.user = null;
  shellMounted = false;
  const { renderAuth } = await import('./views/auth.js');
  renderAuth(document.getElementById('root'));
});
window.addEventListener('df:authenticated', async (e) => {
  disposeActiveView();
  S.user = e.detail.user;
  shellMounted = false;
  location.hash = '#/accueil';
  await boot();
});

/* utile pour le débogage en console */
window.DF = { S, go, api, reauth };

boot();
