/* ═══════════════════════════════════════════════════════════════════════
   home.js — tableau de bord patient
   ═══════════════════════════════════════════════════════════════════════ */
import {
  S, api, icon, h, num, pctRaw, dateFr, relFr, todayLong, initials,
  levelOf, pill, sparkline, toast, el, els, setWound,
} from '../core.js';
import { go } from '../app.js';

export default async function home(root) {
  const [dash, wounds, analyses, engine] = await Promise.all([
    api.get('/wounds/dashboard'),
    api.get('/wounds'),
    api.get('/analysis?limit=6'),
    api.get('/analysis/engine/status').catch(() => null),
  ]);
  S.wounds = wounds;
  S.dashboard = dash;
  S.engine = engine;

  const isPro = S.user?.role === 'practitioner';
  const first = (S.user?.full_name || '').split(' ')[0] || 'à vous';
  const banner = bannerOf(dash);
  const trendWound = wounds.find((w) => w.analysis_count > 1) || wounds[0] || null;

  root.innerHTML = `
  <div class="page">
    <div class="masthead">
      <div>
        <div class="date">${h(todayLong())}</div>
        <h1>${isPro ? 'Bonjour Docteur' : `Bonjour ${h(first)}`}</h1>
        <div class="sub">${dash.active_wounds
          ? `${dash.active_wounds} plaie${dash.active_wounds > 1 ? 's' : ''} suivie${dash.active_wounds > 1 ? 's' : ''} · ${dash.total_analyses} mesure${dash.total_analyses > 1 ? 's' : ''}`
          : 'Aucune plaie suivie pour le moment'}</div>
      </div>
      <div class="right">
        <button class="btn" id="new-analysis">${icon('camera', 16)} Nouvelle analyse</button>
      </div>
    </div>

    <div class="banner ${banner.cls}">
      <div class="ic">${icon(banner.icon, 17)}</div>
      <div>
        <div class="ti">${h(banner.title)}</div>
        <div class="msg">${h(dash.banner_message)}</div>
      </div>
    </div>

    <div class="grid g3 mt">
      <div class="tile">
        <div class="k">Dernière surface</div>
        <div class="v">${dash.last_area_cm2 != null ? num(dash.last_area_cm2, 2) : '—'}<small>cm²</small></div>
        <div class="f">${dash.total_analyses ? `sur ${dash.total_analyses} mesure${dash.total_analyses > 1 ? 's' : ''}` : 'aucune mesure'}</div>
      </div>
      <div class="tile accent">
        <div class="k">Évolution totale</div>
        <div class="v" style="color:${dash.trend_pct > 0 ? 'var(--sage-deep)' : dash.trend_pct < 0 ? 'var(--alert)' : 'var(--ink)'}">
          ${dash.trend_pct != null ? num(-dash.trend_pct, 1) : '—'}<small>%</small></div>
        <div class="f">${dash.trend_pct > 0 ? 'réduction de la surface' : dash.trend_pct < 0 ? 'augmentation de la surface' : 'depuis la première mesure'}</div>
      </div>
      <div class="tile">
        <div class="k">Points d'alerte</div>
        <div class="v" style="color:${dash.critical_wounds ? 'var(--alert)' : 'var(--ink)'}">${dash.critical_wounds}</div>
        <div class="f">${dash.next_follow_up_days != null ? `prochaine photo dans ${dash.next_follow_up_days} j` : 'aucune plaie critique'}</div>
      </div>
    </div>

    <div class="split mt">
      <div>
        <div class="card-h" style="margin-bottom:12px">
          <h2 style="font-size:18px">Plaies suivies</h2>
          <button class="btn quiet sm" id="add-wound">${icon('plus', 14)} Ajouter</button>
        </div>
        ${wounds.length ? `<div class="grid" style="gap:9px">${wounds.map(woundRow).join('')}</div>`
          : emptyWounds()}
      </div>

      <div class="grid" style="gap:14px">
        <div class="card">
          <div class="card-h"><div class="t">Trajectoire</div>
            ${trendWound ? `<button class="btn quiet sm" data-open="${trendWound.id}">Détail ${icon('arrow', 13)}</button>` : ''}</div>
          ${trendWound && trendWound.sparkline?.length > 1 ? `
            <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:10px">
              <div>
                <div class="num" style="font-size:28px; font-weight:600; line-height:1">${num(trendWound.latest_area_cm2, 2)}<span style="font-size:12px; font-family:var(--sans); color:var(--ink-3)"> cm²</span></div>
                <div class="tiny mt-sm">${h(trendWound.label)}</div>
              </div>
              ${sparkline(trendWound.sparkline, { w: 110, h: 42 })}
            </div>
            <div class="divider"></div>
            <div class="row between">
              <span class="small">Évolution</span>
              <span class="pill ${(trendWound.trend_pct ?? 0) > 0 ? 'calm' : 'watch'}">${trendWound.trend_pct != null ? num(-trendWound.trend_pct, 1) + ' %' : '—'}</span>
            </div>` : `<p class="small">Ajoutez deux mesures pour voir la courbe de cicatrisation.</p>`}
        </div>

        <div class="card">
          <div class="card-h"><div class="t">Dernières mesures</div>
            <button class="btn quiet sm" id="go-history">Tout voir ${icon('arrow', 13)}</button></div>
          ${analyses.length ? analyses.slice(0, 4).map((a) => `
            <div class="row between" style="padding:9px 0; border-bottom:1px solid var(--line-soft)">
              <div class="row" style="gap:10px">
                <span class="pill ${levelOf(a.risk_level).cls}" style="padding:3px 8px; font-size:10px">${levelOf(a.risk_level).label}</span>
                <div>
                  <div style="font-size:12.5px; font-weight:600">${num(a.area_cm2, 2)} cm²</div>
                  <div class="tiny">${h(relFr(a.captured_at))}</div>
                </div>
              </div>
              <button class="btn quiet sm" data-analysis="${a.id}" aria-label="Ouvrir le résultat">${icon('arrow', 14)}</button>
            </div>`).join('') : `<p class="small">Aucune analyse enregistrée.</p>`}
        </div>

        <div class="card sink flat">
          <div class="row" style="gap:11px; align-items:flex-start">
            <div style="color:var(--sage-deep); margin-top:2px">${icon('info', 16)}</div>
            <div>
              <div style="font-size:12.5px; font-weight:600">Comment photographier correctement</div>
              <p class="tiny" style="margin-top:5px; line-height:1.55">
                Lumière du jour, pied posé à plat, appareil à 90° au-dessus de la plaie et
                repère de calibration (2 cm) visible près de la lésion.
              </p>
              <button class="btn quiet sm" style="padding-left:0" id="go-capture">Ouvrir la caméra ${icon('arrow', 13)}</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <p class="tiny center mt-lg" style="line-height:1.6">
      PodoTrace est un outil d'aide à la télésurveillance en phase de validation clinique. Il ne pose pas de diagnostic
      et ne remplace pas une consultation. En cas de fièvre, douleur brutale ou rougeur qui s'étend :
      <b>15</b> (SAMU) ou <b>190</b>.
    </p>
  </div>`;

  el('#new-analysis', root).addEventListener('click', () => go('capture'));
  el('#go-capture', root).addEventListener('click', () => go('capture'));
  el('#go-history', root).addEventListener('click', () => go('historique'));
  el('#add-wound', root).addEventListener('click', () => newWoundDialog());
  el('#first-wound', root)?.addEventListener('click', () => newWoundDialog());
  els('[data-analysis]', root).forEach((b) =>
    b.addEventListener('click', () => go('resultat', { id: b.dataset.analysis })));
  els('[data-open]', root).forEach((b) =>
    b.addEventListener('click', () => { setWound(Number(b.dataset.open)); go('historique'); }));
}

