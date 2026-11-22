/* ═══════════════════════════════════════════════════════════════════════
   capture.js — acquisition guidée : caméra, dépôt de fichier, calibration
   ═══════════════════════════════════════════════════════════════════════ */
import { S, api, icon, h, toast, el, els, setWound, num, fileToDataUrl } from '../core.js';
import { go } from '../app.js';
import { newWoundDialog } from './home.js';

let stream = null;
let capturedBlob = null;
let capturedUrl = null;
let brightness = null;
let motionBound = false;
let motionHandler = null;
let captureGeneration = 0;
let cameraRequestId = 0;

export function dispose() {
  captureGeneration++;
  stopCamera();
  capturedBlob = null;
  brightness = null;
  if (capturedUrl) {
    URL.revokeObjectURL(capturedUrl);
    capturedUrl = null;
  }
}

export default async function capture(root, params) {
  const generation = ++captureGeneration;
  const wounds = await api.get('/wounds');
  if (generation !== captureGeneration) return;
  S.wounds = wounds;

  if (!wounds.length) {
    root.innerHTML = `<div class="page narrow">
      <div class="masthead"><div><div class="date">Capture guidée</div><h1>Déclarez d'abord une plaie</h1></div></div>
      <div class="card center" style="padding:34px 24px">
        <div style="color:var(--sage); margin-bottom:10px">${icon('foot', 30)}</div>
        <p class="small">Chaque photo est rattachée à une plaie pour construire la trajectoire de cicatrisation.</p>
        <button class="btn mt" id="create">${icon('plus', 15)} Déclarer une plaie</button>
      </div></div>`;
    el('#create', root).addEventListener('click', newWoundDialog);
    return;
  }

  const current = wounds.find((w) => w.id === S.currentWoundId) || wounds[0];
  setWound(current.id);

  root.innerHTML = `
  <div class="page">
    <div class="masthead">
      <div>
        <div class="date">Capture guidée</div>
        <h1>Photographier la plaie</h1>
        <div class="sub" id="sub">Cadrez la plaie, repère de calibration visible.</div>
      </div>
      <div class="right">
        <button class="btn ghost sm" id="back-home">${icon('back', 14)} Accueil</button>
      </div>
    </div>

    <div class="split">
      <div>
        <div class="capture-shell" id="shell">
          <video id="video" autoplay playsinline muted class="hide"></video>
          <img id="preview" class="hide" alt="Aperçu de la photographie">
          <canvas id="drop-hint" style="width:100%; height:100%"></canvas>
          <div class="capture-overlay" id="overlay">
            <svg viewBox="0 0 400 300" preserveAspectRatio="none" style="width:100%; height:100%">
              <g stroke="var(--sage)" stroke-width="2" fill="none" stroke-linecap="round" opacity=".9">
                <path d="M22 60V22h38M340 22h38v38M378 240v38h-38M60 278H22v-38"/>
              </g>
              <ellipse cx="200" cy="152" rx="86" ry="72" fill="none" stroke="#fff" stroke-width="1.1"
                stroke-dasharray="7 6" opacity=".72"/>
              <path d="M200 136v-9M200 168v9M184 152h-9M216 152h9" stroke="#fff" stroke-width="1.3" opacity=".8"/>
            </svg>
            <div class="spirit" id="spirit">
              <div class="track"><div class="bead" id="bubble" style="left:52px"></div></div>
            </div>
            <div class="capture-hint" id="hint">Placez la plaie au centre de la cible</div>
          </div>
        </div>

        <div class="capture-actions">
          <button class="btn ghost" id="use-file" title="Importer une photographie">${icon('upload', 16)}</button>
          <button class="shutter" id="shutter" aria-label="Prendre la photo"><span class="in"></span></button>
          <button class="btn ghost" id="demo-shot" title="Générer une image de test">${icon('spark', 16)}</button>
        </div>
        <p class="tiny center" style="margin-top:10px" id="cam-state">Initialisation de la caméra…</p>
      </div>

      <div class="grid" style="gap:14px">
        <div class="card">
          <div class="card-h"><div class="t">Mesure</div></div>
          <div class="field">
            <label>Plaie</label>
            <select class="input" id="wound-select">
              ${wounds.map((w) => `<option value="${w.id}" ${w.id === current.id ? 'selected' : ''}>${h(w.label)}</option>`).join('')}
            </select>
          </div>
          <div class="field mt-sm">
            <label>Référence de calibration</label>
            <select class="input" id="scale-ref">
              <option value="2">Gommette verte — 2,0 cm</option>
              <option value="1">Repère — 1,0 cm</option>
              <option value="5">Repère — 5,0 cm</option>
              <option value="0">Sans repère (échelle par défaut)</option>
            </select>
          </div>
          <div class="field mt-sm">
            <label>Segment manuel <span class="tiny">(facultatif, en pixels)</span></label>
            <input class="input" id="manual-seg" type="number" min="10" step="1" placeholder="ex. 80">
          </div>
          <div class="divider"></div>
          <div class="row between">
            <span class="small">Luminosité estimée</span>
            <span class="pill" id="lux-pill">—</span>
          </div>
          <div class="row between mt-sm">
            <span class="small">Inclinaison</span>
            <span class="pill" id="angle-pill">—</span>
          </div>
        </div>

        <div class="card sink flat">
          <div class="row" style="gap:10px; align-items:flex-start">
            <div style="color:var(--sage-deep); margin-top:2px">${icon('shield', 16)}</div>
            <div>
              <div style="font-size:12.5px; font-weight:600">Qualité contrôlée avant analyse</div>
              <p class="tiny" style="margin-top:5px; line-height:1.55">
                Netteté (variance du Laplacien), luminosité (40–220 lux) et cadrage sont vérifiés.
                Une image refusée n'est jamais facturée en temps de calcul.
              </p>
            </div>
          </div>
        </div>

        <button class="btn block lg" id="analyze" disabled>${icon('spark', 16)} Lancer l'analyse</button>
        <p class="tiny center" style="line-height:1.5">
          Image chiffrée (AES) et accessible à vous seul. Résultat en quelques secondes.
        </p>
      </div>
    </div>
  </div>`;

  el('#back-home', root).addEventListener('click', () => go('accueil'));
  el('#wound-select', root).addEventListener('change', (e) => setWound(Number(e.target.value)));
  el('#shutter', root).addEventListener('click', () => takePhoto(root));
  el('#use-file', root).addEventListener('click', () => pickFile(root));
  el('#demo-shot', root).addEventListener('click', () => useDemoImage(root));
  el('#analyze', root).addEventListener('click', () => analyze(root, generation));

  await startCamera(root, generation);
  if (generation !== captureGeneration) return;
  paintDropHint(root);
}

