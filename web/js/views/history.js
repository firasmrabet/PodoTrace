/* ═══════════════════════════════════════════════════════════════════════
   history.js — trajectoire de cicatrisation, mesures, export
   ═══════════════════════════════════════════════════════════════════════ */
import {
  S, api, icon, h, num, pct, dateFr, relFr, levelOf, pill, areaChart, toast,
  el, els, setWound, modal,
} from '../core.js';
import { go } from '../app.js';
import { exportPdf } from './result.js';

export default async function history(root, params) {
  const wounds = await api.get('/wounds');
  S.wounds = wounds;

  if (!wounds.length) {
    root.innerHTML = `<div class="page narrow">
      <div class="masthead"><div><div class="date">Trajectoire</div><h1>Aucune plaie suivie</h1></div></div>
      <div class="card center" style="padding:34px">
        <div style="color:var(--sage); margin-bottom:10px">${icon('chart', 30)}</div>
        <p class="small">La courbe de cicatrisation se construit dès la deuxième mesure.</p>
        <button class="btn mt" onclick="location.hash='#/capture'">Réaliser une première photo</button>
      </div></div>`;
    return;
  }

  const selectedId = Number(params.wound || S.currentWoundId || wounds[0].id);
  const wound = wounds.find((w) => w.id === selectedId) || wounds[0];
  setWound(wound.id);

  const [trend, analyses] = await Promise.all([
    api.get(`/wounds/${wound.id}/trend`),
    api.get(`/analysis?wound_id=${wound.id}`),
  ]);

  const series = (trend.series || []).map((p) => ({
    v: p.area_cm2,
    label: new Date(p.date).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }),
    date: p.date,
  }));
  const risks = (trend.series || []).map((p) => p.infection_risk);
  const statusTone = trend.status === 'healing' ? 'calm'
    : trend.status === 'worsening' ? 'alert' : 'watch';

  root.innerHTML = `
  <div class="page">
    <div class="masthead">
      <div>
        <div class="date">Trajectoire</div>
        <h1>${h(wound.label)}</h1>
        <div class="sub">${wound.foot_side === 'left' ? 'Pied gauche' : 'Pied droit'} ·
          ${h(wound.anatomical_site)} ${wound.wagner_grade != null ? `· Wagner ${wound.wagner_grade}` : ''}</div>
      </div>
      <div class="right">
        <button class="btn ghost sm" id="pdf">${icon('doc', 14)} Rapport</button>
        <button class="btn sm" id="new">${icon('camera', 14)} Nouvelle mesure</button>
      </div>
    </div>

    <div class="wrap-gap" style="margin-bottom:16px">
      ${wounds.map((w) => `<button class="pill ${w.id === wound.id ? 'info' : 'outline'}"
        data-wound="${w.id}" style="font-size:11.5px; padding:7px 13px">${h(w.label)}</button>`).join('')}
    </div>

    <div class="grid g4" style="margin-bottom:16px">
      <div class="tile">
        <div class="k">Réduction</div>
        <div class="v" style="color:${trend.reduction_pct > 0 ? 'var(--sage-deep)' : trend.reduction_pct < 0 ? 'var(--alert)' : 'var(--ink)'}">
          ${num(trend.reduction_pct, 1)}<small>%</small></div>
        <div class="f">sur ${num(trend.weeks_followed, 1)} semaines</div>
      </div>
      <div class="tile">
        <div class="k">Vitesse</div>
        <div class="v">${trend.rate_cm2_per_week > 0 ? '+' : ''}${num(trend.rate_cm2_per_week, 2)}<small>cm²/sem</small></div>
        <div class="f">${trend.rate_cm2_per_week > 0.05 ? 'fermeture en cours' : 'fermeture lente'}</div>
      </div>
      <div class="tile">
        <div class="k">Score PUSH</div>
        <div class="v">${trend.push_score}<small>/17</small></div>
        <div class="f">plus bas = meilleur</div>
      </div>
      <div class="tile">
        <div class="k">Index de Gilman</div>
        <div class="v">${num(trend.gilman_index, 1)}</div>
        <div class="f">> 0 : cicatrisation</div>
      </div>
    </div>

    <div class="card">
      <div class="card-h">
        <div class="t">Évolution de la surface</div>
        <div class="row" style="gap:14px">
          <span class="pill ${statusTone}"><i class="dot"></i>${h(trend.label || 'Suivi')}</span>
          <span class="tiny"><i style="display:inline-block;width:14px;height:0;border-top:2px dotted var(--alert);vertical-align:middle;margin-right:5px"></i>risque infectieux</span>
        </div>
      </div>
      ${areaChart(series, { risk: risks })}
    </div>

    ${(trend.alerts || []).length ? `<div class="banner watch mt">
      <div class="ic">${icon('alert', 16)}</div>
      <div><div class="ti">Signal de vigilance</div>
        ${trend.alerts.map((a) => `<div class="msg">${h(a)}</div>`).join('')}</div>
    </div>` : ''}

    <div class="card mt">
      <div class="card-h"><div class="t">Mesures (${analyses.length})</div>
        <span class="tiny">ordre chronologique inverse</span></div>
      <div class="grid" style="gap:0">
        ${analyses.length ? analyses.map((a) => `
          <div class="row between" style="padding:12px 0; border-bottom:1px solid var(--line-soft); gap:12px">
            <div class="row" style="gap:12px; min-width:0">
              <div style="width:44px; text-align:center; flex:0 0 auto">
                <div class="num" style="font-size:17px; font-weight:600; line-height:1">${new Date(a.captured_at).getDate()}</div>
                <div class="tiny" style="text-transform:uppercase">${new Date(a.captured_at).toLocaleDateString('fr-FR', { month: 'short' })}</div>
              </div>
              <div style="min-width:0">
                <div style="font-size:13px; font-weight:600">${num(a.area_cm2, 2)} cm²
                  <span class="tiny" style="font-weight:400"> · périmètre ${num(a.perimeter_cm, 1)} cm</span></div>
                <div class="tiny">${h(relFr(a.captured_at))} · granulation ${pct(a.tissue_composition?.granulation)} · fibrine ${pct(a.tissue_composition?.fibrin)}</div>
              </div>
            </div>
            <div class="row" style="gap:8px; flex:0 0 auto">
              ${pill(a.risk_level)}
              <button class="btn quiet sm" data-analysis="${a.id}">${icon('arrow', 14)}</button>
            </div>
          </div>`).join('')
          : `<p class="small">Aucune mesure pour cette plaie.</p>`}
      </div>
    </div>

    <div class="row mt" style="gap:9px; flex-wrap:wrap">
      <button class="btn ghost sm" id="edit">Modifier la plaie</button>
      <button class="btn danger sm" id="archive">Archiver la plaie</button>
    </div>

    <p class="tiny mt-lg">
      Courbe calculée avec recalage temporel (ORB / homographie). Les mesures successives
      sont comparables uniquement si la calibration et l'angle de prise de vue restent proches.
    </p>
  </div>`;

  els('[data-wound]', root).forEach((b) =>
    b.addEventListener('click', () => go('historique', { wound: b.dataset.wound })));
  els('[data-analysis]', root).forEach((b) =>
    b.addEventListener('click', () => go('resultat', { id: b.dataset.analysis })));
  el('#new', root).addEventListener('click', () => go('capture'));
  el('#pdf', root).addEventListener('click', (e) => exportPdf(wound.id, e.currentTarget));
  el('#edit', root).addEventListener('click', () => editWound(wound));
  el('#archive', root).addEventListener('click', () => {
    modal({
      title: 'Archiver cette plaie ?',
      body: 'Elle ne sera plus proposée pour de nouvelles mesures, mais son historique et ses rapports restent consultables.',
      confirm: 'Archiver',
      onConfirm: async () => {
        await api.patch(`/wounds/${wound.id}`, { archived: true });
        toast('Plaie archivée.', 'ok');
        go('accueil');
      },
    });
  });
}