function bannerOf(dash) {
  if (dash.global_status === 'alert') return { cls: 'alert', icon: 'alert', title: 'Avis médical recommandé' };
  if (dash.global_status === 'improving') return { cls: 'calm', icon: 'check', title: 'Cicatrisation en cours' };
  if (dash.global_status === 'stable') return { cls: 'calm', icon: 'info', title: 'Suivi stable' };
  return { cls: 'watch', icon: 'info', title: 'Première mesure à réaliser' };
}

function woundRow(w) {
  const lvl = levelOf(w.latest_risk_level);
  return `<div class="wound-row">
    <div class="badge">${icon('foot', 17)}</div>
    <div class="body">
      <div class="nm">${h(w.label)}</div>
      <div class="meta">${w.foot_side === 'left' ? 'Pied gauche' : 'Pied droit'} · ${h(w.anatomical_site)}
        ${w.wagner_grade != null ? `· Wagner ${w.wagner_grade}` : ''} · ${w.analysis_count} mesure${w.analysis_count > 1 ? 's' : ''}</div>
    </div>
    ${w.sparkline?.length > 1 ? sparkline(w.sparkline, { w: 54, h: 22 }) : ''}
    <div class="val">
      <div class="n">${w.latest_area_cm2 != null ? num(w.latest_area_cm2, 2) : '—'}<span style="font-size:10px; font-family:var(--sans); color:var(--ink-3)"> cm²</span></div>
    </div>
    ${w.latest_risk_level ? pill(w.latest_risk_level) : '<span class="pill">Pas de mesure</span>'}
    <button class="btn quiet sm" data-open="${w.id}" aria-label="Historique de la plaie">${icon('arrow', 14)}</button>
  </div>`;
}