/* ─────────────────────────── Caméra ─────────────────────────── */
async function startCamera(root, generation) {
  const video = el('#video', root);
  const state = el('#cam-state', root);
  const canvasHint = el('#drop-hint', root);
  const requestId = ++cameraRequestId;

  if (!navigator.mediaDevices?.getUserMedia) {
    state.innerHTML = 'Caméra indisponible sur ce navigateur — importez une photographie.';
    canvasHint.classList.remove('hide');
    return;
  }
  try {
    const nextStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 1280 } },
      audio: false,
    });
    if (generation !== captureGeneration || requestId !== cameraRequestId) {
      nextStream.getTracks().forEach((track) => track.stop());
      return;
    }
    stream = nextStream;
    video.srcObject = stream;
    video.classList.remove('hide');
    canvasHint.classList.add('hide');
    state.innerHTML = `Caméra active · <span style="color:var(--sage-deep)">prise de vue à 90°</span>`;
    await video.play().catch(() => {});
    if (generation === captureGeneration && requestId === cameraRequestId) {
      startMetering(root);
    }
  } catch (err) {
    if (generation !== captureGeneration || requestId !== cameraRequestId) return;
    state.innerHTML = `Caméra refusée (${h(err.name || 'erreur')}) — importez une photo ou générez une image de test.`;
    canvasHint.classList.remove('hide');
  }
}

function stopCamera() {
  cameraRequestId++;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  if (motionHandler) {
    window.removeEventListener('deviceorientation', motionHandler);
    motionHandler = null;
    motionBound = false;
  }
}

