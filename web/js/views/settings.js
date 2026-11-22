/* ═══════════════════════════════════════════════════════════════════════
   settings.js — profil clinique, sécurité, conformité, diagnostic
   ═══════════════════════════════════════════════════════════════════════ */
import { S, api, icon, h, toast, el, els, setToken, initials, dateFr, num, store } from '../core.js';
import { go } from '../app.js';

export default async function settings(root) {
  const me = await api.get('/auth/me');
  S.user = me;
  const engine = await api.get('/analysis/engine/status').catch(() => null);
  const isPro = me.role === 'practitioner';

  root.innerHTML = `
  <div class="page">
    <div class="masthead">
      <div>
        <div class="date">Profil & données</div>
        <h1>${h(me.full_name || me.email)}</h1>
        <div class="sub">${isPro ? 'Professionnel de santé' : 'Patient'} · membre depuis ${h(dateFr(me.created_at))}</div>
      </div>
      <div class="right">
        <span class="pill ${me.email_verified ? 'calm' : 'watch'}"><i class="dot"></i>${me.email_verified ? 'Email vérifié' : 'Email non vérifié'}</span>
      </div>
    </div>

    <div class="split">
      <div class="grid" style="gap:14px">
        <div class="card">
          <div class="card-h"><div class="t">Identité</div>
            <div class="avatar lg">${h(initials(me.full_name))}</div></div>
          <div class="grid g2" style="gap:12px">
            <div class="field"><label>Nom complet</label>
              <input class="input" id="full_name" value="${h(me.full_name || '')}" placeholder="Votre nom"></div>
            <div class="field"><label>Adresse email</label>
              <input class="input" value="${h(me.email)}" disabled></div>
          </div>
          <div class="grid g2 mt-sm" style="gap:12px">
            <div class="field"><label>Année de naissance</label>
              <input class="input" id="birth_year" type="number" min="1900" max="2026" value="${me.birth_year || ''}" placeholder="1974"></div>
            <div class="field"><label>Langue</label>
              <select class="input" id="locale">
                <option value="fr" ${me.locale === 'fr' ? 'selected' : ''}>Français</option>
                <option value="en" ${me.locale === 'en' ? 'selected' : ''}>English</option>
              </select></div>
          </div>
          <button class="btn mt" id="save-identity">Enregistrer</button>
        </div>

        <div class="card">
          <div class="card-h"><div class="t">Terrain clinique</div>
            <span class="tiny">utilisé pour pondérer le risque</span></div>
          ${[
            ['neuropathy', 'Neuropathie sensitive', 'Perte de la sensibilité protectrice (facteur majeur de récidive)'],
            ['peripheral_artery_disease', 'Artériopathie (AOMI)', 'Ischémie distale documentée'],
            ['biometric_enabled', 'Déverrouillage biométrique', 'Sur mobile : Face ID / empreinte'],
          ].map(([key, label, desc]) => `
            <div class="row between" style="padding:11px 0; border-bottom:1px solid var(--line-soft)">
              <div><div style="font-size:12.5px; font-weight:600">${label}</div>
                <div class="tiny" style="margin-top:2px">${desc}</div></div>
              <button class="toggle" data-toggle="${key}" data-value="${me[key] ? '1' : '0'}" aria-pressed="${me[key]}"
                style="width:38px; height:22px; border-radius:999px; position:relative; flex:0 0 auto;
                background:${me[key] ? 'var(--sage)' : '#DDD8CC'}; transition:background .2s">
                <span style="position:absolute; top:3px; ${me[key] ? 'right:3px' : 'left:3px'}; width:16px; height:16px;
                  border-radius:50%; background:#fff; transition:all .2s"></span>
              </button>
            </div>`).join('')}
          <div class="row between mt-sm">
            <span class="small">Type de diabète</span>
            ${isPro ? `<span class="pill">${h(me.specialty || 'praticien')}</span>` : `
              <select class="input" id="diabetes_type" style="width:auto; padding:6px 30px 6px 10px; font-size:12px">
                <option value="type_1" ${me.diabetes_type === 'type_1' ? 'selected' : ''}>Type 1</option>
                <option value="type_2" ${me.diabetes_type === 'type_2' ? 'selected' : ''}>Type 2</option>
                <option value="gestational" ${me.diabetes_type === 'gestational' ? 'selected' : ''}>Gestationnel</option>
                <option value="other" ${me.diabetes_type === 'other' ? 'selected' : ''}>Autre</option>
                <option value="none" ${me.diabetes_type === 'none' ? 'selected' : ''}>Non renseigné</option>
              </select>`}
          </div>
        </div>

        <div class="card">
          <div class="card-h"><div class="t">Données & conformité</div></div>
          ${[
            ['lock', 'Chiffrement AES au repos', 'Les images médicales sont chiffrées sur disque et déchiffrées à la volée.'],
            ['shield', 'Outil d\'aide en validation', 'Non validé médicalement — aucun diagnostic autonome.'],
            ['user', 'Accès contrôlé par jeton', 'Chaque requête vérifie la propriété de la plaie avant tout envoi.'],
            ['doc', 'Traçabilité', 'Chaque analyse, validation et export est horodaté dans le journal d\'audit.'],
          ].map(([icn, title, desc]) => `
            <div class="row" style="gap:11px; align-items:flex-start; padding:9px 0">
              <span style="color:var(--sage-deep); margin-top:1px">${icon(icn, 15)}</span>
              <div><div style="font-size:12.5px; font-weight:600">${title}</div>
                <div class="tiny" style="margin-top:2px; line-height:1.5">${desc}</div></div>
            </div>`).join('')}
        </div>
      </div>

      <div class="grid" style="gap:14px">
        ${engine ? `<div class="card">
          <div class="card-h"><div class="t">Moteur d'inférence</div>
            <span class="pill ${engine.torch ? 'calm' : 'outline'}">${engine.torch ? 'PyTorch' : 'OpenCV'}</span></div>
          <div class="row between"><span class="small">Moteur actif</span><b class="small mono">${h(engine.engine)}</b></div>
          <div class="row between mt-sm"><span class="small">OpenCV</span><b class="small mono">${engine.opencv ? '✓' : '—'}</b></div>
          <div class="row between mt-sm"><span class="small">Poids .pth</span><b class="small mono">${engine.weights_loaded ? 'chargés' : 'absents'}</b></div>
          <div class="row between mt-sm"><span class="small">Passes MC dropout</span><b class="small mono">${engine.mc_dropout_passes ?? '—'}</b></div>
          <p class="tiny mt-sm" style="line-height:1.5">
            ${engine.weights_loaded
              ? 'Segmentation par réseau profond.'
              : 'Repli colorimétrique calibré : le pipeline complet reste opérationnel sans poids.'}
          </p>
        </div>` : ''}

        <div class="card">
          <div class="card-h"><div class="t">Session</div></div>
          <p class="tiny" style="line-height:1.6">
            Jeton JWT stocké localement pour cette session. La déconnexion efface le jeton
            et les données mises en cache.
          </p>
          <button class="btn ghost block mt" id="logout">${icon('logout', 15)} Se déconnecter</button>
          <button class="btn quiet block mt-sm" id="docs">Ouvrir la documentation API</button>
        </div>

        <div class="card sink flat">
          <div class="eyebrow" style="font-size:9px">Version</div>
          <p class="tiny mt-sm" style="line-height:1.6">
            DiaFoot Sentinel v1.0.0 · interface web.<br>
            Backend FastAPI · segmentation multi-tissus · RAG IWGDF.<br>
            Urgences : <b>15</b> (SAMU) · <b>190</b> (Tunisie).
          </p>
        </div>
      </div>
    </div>
  </div>`;

  el('#save-identity', root).addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';
    try {
      const body = {
        full_name: el('#full_name', root).value,
        birth_year: el('#birth_year', root).value ? Number(el('#birth_year', root).value) : null,
        locale: el('#locale', root).value,
      };
      const dt = el('#diabetes_type', root);
      if (dt) body.diabetes_type = dt.value;
      S.user = await api.patch('/auth/me', body);
      toast('Profil mis à jour.', 'ok');
    } catch (err) { toast(err.message, 'err'); }
    finally { btn.disabled = false; btn.textContent = 'Enregistrer'; }
  });

  els('[data-toggle]', root).forEach((btn) => {
    btn.addEventListener('click', async () => {
      const key = btn.dataset.toggle;
      const next = btn.dataset.value !== '1';
      btn.dataset.value = next ? '1' : '0';
      btn.setAttribute('aria-pressed', String(next));
      btn.style.background = next ? 'var(--sage)' : '#DDD8CC';
      btn.firstElementChild.style.left = next ? 'auto' : '3px';
      btn.firstElementChild.style.right = next ? '3px' : 'auto';
      try {
        S.user = await api.patch('/auth/me', { [key]: next });
        toast('Préférence enregistrée.', 'ok');
      } catch (err) { toast(err.message, 'err'); }
    });
  });

  el('#logout', root).addEventListener('click', () => {
    setToken(null);
    S.user = null;
    store.remove('df.wound');
    window.dispatchEvent(new CustomEvent('df:logout'));
  });

  el('#docs', root).addEventListener('click', () => window.open('/docs', '_blank'));
}
