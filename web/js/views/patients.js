/* ═══════════════════════════════════════════════════════════════════════
   patients.js — espace praticien : file de télésurveillance triée par criticité
   ═══════════════════════════════════════════════════════════════════════ */
import { S, api, icon, h, num, pct, dateFr, relFr, levelOf, pill, initials, sparkline, el, els } from '../core.js';
import { go } from '../app.js';

export default async function patients(root) {
  if (S.user?.role !== 'practitioner') {
    root.innerHTML = `<div class="page narrow">
      <div class="masthead"><div><h1>Espace réservé aux professionnels</h1></div></div>
      <div class="card"><p class="small">Cet espace est accessible avec un compte praticien.</p>
        <button class="btn mt" id="home">Retour à l'accueil</button></div></div>`;
    el('#home', root).addEventListener('click', () => go('accueil'));
    return;
  }

  const [data, pending] = await Promise.all([
    api.get('/practitioner/patients'),
    api.get('/practitioner/pending').catch(() => ({ count: 0, items: [] })),
  ]);
  const list = data.patients || [];
  const high = list.filter((p) => p.risk_level === 'high').length;
  const pendingItems = pending.items || [];

  root.innerHTML = `
  <div class="page">
    <div class="masthead">
      <div>
        <div class="date">Télésurveillance</div>
        <h1>Mes patients</h1>
        <div class="sub">${list.length} patient${list.length > 1 ? 's' : ''} suivi${list.length > 1 ? 's' : ''} · tri par criticité</div>
      </div>
      <div class="right">
        <span class="pill ${high ? 'alert' : 'calm'}"><i class="dot"></i>${high} critique${high > 1 ? 's' : ''}</span>
        <span class="pill watch"><i class="dot"></i>${pendingItems.length} à valider</span>
      </div>
    </div>

    <div class="grid g3" style="margin-bottom:16px">
      <div class="tile"><div class="k">Patients</div><div class="v">${list.length}</div>
        <div class="f">suivis actifs</div></div>
      <div class="tile accent"><div class="k">Analyses reçues</div>
        <div class="v">${list.reduce((a, p) => a + p.analyses_count, 0)}</div>
        <div class="f">toutes plaies confondues</div></div>
      <div class="tile"><div class="k">En attente de validation</div>
        <div class="v" style="color:${pendingItems.length ? 'var(--watch)' : 'var(--ink)'}">${pendingItems.length}</div>
        <div class="f">human-in-the-loop</div></div>
    </div>

    <div class="split">
      <div class="card" style="padding:0; overflow:hidden">
        <div class="card-h" style="padding:18px 18px 0; margin-bottom:10px"><div class="t">File de suivi</div></div>
        ${list.length ? list.map(patientRow).join('') : `<p class="small" style="padding:18px">Aucun patient rattaché.</p>`}
      </div>

      <div class="grid" style="gap:14px">
        <div class="card">
          <div class="card-h"><div class="t">À valider</div>
            <span class="tiny">par risque infectieux</span></div>
          ${pendingItems.length ? pendingItems.slice(0, 6).map((it) => `
            <div class="row between" style="padding:10px 0; border-bottom:1px solid var(--line-soft)">
              <div>
                <div style="font-size:12.5px; font-weight:600">${num(it.area_cm2, 2)} cm²</div>
                <div class="tiny">${h(relFr(it.captured_at))} · risque ${pct(it.infection_risk)}</div>
              </div>
              <div class="row" style="gap:7px">
                ${pill(it.risk_level)}
                <button class="btn quiet sm" data-review="${it.analysis_id}">${icon('arrow', 14)}</button>
              </div>
            </div>`).join('')
            : `<p class="small">Toutes les analyses ont été validées.</p>`}
        </div>

        <div class="card sink flat">
          <div class="eyebrow" style="font-size:9px">Human-in-the-loop</div>
          <p class="tiny mt-sm" style="line-height:1.6">
            Le praticien peut corriger le niveau de risque, ajouter une note clinique horodatée
            et une prescription de pansement. La décision finale reste médicale — la trace est
            conservée dans le dossier et reprise dans le rapport PDF.
          </p>
        </div>
      </div>
    </div>
  </div>`;

  els('[data-review]', root).forEach((b) =>
    b.addEventListener('click', () => go('resultat', { id: b.dataset.review })));
  els('[data-patient]', root).forEach((b) =>
    b.addEventListener('click', () => go('historique', { wound: b.dataset.wound })));
}

function patientRow(p) {
  const lvl = levelOf(p.risk_level);
  return `<div class="patient-row">
    <div class="avatar">${h(initials(p.full_name))}</div>
    <div style="flex:1; min-width:0">
      <div style="font-size:13px; font-weight:600">${h(p.full_name)}</div>
      <div class="tiny" style="margin-top:2px">
        ${p.wounds_count} plaie${p.wounds_count > 1 ? 's' : ''} · ${p.analyses_count} analyse${p.analyses_count > 1 ? 's' : ''}
        ${p.last_analysis_at ? `· ${h(dateFr(p.last_analysis_at))}` : ''}
      </div>
    </div>
    <div style="text-align:right; flex:0 0 auto">
      <div class="num" style="font-size:15px; font-weight:600">${p.latest_area_cm2 != null ? num(p.latest_area_cm2, 2) : '—'}<span style="font-size:9px; font-family:var(--sans); color:var(--ink-3)"> cm²</span></div>
      <div class="tiny">${p.infection_risk != null ? `infectieux ${pct(p.infection_risk)}` : 'sans mesure'}</div>
    </div>
    ${p.risk_level ? pill(p.risk_level) : '<span class="pill">—</span>'}
    ${p.pending_reviews ? `<span class="pill watch" style="font-size:10px">${p.pending_reviews} à valider</span>` : ''}
  </div>`;
}