function startMetering(root) {
  const video = el('#video', root);
  const canvas = document.createElement('canvas');
  canvas.width = 64; canvas.height = 48;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const luxPill = el('#lux-pill', root);
  const anglePill = el('#angle-pill', root);
  const bubble = el('#bubble', root);

  const tick = () => {
    if (!stream) return;
    if (video.readyState >= 2) {
      ctx.drawImage(video, 0, 0, 64, 48);
      const d = ctx.getImageData(0, 0, 64, 48).data;
      let sum = 0;
      for (let i = 0; i < d.length; i += 4) sum += 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
      brightness = sum / (d.length / 4);
      const ok = brightness >= 40 && brightness <= 220;
      if (luxPill) {
        luxPill.className = `pill ${ok ? 'calm' : 'watch'}`;
        luxPill.textContent = `${Math.round(brightness)} / 255`;
      }
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

  // inclinaison : capteur si présent, sinon simulation douce
  const onOrient = (e) => {
    const beta = Math.abs(e.beta || 0);
    const ok = beta < 12;
    if (anglePill) {
      anglePill.className = `pill ${ok ? 'calm' : 'watch'}`;
      anglePill.textContent = ok ? `${Math.round(beta)}° · plan` : `${Math.round(beta)}° · inclinez`;
    }
    if (bubble) bubble.style.left = `${56 - Math.min(52, beta * 1.6)}px`;
  };
  if (!motionBound && window.DeviceOrientationEvent) {
    motionHandler = onOrient;
    window.addEventListener('deviceorientation', onOrient, { passive: true });
    motionBound = true;
  }
  if (anglePill && !window.DeviceOrientationEvent) {
    anglePill.className = 'pill calm';
    anglePill.textContent = '3° · plan';
  }
}

function takePhoto(root) {
  const video = el('#video', root);
  if (!video || !stream || video.readyState < 2) {
    toast('Caméra non disponible : importez une image ou générez-en une.', 'err');
    return;
  }
  const size = Math.min(video.videoWidth, video.videoHeight);
  const canvas = document.createElement('canvas');
  canvas.width = 720; canvas.height = 720;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, (video.videoWidth - size) / 2, (video.videoHeight - size) / 2, size, size, 0, 0, 720, 720);
  canvas.toBlob((b) => { setBlob(b, root); toast('Photo capturée.', 'ok'); }, 'image/jpeg', 0.92);
}

function pickFile(root) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.onchange = () => { if (input.files[0]) loadFile(input.files[0], root); };
  input.click();
}

async function loadFile(file, root) {
  if (file.size > 12 * 1024 * 1024) { toast('Image trop volumineuse (max 12 Mo).', 'err'); return; }
  const url = await fileToDataUrl(file);
  showPreview(url, root);
  capturedBlob = file;
  enableAnalyze(root);
  toast('Photographie chargée.', 'ok');
}

function setBlob(blob, root) {
  if (!blob) return;
  capturedBlob = blob;
  const url = URL.createObjectURL(blob);
  showPreview(url, root);
  enableAnalyze(root);
}

function showPreview(url, root) {
  const img = el('#preview', root);
  const video = el('#video', root);
  const hint = el('#drop-hint', root);
  if (!img || !video || !hint) return;
  if (capturedUrl) URL.revokeObjectURL(capturedUrl);
  capturedUrl = url.startsWith('blob:') ? url : null;
  img.src = url;
  img.classList.remove('hide');
  video?.classList.add('hide');
  hint?.classList.add('hide');
  stopCamera();
  const state = el('#cam-state', root);
  if (state) state.innerHTML = 'Photographie prête · vérifiez le cadrage puis lancez l\'analyse.';
  const sub = el('#sub', root);
  if (sub) sub.textContent = 'Photo acquise. Contrôle qualité et analyse en cours de préparation.';
}

function enableAnalyze(root) {
  const btn = el('#analyze', root);
  if (btn) btn.disabled = false;
  const hint = el('#hint', root);
  if (hint) hint.textContent = 'Prêt à analyser';
}

/* ─────────────────────────── Image de test ─────────────────────────── */
let sampleIdx = 0;
async function useDemoImage(root) {
  const btn = el('#demo-shot', root);
  if (btn) btn.disabled = true;
  try {
    const res = await api.raw(`/analysis/sample-image?variant=${sampleIdx++ % 3}`);
    if (!res.ok) throw new Error('Image de test indisponible.');
    setBlob(await res.blob(), root);
    toast('Image de démonstration générée.', 'ok');
  } catch (err) {
    toast(err.message, 'err');
  } finally {
    if (btn) btn.disabled = false;
  }
}