function emptyWounds() {
  return `<div class="card center" style="padding:34px 22px">
    <div style="color:var(--sage); margin-bottom:10px">${icon('foot', 30)}</div>
    <h3>Commencez par déclarer une plaie</h3>
    <p class="small mt-sm" style="max-width:38ch; margin-inline:auto">
      Un nom, un pied, un grade : votre première analyse devient possible en une minute.
    </p>
    <button class="btn mt" id="first-wound">${icon('plus', 15)} Déclarer une plaie</button>
  </div>`;
}

/* ─────────────── Création de plaie ─────────────── */
export function newWoundDialog() {
  const root = document.getElementById('modal-root');
  root.innerHTML = `
    <div class="modal-bg">
      <div class="modal" role="dialog" aria-modal="true">
        <h2 style="font-size:20px">Nouvelle plaie</h2>
        <p class="small" style="margin-top:5px">Ces informations restent modifiables à tout moment.</p>
        <form id="wound-form" class="mt">
          <div class="field"><label>Libellé</label>
            <input class="input" name="label" placeholder="Ulcère plantaire — hallux droit" required maxlength="120" autofocus></div>
          <div class="grid g2 mt-sm" style="gap:10px">
            <div class="field"><label>Pied</label>
              <select class="input" name="foot_side"><option value="right">Droit</option><option value="left">Gauche</option></select></div>
            <div class="field"><label>Localisation</label>
              <select class="input" name="anatomical_site">
                <option value="hallux">Hallux (gros orteil)</option>
                <option value="metatarsal">Tête métatarsienne</option>
                <option value="heel">Talon</option>
                <option value="plantar">Plante</option>
                <option value="lateral">Bord latéral</option>
                <option value="medial">Bord médial</option>
                <option value="toe">Autre orteil</option>
                <option value="dorsal">Dos du pied</option>
              </select></div>
          </div>
          <div class="field mt-sm"><label>Grade de Wagner (facultatif)</label>
            <select class="input" name="wagner_grade">
              <option value="">Non renseigné</option>
              ${[0, 1, 2, 3, 4, 5].map((g) => `<option value="${g}">Grade ${g}</option>`).join('')}
            </select></div>
          <div class="row mt-lg" style="justify-content:flex-end; gap:9px">
            <button type="button" class="btn ghost" data-close>Annuler</button>
            <button type="submit" class="btn" id="wound-submit">Créer la plaie</button>
          </div>
        </form>
      </div>
    </div>`;

  const close = () => { root.innerHTML = ''; };
  el('.modal-bg', root)?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) close();
  });
  el('.modal', root)?.addEventListener('click', (e) => e.stopPropagation());
  els('[data-close]', root).forEach((b) => b.addEventListener('click', close));
  el('#wound-form', root).addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = el('#wound-submit', root);
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';
    const fd = new FormData(e.target);
    const payload = {
      label: fd.get('label'),
      foot_side: fd.get('foot_side'),
      anatomical_site: fd.get('anatomical_site'),
      wagner_grade: fd.get('wagner_grade') === '' ? null : Number(fd.get('wagner_grade')),
    };
    try {
      const w = await api.post('/wounds', payload);
      setWound(w.id);
      close();
      toast('Plaie créée. Vous pouvez réaliser la première photo.', 'ok');
      go('capture');
    } catch (err) {
      toast(err.message, 'err');
      btn.disabled = false;
      btn.textContent = 'Créer la plaie';
    }
  });
}
