"""Assistant médical IA — chaîne de fournisseurs + RAG IWGDF + red flags.

Ordre de tentative : Groq (Llama-3.3-70B) → Mistral → OpenRouter → heuristique
locale. Sans clé API ou sans réseau, la réponse est produite par le moteur
heuristique adossé à une base de connaissances IWGDF/Wagner/Texas : le chat
reste utilisable en toutes circonstances (exigence de robustesse clinique).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core import config as _cfg

# ---------------------------------------------------------------------------
# Drapeaux rouges (détection d'urgence immédiate)
# ---------------------------------------------------------------------------
RED_FLAGS: dict[str, list[str]] = {
    "systemic_infection": [
        "fièvre", "fievre", "température", "fever", "frissons", "grelotte",
        "malaise général", "vomissements",
        "حمى", "سخانة", "حرارة", "قشعريرة", "رجفة", "دوخة", "غثيان", "تقيؤ",
    ],
    "rapid_extension": [
        "rougeur qui s'étend", "rougeur ascendante", "traînée rouge", "trainée rouge",
        "gangrène", "gangrene", "noir", "noire", "nécrose étendue", "necrose etendue",
        "très noir", "tres noir",
        "احمرار ينتشر", "احمرار متصاعد", "غرغرينا", "غرغرينة", "سواد", "كحولة",
        "نخر", "تعفن", "أسود", "كحل",
    ],
    "severe_pain": [
        "douleur brutale", "douleur intense", "douleur insupportable", "douleur atroce",
        "perte de sensibilité", "insensibilité", "pied froid", "pied bleu", "pied noir",
        "ألم حاد", "ألم شديد", "وجيعة قوية", "وجيعة لا تطاق", "فقدان الإحساس",
        "تنميل شديد", "ساق باردة", "قدم زرقاء", "قدم سوداء", "رجل باردة",
    ],
    "purulence": [
        "pus", "odeur fétide", "odeur fetide", "suppuration", "écoulement verdâtre",
        "écoulement purulent", "collection",
        "قيح", "صديد", "رائحة كريهة", "ريحة خايبة", "إفرازات", "سيلان",
    ],
    "critical_ischemia": [
        "orteil noir", "orteils noirs", "pied qui devient noir", "ischémie critique",
        "ischemie critique", "absence de pouls", "claudication", "repos douloureux",
        "أصبع أسود", "إصبع كحل", "نقص تروية", "غياب النبض", "ألم أثناء الراحة",
    ],
}

EMERGENCY_MESSAGE_FR = (
    "⚠️ URGENCE MÉDICALE POTENTIELLE — Appelez immédiatement le 15 (SAMU) ou le 190 "
    "(SAMU Tunisie) / rendez-vous aux urgences les plus proches. N'attendez pas. "
    "Ne débridez pas vous-même, ne posez aucun produit et surélevez le membre sans "
    "comprimer la plaie. DiaFoot Sentinel ne peut pas poser de diagnostic d'urgence."
)
EMERGENCY_MESSAGE_EN = (
    "⚠️ POTENTIAL MEDICAL EMERGENCY — Call your local emergency number (SAMU 15 / 190) "
    "or go to the nearest emergency department immediately. Do not self-debride, do not "
    "apply any product, and keep the limb elevated without compressing the wound."
)
EMERGENCY_MESSAGE_AR = (
    "⚠️ حالة طوارئ طبية محتملة — اتصل فوراً بالإسعاف (190 للحماية المدنية / SAMU بتونس أو 15) "
    "أو توجه إلى أقرب قسم استعجالي في المستشفى فوراً ولا تنتظر. "
    "لا تقم بتنظيف أو كشط الجرح بنفسك، ولا تضع أي مواد أو مراهم غير موصوفة، وارفع ساقك "
    "بلطف دون الضغط على موضع الجرح. DiaFoot Sentinel هو نظام مساعدة للقرار ولا يحل محل الطبيب."
)

# ---------------------------------------------------------------------------
# Base de connaissances (RAG lexical, sans dépendance externe)
# ---------------------------------------------------------------------------
KB: list[dict[str, Any]] = [
    {
        "id": "iwgdf-2023-offloading",
        "title": "IWGDF 2023 — Décharge de la plaie",
        "keywords": ["décharge", "decharge", "appui", "chaussure", "botte", "offloading"],
        "text": (
            "La décharge est la pierre angulaire du traitement d'un ulcère neuropathique "
            "du pied. Une botte de décharge irremplaçable (TCC) ou une botte amovible "
            "haute est recommandée. L'absence de décharge multiplie par 2 à 4 le risque "
            "de non-cicatrisation."
        ),
    },
    {
        "id": "iwgdf-2023-infection",
        "title": "IWGDF — Diagnostic d'infection du pied diabétique",
        "keywords": ["infection", "pus", "rougeur", "chaleur", "odeur", "fièvre"],
        "text": (
            "L'infection est clinique : ≥ 2 signes (rougeur, chaleur, œdème, douleur, "
            "purulence) ou présence de pus. Infection légère : érythème < 2 cm autour de "
            "la plaie. Modérée : érythème > 2 cm, atteinte des tissus profonds. Sévère : "
            "signes systémiques (fièvre, hypotension, confusion) → hospitalisation urgente."
        ),
    },
    {
        "id": "wagner",
        "title": "Classification de Wagner (0 à 5)",
        "keywords": ["wagner", "grade", "classification"],
        "text": (
            "Wagner 0 : pied à risque, peau intacte. 1 : ulcère superficiel. 2 : ulcère "
            "profond jusqu'au tendon/os. 3 : ulcère profond avec abcès ou ostéite. "
            "4 : gangrène localisée (orteil/avant-pied). 5 : gangrène de tout le pied."
        ),
    },
    {
        "id": "texas",
        "title": "Classification de l'Université du Texas",
        "keywords": ["texas", "classification", "profondeur"],
        "text": (
            "Stades 0 à 3 selon la profondeur (pré-ulcéreux, superficiel, tendon/capsule, "
            "os/articulation), associés aux grades A (non infecté, non ischémique), "
            "B (infecté), C (ischémique), D (infecté et ischémique)."
        ),
    },
    {
        "id": "tissue",
        "title": "Préparation du lit de la plaie (TIME)",
        "keywords": ["fibrine", "nécrose", "necrose", "débridement", "debridement", "slough", "tissu"],
        "text": (
            "Principe TIME : Tissu non viable (débridement), Inflammation/Infection, "
            "Maîtrise de l'exsudat, Épidermisation (berges). La fibrine jaune doit être "
            "débridée ; la nécrose noire sèche ne se débride jamais sans évaluation "
            "vasculaire préalable."
        ),
    },
    {
        "id": "measure",
        "title": "Mesure et suivi de la surface",
        "keywords": ["surface", "mesure", "cm2", "photo", "calibration", "gommette"],
        "text": (
            "La surface se mesure idéalement par planimétrie photographique calibrée "
            "(repère de taille connue). Une réduction < 50 % à 4 semaines est un "
            "indicateur prédictif de chronicité : réévaluez la décharge et la perfusion."
        ),
    },
    {
        "id": "ischemia",
        "title": "Artériopathie et ischémie critique",
        "keywords": ["ischémie", "ischemie", "artériopathie", "pouls", "ips", "froid", "pâle", "pale"],
        "text": (
            "Rechercher : pouls pédieux absents, IPS < 0,9, temps de recoloration > 3 s, "
            "peau froide et pâle. En ischémie critique, un bilan vasculaire urgent "
            "(écho-Doppler, avis chirurgical) est prioritaire sur tout débridement."
        ),
    },
    {
        "id": "glycemia",
        "title": "Contrôle glycémique et cicatrisation",
        "keywords": ["glycémie", "glycemie", "hba1c", "sucre", "diabète", "diabete"],
        "text": (
            "Une HbA1c > 8 % retarde significativement la cicatrisation et augmente le "
            "risque infectieux. Cible usuelle : 7 % (individualisée selon l'âge et les "
            "comorbidités)."
        ),
    },
]

SYSTEM_PROMPT_FR = """Tu es DiaFoot Sentinel, assistant médical spécialisé dans le pied diabétique.
Règles absolues :
1. Tu t'appuies exclusivement sur les guidelines IWGDF, les classifications Wagner/Texas
   et les principes TIME. Cite la source utilisée.
