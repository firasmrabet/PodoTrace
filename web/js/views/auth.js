/* ═══════════════════════════════════════════════════════════════════════
   auth.js — connexion, création de compte, vérification OTP
   ═══════════════════════════════════════════════════════════════════════ */
import { S, api, setToken, icon, h, toast, el, els } from '../core.js';

const DEMO = {
  patient: { email: 'amine@podotrace.tn', password: 'podotrace2026' },
  pro: { email: 'dr.mansouri@podotrace.tn', password: 'podotrace2026' },
  aidant: { email: 'monia@podotrace.tn', password: 'podotrace2026' },
};

let mode = 'login';
let pendingEmail = '';
let devCode = '';

export function renderAuth(root) {
  root.innerHTML = `
  <div class="auth">
    <section class="auth-art">
      <div class="veil"></div>
      <div class="art-body" style="position:relative; z-index:1">
        <div class="row" style="gap:11px">
          <div class="mark" style="width:42px; height:42px; border-radius:13px">${icon('foot', 23)}</div>
          <div>
            <div style="font-family:var(--serif); font-size:16px; font-weight:600">PodoTrace</div>
            <div class="tiny" style="letter-spacing:.16em; text-transform:uppercase; margin-top:2px">Télésurveillance</div>
          </div>
        </div>

        <div style="margin-top:clamp(40px,9vh,86px)">
          <div class="eyebrow">Pied diabétique · suivi continu</div>
          <div class="quote" style="margin-top:16px">
            Voir la plaie <em>évoluer</em>,<br>avant qu'elle ne s'aggrave.
          </div>
          <p class="sub">
            Une photographie calibrée suffit : mesure de la surface, composition des tissus,
            niveau de risque et trajectoire de cicatrisation — expliqués, jamais imposés.
          </p>
        </div>

        <div style="position:relative; z-index:1; margin-top:clamp(26px,5vh,54px); max-width:380px">
          ${artPlate()}
        </div>
      </div>
      <div class="foot" style="position:relative; z-index:1">
        <span>${icon('lock', 12)} Données chiffrées au repos</span>
        <span>RGPD · HDS</span>
        <span>IWGDF 2023</span>
      </div>
    </section>

    <section class="auth-form">
      <div class="inner" id="auth-inner"></div>
    </section>
  </div>`;

  paint();
}

/* Fine planche anatomique filaire — dessinée, jamais chargée */
function artPlate() {
  return `<svg viewBox="0 0 300 210" width="100%" style="max-width:360px" aria-hidden="true">
    <defs>
      <linearGradient id="ar1" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#5C8570" stop-opacity=".26"/>
        <stop offset="100%" stop-color="#5C8570" stop-opacity=".04"/>
      </linearGradient>
    </defs>
    <path d="M12 168h276" stroke="#CFC9BA" stroke-width="1"/>
    <g fill="none" stroke="#5C8570" stroke-opacity=".62" stroke-width="1.1">
      <ellipse cx="150" cy="46" rx="16" ry="13"/>
      <ellipse cx="176" cy="39" rx="11" ry="9"/>
      <ellipse cx="195" cy="47" rx="9" ry="8"/>
      <ellipse cx="210" cy="60" rx="8" ry="7"/>
      <ellipse cx="221" cy="76" rx="7" ry="6"/>
      <path d="M150 59c19 0 34 5 46 11 11 6 22 16 22 32 0 23-6 31-11 47-6 23-8 42-23 54-13 11-32 13-47 4-17-9-23-28-25-49-2-19-6-27-6-44 0-15 2-28 11-38 8-11 21-17 33-17z"
        stroke-dasharray="4 4" stroke-opacity=".45"/>
    </g>
    <g stroke="#B98C3C" stroke-width="1.2" fill="none" stroke-opacity=".8">
      <path d="M150 96v12M144 102h12"/>
      <circle cx="150" cy="102" r="16" fill="url(#ar1)" stroke="none"/>
    </g>
    <g font-family="Inter,system-ui" font-size="8" fill="#8B9A95" letter-spacing=".1em">
      <text x="216" y="96">HALLUX</text>
      <text x="20" y="188">MESURE · 2,0 CM</text>
      <text x="20" y="200" fill="#B0BBB6">CALIBRATION PAR REPÈRE</text>
    </g>
    <path d="M60 178h22M60 174v8M82 174v8" stroke="#9FB3A8" stroke-width="1"/>
  </svg>`;
}