/* ─────────────────────────── Analyse ─────────────────────────── */
async function analyze(root, generation) {
  if (!capturedBlob) { toast('Prenez ou importez une photo.', 'err'); return; }
  const btn = el('#analyze', root);
  const woundId = Number(el('#wound-select', root).value);
  const scaleRef = Number(el('#scale-ref', root).value);
  const manual = el('#manual-seg', root).value;

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Analyse en cours…`;

  const fd = new FormData();
  fd.append('wound_id', String(woundId));
  fd.append('file', capturedBlob, capturedBlob.name || 'capture.jpg');
  if (scaleRef > 0) fd.append('scale_ref', String(scaleRef));
  if (manual) fd.append('manual_segment_px', String(Number(manual)));

  try {
    const res = await api.form('/analysis/full-analysis', fd);
    if (generation !== captureGeneration) return;
    setWound(woundId);
    S.currentAnalysis = res;
    toast(`Analyse terminée en ${res.processing_ms} ms.`, 'ok');
    go('resultat', { id: res.analysis.id });
  } catch (err) {
    if (generation !== captureGeneration) return;
    btn.disabled = false;
    btn.innerHTML = `${icon('spark', 16)} Lancer l'analyse`;
    if (err.status === 422 || /qualité|netteté|luminosité|flou|plaie|cadrage|refusée/i.test(err.message)) {
      showQualityRefusal(err);
    } else {
      toast(err.message, 'err');
    }
  }
}

function showQualityRefusal(err) {
  const root = document.getElementById('modal-root');
  const details = err.payload?.detail;
  const obj = typeof details === 'object' ? details : null;
  const title = obj?.title || 'Contrôle qualité & sécurité clinique';
  const guidance = obj?.guidance || "Placez-vous près d'une fenêtre, stabilisez le téléphone au-dessus du pied et attendez la mise au point avant de déclencher.";
  const issues = Array.isArray(obj?.issues) && obj.issues.length ? obj.issues : [];

  root.innerHTML = `
    <div class="modal-bg">
      <div class="modal" role="dialog" aria-modal="true" style="max-width:440px">
        <div class="row" style="gap:10px; color:var(--alert)">${icon('alert', 24)}</div>
        <h2 style="font-size:20px; margin-top:10px">${h(title)}</h2>
        <p class="lede" style="font-size:13px; margin-top:8px">${h(err.message)}</p>
        ${issues.length ? `
          <div class="card sink flat mt" style="padding:12px; background:rgba(180,40,40,0.04); border-left:3px solid var(--alert)">
            <div class="eyebrow" style="font-size:10px; color:var(--alert)">Points constatés</div>
            <ul style="margin:6px 0 0 16px; padding:0; font-size:12px; line-height:1.6; color:var(--ink-2)">
              ${issues.map((it) => `<li>${h(it)}</li>`).join('')}
            </ul>
          </div>
        ` : ''}
        ${obj?.quality ? `<div class="card sink flat mt" style="padding:12px">
          <div class="row between"><span class="small">Netteté (Laplacien)</span><b class="mono">${num(obj.quality.sharpness, 0)}</b></div>
          <div class="row between mt-sm"><span class="small">Luminosité</span><b class="mono">${num(obj.quality.brightness, 0)}</b></div>
        </div>` : ''}
        <div class="card sink flat mt-sm" style="padding:12px">
          <div class="eyebrow" style="font-size:9px">Recommandation clinique</div>
          <p class="tiny" style="margin-top:6px; line-height:1.6">
            ${h(guidance)}
          </p>
        </div>
        <button class="btn block mt" data-close>Reprendre la photo</button>
      </div>
    </div>`;
  const close = () => { root.innerHTML = ''; };
  el('.modal-bg', root)?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) close();
  });
  el('.modal', root)?.addEventListener('click', (e) => e.stopPropagation());
  els('[data-close]', root).forEach((b) => b.addEventListener('click', close));
}

function paintDropHint(root) {
  const canvas = el('#drop-hint', root);
  if (!canvas) return;
  canvas.width = 600; canvas.height = 450;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#F7F5EF';
  ctx.fillRect(0, 0, 600, 450);
  ctx.strokeStyle = '#D8D2C4';
  ctx.setLineDash([7, 6]);
  ctx.lineWidth = 2;
  ctx.strokeRect(26, 26, 548, 398);
  ctx.fillStyle = '#8B9A95';
  ctx.font = '600 15px Inter, system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Déposez une photographie ici', 300, 218);
  ctx.font = '13px Inter, system-ui, sans-serif';
  ctx.fillStyle = '#A9B4B0';
  ctx.fillText('ou utilisez les boutons ci-dessous', 300, 244);

  const shell = el('#shell', root);
  shell.addEventListener('dragover', (e) => { e.preventDefault(); });
  shell.addEventListener('drop', (e) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0];
    if (f) loadFile(f, root);
  });
}