2. Tu ne poses JAMAIS de diagnostic définitif et ne prescris JAMAIS de médicament ou de dose.
3. Tu réponds en français, de façon empathique, structurée et concise (max 220 mots).
4. Si des signes d'urgence apparaissent (fièvre, extension rapide de la rougeur, douleur
   brutale, odeur fétide, zone noire étendue), tu commences par un encart d'urgence
   recommandant d'appeler immédiatement le 15 / 190.
5. Tu termines par une phrase rappelant que ceci est une aide à la décision et non un avis médical.
"""

SYSTEM_PROMPT_EN = """You are DiaFoot Sentinel, a medical assistant specialised in the diabetic foot.
Absolute rules: rely on IWGDF guidelines, Wagner/Texas classifications and TIME principles;
never make a definitive diagnosis or prescribe drugs/doses; answer in English, empathically and
concisely (max 220 words); start with an emergency box for red flags; end with a disclaimer that
this is decision support, not medical advice.
"""

SYSTEM_PROMPT_AR = """أنت DiaFoot Sentinel، مساعد طبي ذكي متخصص في متابعة قرحة وقدم مريض السكري وفق المعايير الدولية IWGDF 2023 وتصنيفات Wagner و Texas ومبادئ TIME.
القواعد الطبية الصارمة:
1. اعتمد حصرياً على الأدلة الإكلينيكية المعترف بها عالمياً، واذكر المصدر الطبي المستخدم.
2. لا تقدم تشخيصاً قاطعاً مطلقاً ولا تصف أي أدوية أو جرعات علاجية.
3. أجب بلغة عربية طبية واضحة، دقيقة ومتعاطفة، وبشكل منظم ومختصر (أقل من 220 كلمة).
4. عند ظهور أي علامات إنذار أو خطر حاد (سخانة/حمى، انتشار سريع للاحمرار، ألم مفاجئ، رائحة كريهة، أو ظهور مساحات سوداء نخرية)، ابدأ فوراً بإشعار طوارئ يحث المريض على الاتصال بالإسعاف (190 للحماية المدنية / SAMU في تونس أو 15) أو التوجه فوراً لأقرب قسم استعجالي.
5. اربط إجابتك دائماً بالبيانات والتحليلات الخاصة بالمريض المذكورة في ملفه الطبي (مساحة الجرح بالسنتيمتر المربع، نسب الأنسجة، مسار الشفاء).
6. اختم دائماً بتذكير واضح بأن هذه المعلومات مساعدة لاتخاذ القرار الطبي وليست بديلاً عن استشارة الطبيب المعالج.
"""


def detect_language(text: str, default: str = "fr") -> str:
    """Détecte automatiquement la langue du message (ar, fr, en)."""
    if not text:
        return default
    # Plages Unicode arabes
    if re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]", text):
        return "ar"
    low = text.lower()
    en_cues = ["the ", "is ", "wound", "what ", "how ", "should i", "pain", "doctor", "please", "help", "healing", "foot"]
    fr_cues = ["le ", "la ", "les ", "un ", "une ", "est ", "plaie", "pied", "j'ai", "c'est", "que ", "comment ", "douleur"]
    score_en = sum(1 for c in en_cues if c in low)
    score_fr = sum(1 for c in fr_cues if c in low)
    if score_en > score_fr and score_en > 0:
        return "en"
    if score_fr > 0:
        return "fr"
    return default


@dataclass
class LLMAnswer:
    reply: str
    provider: str
    sources: list[str]
    red_flag: bool
    red_flag_terms: list[str]
    emergency_message: Optional[str]
    suggestions: list[str]


# ---------------------------------------------------------------------------
# Détection des red flags
# ---------------------------------------------------------------------------
def detect_red_flags(text: str) -> tuple[bool, list[str]]:
    low = text.lower()
    found: list[str] = []
    for terms in RED_FLAGS.values():
        for t in terms:
            if re.search(r"\b" + re.escape(t), low):
                found.append(t)
    return bool(found), sorted(set(found))


def retrieve(question: str, k: int = 3) -> list[dict[str, Any]]:
    low = question.lower()
    scored = []
    for doc in KB:
        score = sum(2.0 if kw in low else 0.0 for kw in doc["keywords"])
        score += 0.5 * sum(1 for w in low.split() if len(w) > 4 and w in doc["text"].lower())
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:k]] or [KB[0]]


def build_context(
    wound: Optional[dict[str, Any]] = None,
    user: Optional[dict[str, Any]] = None,
    history: Optional[list[dict[str, Any]]] = None,
) -> str:
    lines = ["=== DOSSIER PATIENT (contexte injecté) ==="]
    if user:
        lines.append(
            f"- Diabète : {user.get('diabetes_type', 'non renseigné')}; "
            f"neuropathie : {'oui' if user.get('neuropathy') else 'non'}; "
            f"artériopathie : {'oui' if user.get('peripheral_artery_disease') else 'non'}"
        )
    if wound:
        lines.append(
            f"- Plaie « {wound.get('label')} » ({wound.get('anatomical_site')}, pied "
            f"{wound.get('foot_side')}) — Wagner {wound.get('wagner_grade', '?')}"
        )
        if wound.get("area_cm2") is not None:
            lines.append(
                f"- Dernière mesure : {wound['area_cm2']} cm², risque infectieux "
                f"{wound.get('infection_risk', 0):.2f}, ischémique "
                f"{wound.get('ischemia_risk', 0):.2f} ({wound.get('risk_level')})"
            )
        comp = wound.get("composition") or {}
        if comp:
            lines.append(
                "- Tissus : "
                + ", ".join(f"{k} {v*100:.0f}%" for k, v in comp.items() if v > 0)
            )
        if wound.get("trend"):
            lines.append(f"- Tendance : {wound['trend']}")
    if history:
        lines.append("- Échanges récents :")
        for h in history[-4:]:
            lines.append(f"  · {h['role']}: {h['content'][:160]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fournisseurs distants
# ---------------------------------------------------------------------------
PROVIDERS = [
    {
        "name": "groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "qwen/qwen3.8-27b",
        "key_env": "GROQ_API_KEY",
    },
    {
        "name": "gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": "gemini-1.5-flash",
        "key_env": "GEMINI_API_KEY",
    },
    {
        "name": "mistral",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-large-latest",
        "key_env": "MISTRAL_API_KEY",
    },
    {
        "name": "openrouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.3-70b-instruct",
        "key_env": "OPENROUTER_API_KEY",
    },
]


async def _call_provider(provider: dict[str, Any], messages: list[dict[str, str]]) -> Optional[str]:
    import os

    key = os.getenv(provider["key_env"], "")
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=28.0) as client:
            r = await client.post(
                provider["url"],
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": provider["model"],
                    "messages": messages,
                    "temperature": 0.25,
                    "max_tokens": 700,
                },
            )
            if r.status_code >= 400:
                return None
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001
        print(f"[DiaFoot][LLM] {provider['name']} indisponible : {exc}")
        return None


# ---------------------------------------------------------------------------
# Moteur heuristique (fallback trilingue hors-ligne ar / fr / en)
# ---------------------------------------------------------------------------
def heuristic_answer(question: str, docs: list[dict[str, Any]], red_flag: bool,
                     locale: str = "fr") -> str:
    low = question.lower()
    blocks: list[str] = []
    if red_flag:
        if locale == "ar":
            blocks.append("⚠️ **علامة إنذار طبي تم رصدها.** " + EMERGENCY_MESSAGE_AR)
        elif locale == "en":
            blocks.append("⚠️ **Red flag detected.** " + EMERGENCY_MESSAGE_EN)
        else:
            blocks.append("⚠️ **Signe d'alerte détecté.** " + EMERGENCY_MESSAGE_FR)

    if locale == "ar":
        blocks.append(
            "إليك المعطيات الطبية المرجعية الإكلينيكية (IWGDF) المتعلقة بحالتك المحددة:\n"
            "• **تخفيف الضغط (Décharge) :** الركيزة الأساسية لمنع تدهور القرحة هي تجنب الضغط المباشر واستعمال حذاء طبي أو وسيلة تخفيف مناسبة.\n"
            "• **مراقبة التئام الأنسجة :** التطور الإيجابي يُقاس بنمو الأنسجة الحبيبية الوردية السليمة وتراجع الأنسجة الليفية أو النخرية.\n"
            "• **مستوى السكر بالدم :** الحفاظ على معدل السكر التراكمي ومتابعته يسرع من شفاء الأوعية الدقيقة."
        )
        blocks.append(
            "**الخطوات العملية التالية :**\n"
            "1. التقط صورة جديدة بانتظام بنفس المسافة وفي إضاءة جيدة مع ظهور علامة القياس.\n"
            "2. تأكد يومياً من عدم وجود احمرار متصاعد، حرارة موضعية، أو إفرازات غير معتادة.\n"
            "3. التزم التام بتوصيات الطبيب المتابع، وفي حال ملاحظة أي تدهور راجع طبيبك خلال 48 ساعة."
        )
        blocks.append(
            "هذه المعلومات مستندة إلى توصيات IWGDF الدولية ومخصصة للمساعدة على المتابعة الطبية وليست بديلاً عن تشخيص الطبيب."
        )
    elif locale == "fr":
        intro = "Voici les éléments cliniques de référence pour votre situation :"
        if any(w in low for w in ("décharge", "decharge", "appui", "marcher", "chaussure")):
            intro = "La question de la décharge est centrale dans votre situation."
        elif any(w in low for w in ("fibrine", "jaune", "nettoyer", "nettoyage", "débrid", "debrid")):
            intro = "Le nettoyage conditionne directement la cicatrisation."
        elif any(w in low for w in ("surface", "mesure", "évolue", "evolue", "progrès", "progres")):
            intro = "Voici comment interpréter l'évolution de votre plaie."
        elif any(w in low for w in ("glycémie", "glycemie", "sucre", "hba1c", "alimentation")):
            intro = "L'équilibre glycémique est un levier majeur de cicatrisation."
        blocks.append(intro)

        for d in docs[:3]:
            blocks.append(f"**{d['title']}**\n{d['text']}")

        blocks.append(
            "**Prochaines étapes concrètes**\n"
            "1. Photographiez la plaie à la même distance, avec la gommette verte visible.\n"
            "2. Vérifiez l'absence de rougeur qui s'étend, de chaleur ou d'odeur nouvelle.\n"
            "3. Respectez la décharge prescrite, même si la douleur diminue.\n"
            "4. Signalez tout changement à votre praticien référent sous 48 h."
        )
        blocks.append(
            "Ces informations sont issues des recommandations IWGDF et constituent une "
            "aide à la décision : elles ne remplacent pas l'avis de votre médecin."
        )
    else:
        blocks.append("Here are the reference clinical elements for your situation:")
        for d in docs[:3]:
            blocks.append(f"**{d['title']}**\n{d['text']}")
        blocks.append(
            "This guidance follows IWGDF recommendations and is decision support only — "
            "it does not replace your physician's assessment."
        )
    return "\n\n".join(blocks)


def suggestions_for(locale: str = "fr") -> list[str]:
    if locale == "ar":
        return [
            "هل جرحي معرض لخطر العدوى؟",
            "كيف أقوم بتخفيف الضغط على القدم يومياً؟",
            "ماذا تعني نسب الأنسجة المكتشفة في تحليلي؟",
            "متى يجب علي التوجه فوراً للاستعجالي؟",
        ]
    if locale == "en":
        return [
            "Is my wound infected?",
            "How do I offload pressure daily?",
            "What do my tissue percentages mean?",
            "When should I seek emergency care?",
        ]
    return [
        "Ma plaie est-elle infectée ?",
        "Comment décharger mon appui au quotidien ?",
        "Que signifient mes pourcentages de tissus ?",
        "Quand dois-je consulter en urgence ?",
    ]


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
async def answer_question(
    question: str,
    *,
    wound: Optional[dict[str, Any]] = None,
    user: Optional[dict[str, Any]] = None,
    history: Optional[list[dict[str, Any]]] = None,
    locale: str = "fr",
) -> LLMAnswer:
    # Détection automatique de la langue de l'utilisateur
    effective_locale = detect_language(question, default=locale)

    red_flag, terms = detect_red_flags(question + " " + (wound or {}).get("label", ""))
    docs = retrieve(question)
    sources = [d["title"] for d in docs]
    context = build_context(wound, user, history)
    kb_block = "\n\n".join(f"[{d['title']}]\n{d['text']}" for d in docs)

    if effective_locale == "ar":
        system = SYSTEM_PROMPT_AR
    elif effective_locale == "en":
        system = SYSTEM_PROMPT_EN
    else:
        system = SYSTEM_PROMPT_FR

    messages = [
        {"role": "system", "content": f"{system}\n\n{context}\n\n=== EXTRAITS IWGDF ===\n{kb_block}"},
        *[{"role": h["role"], "content": h["content"]} for h in (history or [])[-6:]],
        {"role": "user", "content": question},
    ]

    reply: Optional[str] = None
    provider_used = "heuristic"
    for p in PROVIDERS:
        reply = await _call_provider(p, messages)
        if reply:
            provider_used = p["name"]
            break

    if not reply:
        reply = heuristic_answer(question, docs, red_flag, effective_locale)

    emergency_msg = None
    if red_flag:
        if effective_locale == "ar":
            emergency_msg = EMERGENCY_MESSAGE_AR
        elif effective_locale == "en":
            emergency_msg = EMERGENCY_MESSAGE_EN
        else:
            emergency_msg = EMERGENCY_MESSAGE_FR

    return LLMAnswer(
        reply=reply,
        provider=provider_used,
        sources=sources,
        red_flag=red_flag,
        red_flag_terms=terms,
        emergency_message=emergency_msg,
        suggestions=suggestions_for(effective_locale),
    )