function paint() {
  const inner = el('#auth-inner');
  if (!inner) return;
  if (mode === 'otp') { paintOtp(inner); return; }

  inner.innerHTML = `
    <div class="steps"><i class="on"></i><i></i><i></i></div>
    <h2>${mode === 'login' ? 'Reprendre le suivi' : 'Créer votre espace'}</h2>
    <p class="small" style="margin-top:6px">
      ${mode === 'login'
        ? 'Vos mesures, vos courbes et votre rapport clinique.'
        : 'Un compte sécurisé, vérifié par code à 6 chiffres.'}
    </p>

    <div class="seg mt" id="mode-switch">
      <button data-mode="login" class="${mode === 'login' ? 'on' : ''}">Connexion</button>
      <button data-mode="register" class="${mode === 'register' ? 'on' : ''}">Créer un compte</button>
    </div>

    ${mode === 'login' ? `
    <div class="demo-strip mt">
      <div class="row between" style="align-items:baseline">
        <span class="eyebrow" style="font-size:9px">Accès de démonstration</span>
        <span class="tiny">aucun mot de passe</span>
      </div>
      <button type="button" class="btn block mt-sm" data-demo="patient">
        ${icon('foot', 15)} Entrer dans la démo
      </button>
      <div class="row" style="gap:8px; margin-top:8px">
        <button type="button" class="btn ghost sm" data-demo="pro" style="flex:1">Praticien</button>
        <button type="button" class="btn ghost sm" data-demo="aidant" style="flex:1">Proche</button>
      </div>
    </div>` : ''}

    <form id="auth-form" class="mt" novalidate>
      ${mode === 'register' ? `
        <div class="grid g2" style="gap:10px">
          <div class="field"><label>Nom complet</label>
            <input class="input" name="full_name" placeholder="Amine Ben Salah" autocomplete="name" required></div>
          <div class="field"><label>Profil</label>
            <select class="input" name="role">
              <option value="patient">Patient</option>
              <option value="practitioner">Professionnel de santé</option>
            </select></div>
        </div>` : ''}

      <div class="field mt-sm"><label>Adresse email</label>
        <input class="input" type="email" name="email" placeholder="vous@exemple.tn" autocomplete="email" required></div>

      <div class="field mt-sm"><label>Mot de passe</label>
        <input class="input" type="password" name="password"
          placeholder="${mode === 'login' ? 'Votre mot de passe' : 'Ex. Sentinel2026!'}"
          autocomplete="${mode === 'login' ? 'current-password' : 'new-password'}" required minlength="8">
        ${mode === 'register' ? `<span class="tiny" style="margin-top:2px">
          8 caractères minimum, avec une majuscule, un chiffre et un caractère spécial.</span>` : ''}
      </div>

      ${mode === 'register' ? `
        <div class="field mt-sm" data-for="patient"><label>Type de diabète</label>
          <select class="input" name="diabetes_type">
            <option value="type_2">Type 2</option>
            <option value="type_1">Type 1</option>
            <option value="gestational">Gestationnel</option>
            <option value="other">Autre</option>
          </select></div>
        <div class="field mt-sm hide" data-for="pro"><label>Spécialité</label>
          <select class="input" name="specialty">
            <option value="diabetology">Diabétologie</option>
            <option value="vascular_surgery">Chirurgie vasculaire</option>
            <option value="podiatry">Podologie</option>
            <option value="dermatology">Dermatologie</option>
            <option value="nursing">Soins infirmiers</option>
          </select></div>

        <label class="checkline mt" id="consent" style="margin-top:16px">
          <span class="box">${icon('check', 11)}</span>
          <span class="small" style="color:var(--ink-2); line-height:1.55">
            J'accepte le traitement chiffré de mes données de santé (RGPD / HDS) et je comprends
            que PodoTrace est une <b>aide à la décision</b>, non un diagnostic.
          </span>
        </label>` : `
        <div class="row between mt-sm">
          <span class="tiny">Session sécurisée · jeton JWT</span>
          <span class="tiny" style="color:var(--sage-deep)">Mot de passe oublié ?</span>
        </div>`}

      <button class="btn block lg mt" type="submit" id="submit-btn">
        ${mode === 'login' ? 'Se connecter' : 'Recevoir mon code'}
        ${icon('arrow', 16)}
      </button>
    </form>

    <button class="btn ghost block sm" id="google-btn" style="margin-top:12px; font-weight:500; color:var(--ink-2)">
      <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
        <path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2a9.6 9.6 0 0 0 3-7.3z"/>
        <path fill="#34A853" d="M12 22a9.9 9.9 0 0 0 6.8-2.5l-3.3-2.5a6.2 6.2 0 0 1-9.2-3.3H2.9v2.6A10 10 0 0 0 12 22z"/>
        <path fill="#FBBC05" d="M6.3 13.7a6 6 0 0 1 0-3.8V7.3H2.9a10 10 0 0 0 0 8.9z"/>
        <path fill="#EA4335" d="M12 5.9a5.4 5.4 0 0 1 3.8 1.5l2.8-2.8A9.6 9.6 0 0 0 2.9 7.3l3.4 2.6A6 6 0 0 1 12 5.9z"/>
      </svg>
      Continuer avec Google
    </button>

    <p class="tiny center" style="margin-top:16px; line-height:1.5">
      Urgence médicale : <b>15</b> (SAMU) ou <b>190</b> (Tunisie).
    </p>`;

  // bascule connexion / inscription
  els('#mode-switch button', inner).forEach((b) =>
    b.addEventListener('click', () => { mode = b.dataset.mode; paint(); }));

  // consentement
  let consented = false;
  const consent = el('#consent', inner);
  if (consent) {
    consent.addEventListener('click', (e) => {
      e.preventDefault();
      consented = !consented;
      consent.classList.toggle('on', consented);
    });
  }

  // rôle → champs conditionnels
  const roleSel = el('[name=role]', inner);
  if (roleSel) {
    const sync = () => {
      const pro = roleSel.value === 'practitioner';
      el('[data-for=patient]', inner)?.classList.toggle('hide', pro);
      el('[data-for=pro]', inner)?.classList.toggle('hide', !pro);
    };
    roleSel.addEventListener('change', sync);
    sync();
  }

  // soumission
  el('#auth-form', inner).addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = el('#submit-btn', inner);
    const fd = new FormData(e.target);
    const data = Object.fromEntries(fd.entries());

    if (mode === 'register') {
      if (!consented) { toast('Le consentement éclairé est obligatoire.', 'err'); return; }
      const pw = data.password || '';
      const missing = [];
      if (pw.length < 8) missing.push('8 caractères');
      if (!/[A-Z]/.test(pw)) missing.push('une majuscule');
      if (!/[0-9]/.test(pw)) missing.push('un chiffre');
      if (!/[^A-Za-z0-9]/.test(pw)) missing.push('un caractère spécial');
      if (missing.length) {
        toast(`Mot de passe trop faible : il manque ${missing.join(', ')}.`, 'err');
        return;
      }
    }

    if (mode === 'login') {
      const email = (data.email || '').trim();
      const emailField = el('[name=email]', inner);
      const passField = el('[name=password]', inner);
      if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
        toast("Saisissez votre adresse e-mail — ou entrez directement avec un accès de démonstration (Patient / Praticien / Proche).", 'err');
        emailField?.focus();
        return;
      }
      if (!data.password) {
        toast('Saisissez votre mot de passe.', 'err');
        passField?.focus();
        return;
      }
    }

    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Vérification…`;
    try {
      if (mode === 'login') {
        const res = await api.post('/auth/login', { email: data.email.trim(), password: data.password });
        return finish(res);
      }
      const res = await api.post('/auth/register', {
        email: data.email.trim(),
        password: data.password,
        full_name: data.full_name || '',
        role: data.role || 'patient',
        diabetes_type: data.diabetes_type || 'none',
        specialty: data.role === 'practitioner' ? data.specialty : null,
        consent_accepted: true,
        locale: 'fr',
      });
      pendingEmail = res.email;
      devCode = res.dev_otp || '';
      mode = 'otp';
      paint();
      toast('Code de vérification généré.', 'ok');
      return;
    } catch (err) {
      if (err.status === 403 && err.payload?.detail?.code === 'email_not_verified') {
        pendingEmail = data.email.trim();
        devCode = err.payload.detail.dev_otp || '';
        mode = 'otp';
        paint();
        return;
      }
      toast(err.message, 'err');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `${mode === 'login' ? 'Se connecter' : 'Recevoir mon code'} ${icon('arrow', 16)}`;
    }
  });

  let googleInitialized = false;
  el('#google-btn', inner)?.addEventListener('click', async () => {
    try {
      const cfg = await fetch('/config').then((r) => r.json()).catch(() => null);
      const clientId = cfg?.google_client_id;
      if (!clientId) {
        toast('Google Sign-In nécessite GOOGLE_CLIENT_ID dans backend/.env. Utilisez l\'accès de démonstration ou l\'inscription par email.', 'err');
        return;
      }
      if (!window.google?.accounts?.id) {
        const s = document.createElement('script');
        s.src = 'https://accounts.google.com/gsi/client';
        s.async = true;
        s.defer = true;
        document.head.appendChild(s);
        await new Promise((resolve) => { s.onload = resolve; setTimeout(resolve, 1500); });
      }

      if (!googleInitialized && window.google?.accounts?.id) {
        window.google.accounts.id.initialize({
          client_id: clientId,
          use_fedcm_for_prompt: true,
          callback: async (response) => {
            try {
              const res = await api.post('/auth/google', { id_token: response.credential });
              finish(res);
            } catch (err) {
              toast(err.message || 'Échec de la connexion Google', 'err');
            }
          },
        });
        googleInitialized = true;
      }

      window.google.accounts.id.prompt((notification) => {
        // Notification silencieuse de statut FedCM
        if (notification.isSkippedMoment?.() || notification.isDismissedMoment?.()) {
          console.info('[Google Sign-In] Invite fermée ou ignorée.');
        }
      });
    } catch (e) {
      toast('Google Sign-In non disponible : ' + (e.message || ''), 'err');
    }
  });

  els('[data-demo]', inner).forEach((b) =>
    b.addEventListener('click', () => demoLogin(b.dataset.demo, b)));
}

/**
 * Au tout premier démarrage, le jeu de démonstration est créé en tâche de fond
 * (quelques secondes sur une machine lente). On attend `/health` → demo_ready
 * plutôt que d'afficher un échec incompréhensible.
 */
async function waitForDemo(maxMs = 25000) {
  const t0 = Date.now();
  while (Date.now() - t0 < maxMs) {
    try {
      // /health est hors du préfixe /api/v1 : appel direct, sans passer par `api`.
      const r = await fetch('health', { cache: 'no-store' });
      if (r.ok) {
        const body = await r.json();
        if (body.demo_ready !== false) return true;
      }
    } catch (_) { /* serveur pas encore prêt : on réessaie */ }
    await new Promise((r) => setTimeout(r, 700));
  }
  return false;
}

async function demoLogin(kind, btn) {
  const creds = DEMO[kind];
  const old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner dark"></span>';
  try {
    if (!(await waitForDemo())) {
      toast('Préparation des données de démonstration en cours — réessayez dans un instant.', 'err');
      return;
    }
    const res = await api.post('/auth/login', creds);
    finish(res);
  } catch (err) {
    const msg = String(err.message || '');
    toast(/401|identifiants/i.test(msg)
      ? 'Compte de démonstration en cours de création — réessayez dans 2 secondes.'
      : (msg || 'Compte de démonstration indisponible — créez un compte.'), 'err');
  } finally {
    btn.disabled = false;
    btn.innerHTML = old;
  }
}

function paintOtp(inner) {
  inner.innerHTML = `
    <div class="steps"><i class="on"></i><i class="on"></i><i class="on"></i></div>
    <h2>Code de vérification</h2>
    <p class="small" style="margin-top:6px">
      Saisissez les 6 chiffres envoyés à <b style="color:var(--ink)">${h(pendingEmail)}</b>
    </p>
    <div class="otp mt" id="otp-inputs">
      ${[0, 1, 2, 3, 4, 5].map((i) => `<input inputmode="numeric" maxlength="1" aria-label="Chiffre ${i + 1}">`).join('')}
    </div>
    <div class="row between mt-sm">
      <span class="tiny">Code non reçu ?</span>
      <button class="btn quiet sm" id="resend">Renvoyer</button>
    </div>
    ${devCode ? `<div class="devcode">Environnement de développement — code : <b>${h(devCode)}</b></div>` : ''}
    <button class="btn block lg mt" id="verify">Vérifier ${icon('arrow', 16)}</button>
    <button class="btn quiet block mt-sm" id="back">Utiliser un autre compte</button>
    <p class="tiny center" style="margin-top:18px">${icon('shield', 11)} Code à usage unique · 5 minutes · 3 tentatives</p>`;

  const inputs = els('#otp-inputs input', inner);
  inputs[0]?.focus();
  inputs.forEach((inp, i) => {
    inp.addEventListener('input', () => {
      inp.value = inp.value.replace(/\D/g, '').slice(0, 1);
      inp.classList.toggle('filled', !!inp.value);
      if (inp.value && i < 5) inputs[i + 1].focus();
      if (inputs.every((x) => x.value)) el('#verify', inner).click();
    });
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !inp.value && i > 0) inputs[i - 1].focus();
    });
    inp.addEventListener('paste', (e) => {
      const txt = (e.clipboardData.getData('text') || '').replace(/\D/g, '').slice(0, 6);
      if (!txt) return;
      e.preventDefault();
      txt.split('').forEach((c, k) => { if (inputs[k]) { inputs[k].value = c; inputs[k].classList.add('filled'); } });
      inputs[Math.min(txt.length, 5)].focus();
    });
  });

  if (devCode) {
    inputs.forEach((inp, i) => { inp.value = devCode[i] || ''; inp.classList.add('filled'); });
  }

  const verify = async () => {
    const code = inputs.map((x) => x.value).join('');
    if (code.length !== 6) { toast('Saisissez les 6 chiffres.', 'err'); return; }
    const btn = el('#verify', inner);
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Vérification…';
    try {
      const res = await api.post('/auth/verify-otp', { email: pendingEmail, code });
      finish(res);
    } catch (err) {
      toast(err.message, 'err');
      btn.disabled = false;
      btn.innerHTML = `Vérifier ${icon('arrow', 16)}`;
    }
  };
  el('#verify', inner).addEventListener('click', verify);

  el('#resend', inner).addEventListener('click', async () => {
    try {
      const res = await api.post('/auth/resend-otp', { email: pendingEmail, code: '000000' });
      devCode = res.dev_otp || devCode;
      toast('Nouveau code envoyé.', 'ok');
      paint();
    } catch (err) { toast(err.message, 'err'); }
  });

  el('#back', inner).addEventListener('click', () => { mode = 'login'; paint(); });
}

function finish(res) {
  setToken(res.access_token);
  S.user = res.user;
  window.dispatchEvent(new CustomEvent('df:authenticated', { detail: { user: res.user } }));
}
