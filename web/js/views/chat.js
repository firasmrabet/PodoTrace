/* ═══════════════════════════════════════════════════════════════════════
   chat.js — assistant médical RAG (IWGDF), contexte patient injecté
   ═══════════════════════════════════════════════════════════════════════ */
import { S, api, icon, h, md, toast, el, els, dateFr, num, pct } from '../core.js';
import { go } from '../app.js';

export default async function chat(root, params) {
  const [wounds, suggestions, history] = await Promise.all([
    api.get('/wounds').catch(() => []),
    api.get('/chat/suggestions').catch(() => ({ suggestions: [] })),
    api.get('/chat/history').catch(() => []),
  ]);
  S.wounds = wounds;

  const wound = wounds.find((w) => w.id === Number(params.wound || S.currentWoundId)) || wounds[0] || null;
  const chips = suggestions.suggestions || suggestions || [];

  root.innerHTML = `
  <div class="page">
    <div class="masthead">
      <div>
        <div class="date">Assistant médical</div>
        <h1>Une question sur la plaie ?</h1>
        <div class="sub">
          ${wound
            ? `Contexte : ${h(wound.label)} · ${wound.latest_area_cm2 != null ? num(wound.latest_area_cm2, 2) + ' cm²' : 'sans mesure'}`
            : 'Aucune plaie sélectionnée'}
        </div>
      </div>
      <div class="right">
        <span class="pill outline">${icon('spark', 12)} IWGDF 2023</span>
        <span class="pill" id="engine-pill" title="Moteur de réponse de l'assistant">RAG local</span>
      </div>
    </div>

    <div class="card" style="padding:18px">
      <div class="chat-wrap">
        <div class="chat-scroll" id="scroll"></div>
        <div class="composer">
          <textarea class="input" id="msg" rows="1" placeholder="Décrivez ce que vous observez…"></textarea>
          <button class="btn" id="send" aria-label="Envoyer">${icon('send', 16)}</button>
        </div>
      </div>
    </div>

    <div class="wrap-gap mt" id="suggestions">
      ${chips.slice(0, 4).map((c) => `<button class="pill outline" data-chip="${h(c)}"
        style="padding:7px 13px; font-size:11.5px; cursor:pointer">${h(c)}</button>`).join('')}
    </div>

    <div class="banner watch mt">
      <div class="ic">${icon('alert', 16)}</div>
      <div>
        <div class="ti">Urgence</div>
        <div class="msg">Fièvre, douleur brutale, odeur fétide, rougeur qui s'étend ou zone noire :
          appelez le <b>15</b> (SAMU) ou le <b>190</b> sans attendre. L'assistant ne remplace jamais un médecin.</div>
      </div>
    </div>
  </div>`;

  const scroll = el('#scroll', root);

  if (!history.length) {
    pushBubble('ia', `Bonjour. Je suis l'assistant PodoTrace, adossé aux recommandations IWGDF.
Je peux expliquer un résultat, décrire les soins de décharge ou repérer un signe d'alerte.
Je ne pose pas de diagnostic et ne prescris pas de médicament.`);
  } else {
    history.slice(-30).forEach((m) => {
      if (m.red_flag && m.role === 'assistant') scroll.appendChild(flagCard(null));
      pushBubble(m.role === 'assistant' ? 'ia' : 'me', m.content, m.sources, m.red_flag, null);
    });
  }
  scroll.scrollTop = scroll.scrollHeight;

  els('[data-chip]', root).forEach((b) =>
    b.addEventListener('click', () => { el('#msg', root).value = b.dataset.chip; send(); }));

  const ta = el('#msg', root);
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  ta.addEventListener('input', () => {
    ta.style.height = 'auto';
    ta.style.height = Math.min(130, ta.scrollHeight) + 'px';
    if (/[\u0600-\u06FF]/.test(ta.value)) {
      ta.style.direction = 'rtl';
      ta.style.textAlign = 'right';
    } else {
      ta.style.direction = 'ltr';
      ta.style.textAlign = 'left';
    }
  });
  el('#send', root).addEventListener('click', send);

  async function send() {
    const text = ta.value.trim();
    if (!text) return;
    ta.value = '';
    ta.style.height = 'auto';
    pushBubble('me', text);
    const typing = pushTyping();
    el('#send', root).disabled = true;

    try {
      const res = await api.post('/chat', {
        message: text,
        wound_id: wound?.id || null,
        locale: S.locale,
      });
      typing.remove();
      if (res.red_flag) scroll.appendChild(flagCard(res.emergency_message));
      const pill = el('#engine-pill', root);
      if (pill) {
        pill.textContent = res.provider && res.provider !== 'heuristic'
          ? `LLM · ${res.provider}` : 'RAG local';
        pill.className = `pill ${res.provider && res.provider !== 'heuristic' ? 'calm' : ''}`;
      }
      pushBubble('ia', res.reply, res.sources, res.red_flag, res.emergency_message);
      if (res.suggestions?.length) {
        el('#suggestions', root).innerHTML = res.suggestions.slice(0, 4)
          .map((c) => `<button class="pill outline" data-chip="${h(c)}" style="padding:7px 13px; font-size:11.5px; cursor:pointer">${h(c)}</button>`)
          .join('');
        els('[data-chip]', root).forEach((b) =>
          b.addEventListener('click', () => { el('#msg', root).value = b.dataset.chip; send(); }));
      }
    } catch (err) {
      typing.remove();
      toast(err.message, 'err');
      pushBubble('ia', "Je ne parviens pas à joindre le service pour le moment. En cas de signe d'alerte, contactez directement le 15 ou le 190.");
    } finally {
      el('#send', root).disabled = false;
      scroll.scrollTop = scroll.scrollHeight;
    }
  }

  /* Le moteur renvoie déjà le message d'urgence dans `reply` : on le retire du
     texte pour ne pas l'afficher deux fois (carte + bulle). */
  function stripEmergency(text, emergency) {
    let body = text || '';
    if (emergency && body.includes(emergency)) body = body.split(emergency).join(' ');
    body = body.replace(/⚠️?\s*URGENCE MÉDICALE POTENTIELLE[\s\S]*?diagnostic d'urgence\./gi, ' ');
    body = body.replace(/^[\s*_]*(⚠️?)?\s*\**\s*Signe d'alerte détecté\.?\s*\**[\s*_]*/i, '');
    body = body.replace(/⚠️/g, ' ');
    return body.replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
  }

  function flagCard(emergency) {
    const card = document.createElement('div');
    card.className = 'chat-flag';
    card.setAttribute('role', 'alert');
    card.innerHTML = `<div class="ic">${icon('alert', 18)}</div>
      <div><b>Signe d'urgence détecté</b>
      <p>${h(emergency || 'Appelez immédiatement le 190 (Tunisie) ou le 15 (France) — ou rendez-vous aux urgences les plus proches.')}</p></div>`;
    return card;
  }

  function pushBubble(who, text, sources = [], redFlag = false, emergency = null) {
    const node = document.createElement('div');
    node.className = `bubble ${who}`;
    const isArabic = /[\u0600-\u06FF]/.test(text || '');
    if (isArabic) {
      node.style.direction = 'rtl';
      node.style.textAlign = 'right';
      node.style.lineHeight = '1.7';
    }
    const body = redFlag ? stripEmergency(text, emergency) : text;
    node.innerHTML = `<div>${md(body)}</div>${sources?.length
      ? `<div class="src">${sources.map((s) => `<span>${h(s)}</span>`).join('')}</div>` : ''}`;
    scroll.appendChild(node);
    scroll.scrollTop = scroll.scrollHeight;
    return node;
  }

  function pushTyping() {
    const node = document.createElement('div');
    node.className = 'bubble ia';
    node.innerHTML = `<span class="typing"><i></i><i></i><i></i></span>`;
    scroll.appendChild(node);
    scroll.scrollTop = scroll.scrollHeight;
    return node;
  }
}
