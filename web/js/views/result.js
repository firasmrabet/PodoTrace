/* ═══════════════════════════════════════════════════════════════════════
   result.js — résultat d'analyse : couches, métriques, explication, export
   ═══════════════════════════════════════════════════════════════════════ */
import {
  S, api, icon, h, num, pct, pctRaw, dateFr, timeFr, levelOf, pill, gauge, donut,
  TISSUES, toast, el, els, modal, download, setWound,
} from '../core.js';
import { go } from '../app.js';

const LAYERS = [
  { key: 'original', short: 'Photo', label: 'Photographie originale', tag: 'Image redressée' },
  { key: 'segmentation', short: 'Tissus', label: 'Segmentation tissulaire', tag: '5 classes de tissus' },
  { key: 'contour', short: 'Contour', label: 'Contour & planimétrie', tag: 'Surface mesurée' },
  { key: 'heatmap', short: 'Grad-CAM', label: 'Carte d\'attention (Grad-CAM)', tag: 'Zones décisionnelles' },
];

export default async function result(root, params) {
  const id = params.id;
  if (!id) { go('accueil'); return; }

  const a = await api.get(`/analysis/${id}`);
  const wounds = await api.get('/wounds');
  const wound = wounds.find((w) => w.id === a.wound_id);
  setWound(a.wound_id);
  const lvl = levelOf(a.risk_level);
  const tissues = a.tissue_composition || {};
  const factors = a.risk_factors || [];
  const expl = a.explainability || {};
  const isPro = S.user?.role === 'practitioner';

  const tissueParts = TISSUES
    .map((t) => ({ label: t.label, color: t.color, v: tissues[t.key] ?? 0 }))
    .filter((p) => p.v > 0.004);

  // Les images médicales sont protégées : le jeton est passé en query pour <img>.
  const token = S.token;
  const imgUrl = (aid, variant) =>
    `/api/v1/analysis/${aid}/image/${variant}?token=${encodeURIComponent(token)}`;

  root.innerHTML = `
  <div class="page">
    <div class="masthead">
      <div>
        <div class="date">Analyse du ${h(dateFr(a.captured_at))} à ${h(timeFr(a.captured_at))}</div>
        <h1>${h(wound?.label || 'Résultat d\'analyse')}</h1>
        <div class="sub">${num(a.area_cm2, 2)} cm² · ${h(a.engine)} · ${a.processing_ms} ms</div>
      </div>
      <div class="right">
        ${pill(a.risk_level, `Risque ${lvl.label.toLowerCase()}`)}
        <button class="btn ghost sm" id="back">${icon('back', 14)} Retour</button>
      </div>
    </div>

    <div class="split">
      <div>
        <div class="viewer">
          <img id="layer-img" src="${imgUrl(a.id, 'original')}" alt="Couche d'analyse">
          <div class="tag" id="layer-tag">Image redressée</div>
        </div>
        <div class="seg mt-sm" id="layer-tabs">
          ${LAYERS.map((l, i) => `<button data-layer="${l.key}" class="${i === 0 ? 'on' : ''}">${h(l.short)}</button>`).join('')}
        </div>

        <div class="card mt">
          <div class="card-h">
            <div class="t">Composition tissulaire</div>
            <span class="tiny">${expl.method ? h(expl.method) : 'segmentation multi-classes'}</span>
          </div>
          <div class="row" style="gap:22px; align-items:center; flex-wrap:wrap">
            <div style="position:relative">
              ${donut(tissueParts, 132)}
            </div>
            <div class="legend" style="flex:1; min-width:170px">
              ${TISSUES.map((t) => {
                const v = tissues[t.key] ?? 0;
                return `<div class="li">
                  <span class="sw" style="background:${t.color}"></span>
                  <span class="nm">${t.label}</span>
                  <span class="vl">${pct(v)}</span>
                </div>`;
              }).join('')}
            </div>
          </div>
          <div class="divider"></div>
          <div class="grid g3" style="gap:10px">
            <div><div class="tiny">Surface</div><div class="num" style="font-size:18px; font-weight:600">${num(a.area_cm2, 2)} <span style="font-size:10px; font-family:var(--sans); color:var(--ink-3)">cm²</span></div></div>
            <div><div class="tiny">Périmètre</div><div class="num" style="font-size:18px; font-weight:600">${num(a.perimeter_cm, 1)} <span style="font-size:10px; font-family:var(--sans); color:var(--ink-3)">cm</span></div></div>
            <div><div class="tiny">Score PUSH</div><div class="num" style="font-size:18px; font-weight:600">${a.push_score != null ? `${a.push_score}/17` : '—'}</div></div>
          </div>
        </div>

        <div class="card mt">
          <div class="card-h"><div class="t">Points d'attention clinique</div></div>
          <div class="grid" style="gap:9px">
            ${factors.length ? factors.map(factorCard).join('')
              : `<p class="small">Aucun facteur de risque particulier détecté sur cette image.</p>`}
          </div>
        </div>

        <div class="card mt">
          <div class="card-h"><div class="t">Conduite à tenir (IWGDF 2023)</div>
            <span class="pill outline">${icon('doc', 12)} recommandations</span></div>
          <ol style="margin:0; padding-left:18px; display:grid; gap:9px">
            ${(a.recommendations || []).map((r) => `<li class="small" style="line-height:1.6">${h(r)}</li>`).join('')}
          </ol>
          ${a.uncertainty > 0.12 ? `<div class="banner watch mt">
            <div class="ic">${icon('info', 16)}</div>
            <div><div class="ti">Incertitude du modèle</div>
              <div class="msg">Dispersion des prédictions (MC dropout) : ${pctRaw(a.uncertainty * 100, 1)}.
              Le score est à interpréter avec prudence ; une seconde photographie est recommandée.</div></div>
          </div>` : ''}
        </div>
      </div>

      <div class="grid" style="gap:14px">
        <div class="card center">
          <div class="eyebrow" style="margin-bottom:10px">Risque infectieux</div>
          ${gauge(a.infection_risk, a.risk_level, lvl.label)}
          <div class="divider"></div>
          <div class="row between"><span class="small">Ischémie</span><b class="num">${pct(a.ischemia_risk)}</b></div>
          <div class="row between mt-sm"><span class="small">Incertitude</span><b class="num">±${num(a.uncertainty * 100, 1)}</b></div>
          <div class="row between mt-sm"><span class="small">Qualité image</span><b class="num">${pct(a.quality_score)}</b></div>
        </div>

        <div class="card">
          <div class="card-h"><div class="t">Calibration</div></div>
          <div class="row between"><span class="small">Méthode</span><b class="small" style="color:var(--ink)">${h(a.calibration_method)}</b></div>
          <div class="row between mt-sm"><span class="small">Échelle</span><b class="num">${num(a.pixels_per_cm, 2)} px/cm</b></div>
          <div class="tiny mt-sm">La mesure en cm² dépend directement de cette calibration.</div>
        </div>

        <div class="card">
          <div class="card-h"><div class="t">Actions</div></div>
          <div class="grid" style="gap:8px">
            <button class="btn block" id="pdf">${icon('doc', 15)} Rapport PDF</button>
            <button class="btn ghost block" id="ask">${icon('chat', 15)} Poser une question</button>
            <button class="btn ghost block" id="history">${icon('chart', 15)} Voir la trajectoire</button>
          </div>
        </div>

        ${isPro ? `<div class="card" style="border-color:#DCE8E0; background:#FAFCFA">
          <div class="card-h"><div class="t">Validation clinique</div>
            ${a.doctor_validated ? '<span class="pill calm"><i class="dot"></i>Validée</span>' : '<span class="pill watch"><i class="dot"></i>À valider</span>'}</div>
          <div class="field"><label>Ajustement du niveau de risque</label>
            <select class="input" id="override">
              <option value="">Conserver l'évaluation IA (${lvl.label})</option>
              <option value="low">Faible</option>
              <option value="moderate">Modéré</option>
              <option value="high">Élevé</option>
            </select></div>
          <div class="field mt-sm"><label>Note clinique horodatée</label>
            <textarea class="input" id="notes" placeholder="Observations, débridement réalisé…">${h(a.doctor_notes || '')}</textarea></div>
          <div class="field mt-sm"><label>Prescription de pansement</label>
            <textarea class="input" id="prescription" placeholder="Hydrocolloïde, changement tous les 3 jours…">${h(a.dressing_prescription || '')}</textarea></div>
          <button class="btn block mt" id="validate">Valider et archiver</button>
        </div>` : ''}

        <button class="btn danger block" id="delete">Supprimer cette analyse</button>

        <p class="tiny" style="line-height:1.6">
          ${icon('shield', 11)} Résultat d'aide à la décision. Ne remplace pas l'examen clinique.
          En cas de doute : avis médical sous 24 h.
        </p>
      </div>
    </div>
  </div>`;

  // couches
  els('#layer-tabs button', root).forEach((b) => {
    b.addEventListener('click', () => {
      els('#layer-tabs button', root).forEach((x) => x.classList.toggle('on', x === b));
      const layer = LAYERS.find((l) => l.key === b.dataset.layer);
      const img = el('#layer-img', root);
      img.style.opacity = '0';
      setTimeout(() => {
        img.src = imgUrl(a.id, layer.key);
        img.style.opacity = '1';
      }, 130);
      el('#layer-tag', root).textContent = layer.tag;
    });
  });

  el('#back', root).addEventListener('click', () => go('accueil'));
  el('#history', root).addEventListener('click', () => go('historique'));
  el('#ask', root).addEventListener('click', () => go('assistant', { wound: a.wound_id }));
  el('#pdf', root).addEventListener('click', (e) => exportPdf(a.wound_id, e.currentTarget));

  el('#validate', root)?.addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Enregistrement…';
    try {
      await api.patch(`/analysis/${a.id}/review`, {
        doctor_notes: el('#notes', root).value || null,
        dressing_prescription: el('#prescription', root).value || null,
        doctor_override_level: el('#override', root).value || null,
        validate: true,
      });
      toast('Évaluation validée et archivée.', 'ok');
      go('resultat', { id: a.id });
    } catch (err) {
      toast(err.message, 'err');
      btn.disabled = false;
      btn.textContent = 'Valider et archiver';
    }
  });

  el('#delete', root).addEventListener('click', () => {
    modal({
      title: 'Supprimer cette analyse ?',
      body: 'L\'image chiffrée et ses mesures seront définitivement effacées. La courbe de suivi sera recalculée.',
      confirm: 'Supprimer',
      danger: true,
      onConfirm: async () => {
        await api.del(`/analysis/${a.id}`);
        toast('Analyse supprimée.', 'ok');
        go('accueil');
      },
    });
  });
}

function factorCard(f) {
  const tone = f.severity === 'high' || f.level === 'high' ? 'alert'
    : f.severity === 'moderate' || f.level === 'moderate' ? 'watch' : 'calm';
  const sym = tone === 'alert' ? '!' : tone === 'watch' ? 'i' : '✓';
  return `<div class="factor ${tone}">
    <div class="fi">${sym}</div>
    <div>
      <div class="ft">${h(f.label || f.name || 'Facteur')}</div>
      ${f.detail ? `<div class="fd">${h(f.detail)}</div>` : ''}
    </div>
  </div>`;
}

export async function exportPdf(woundId, btn) {
  const old = btn?.innerHTML;
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner dark"></span> Génération…'; }
  try {
    const res = await api.raw(`/reports/wound/${woundId}/pdf`);
    const blob = await res.blob();
    if (blob.size < 1000) throw new Error('Le rapport généré est vide.');
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    download(blob, `diafoot-rapport-plaie-${woundId}.pdf`);
    toast('Rapport PDF généré.', 'ok');
  } catch (err) {
    toast(err.message || 'Export impossible.', 'err');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = old; }
  }
}