function editWound(wound) {
  const root = document.getElementById('modal-root');
  root.innerHTML = `
    <div class="modal-bg">
      <div class="modal" role="dialog" aria-modal="true">
        <h2 style="font-size:20px">Modifier la plaie</h2>
        <form id="edit-form" class="mt">
          <div class="field"><label>Libellé</label>
            <input class="input" name="label" value="${h(wound.label)}" required></div>
          <div class="field mt-sm"><label>Grade de Wagner</label>
            <select class="input" name="wagner_grade">
              <option value="">Non renseigné</option>
              ${[0, 1, 2, 3, 4, 5].map((g) => `<option value="${g}" ${wound.wagner_grade === g ? 'selected' : ''}>Grade ${g}</option>`).join('')}
            </select></div>
          <div class="row mt-lg" style="justify-content:flex-end; gap:9px">
            <button type="button" class="btn ghost" data-close>Annuler</button>
            <button type="submit" class="btn">Enregistrer</button>
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
  el('#edit-form', root).addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api.patch(`/wounds/${wound.id}`, {
        label: fd.get('label'),
        wagner_grade: fd.get('wagner_grade') === '' ? null : Number(fd.get('wagner_grade')),
      });
      root.innerHTML = '';
      toast('Plaie mise à jour.', 'ok');
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    } catch (err) { toast(err.message, 'err'); }
  });
}
