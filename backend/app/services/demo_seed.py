"""Amorçage idempotent du jeu de démonstration.

Quand `AUTO_SEED_DEMO=true`, les comptes, plaies et mesures manquants sont
créés même si la base contient déjà d'autres utilisateurs.

Le résultat est un environnement immédiatement explorable : courbes, rapport
PDF, centres de soin de Tunis, fil de télésurveillance praticien.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core import storage
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.inference.pipeline import get_analyzer
from app.models.entities import DiabetesType, RiskLevel, User, UserRole, Wound, WoundAnalysis
from app.services.demo_images import trajectory_images

DEMO_PASSWORD = "diafoot2026"
PATIENT_EMAIL = "amine@diafoot.tn"
PRO_EMAIL = "dr.mansouri@diafoot.tn"

# (libellé, pied, site, grade de Wagner)
WOUNDS = [
    ("Ulcère plantaire — hallux droit", "right", "hallux", 2),
    ("Fissure talonnière — pied gauche", "left", "heel", 1),
]


#: Passe à True dès que le jeu de démonstration est complet.
DEMO_READY = False


def demo_ready() -> bool:
    """True si les comptes et les mesures de démonstration existent."""
    return DEMO_READY


def _report_ready() -> None:
    global DEMO_READY
    DEMO_READY = True


async def seed_demo_if_empty() -> bool:
    """Complète les comptes et données de démonstration manquants de façon idempotente."""
    changed = False
    async with SessionLocal() as db:
        practitioner = (
            await db.execute(select(User).where(User.email == PRO_EMAIL))
        ).scalar_one_or_none()
        if practitioner is None:
            practitioner = User(
                email=PRO_EMAIL,
                full_name="Dr Leïla Mansouri",
                hashed_password=hash_password(DEMO_PASSWORD),
                role=UserRole.practitioner,
                locale="fr",
                email_verified=True,
                consent_accepted=True,
                consent_accepted_at=datetime.now(timezone.utc),
                onboarding_done=True,
            )
            db.add(practitioner)
            await db.flush()
            changed = True
        if practitioner.role != UserRole.practitioner:
            raise RuntimeError(f"Le compte {PRO_EMAIL} n'a pas le rôle praticien.")
        if not practitioner.hashed_password:
            practitioner.hashed_password = hash_password(DEMO_PASSWORD)
            changed = True

        patient = (
            await db.execute(select(User).where(User.email == PATIENT_EMAIL))
        ).scalar_one_or_none()
        if patient is None:
            patient = User(
                email=PATIENT_EMAIL,
                full_name="Amine Ben Salah",
                hashed_password=hash_password(DEMO_PASSWORD),
                role=UserRole.patient,
                diabetes_type=DiabetesType.type_2,
                birth_year=1958,
                neuropathy=True,
                peripheral_artery_disease=True,
                referent_practitioner_id=practitioner.id,
                locale="fr",
                email_verified=True,
                consent_accepted=True,
                consent_accepted_at=datetime.now(timezone.utc),
                onboarding_done=True,
                biometric_enabled=True,
            )
            db.add(patient)
            await db.flush()
            changed = True
        if patient.role != UserRole.patient:
            raise RuntimeError(f"Le compte {PATIENT_EMAIL} n'a pas le rôle patient.")
        if not patient.hashed_password:
            patient.hashed_password = hash_password(DEMO_PASSWORD)
            changed = True
        if patient.referent_practitioner_id is None:
            patient.referent_practitioner_id = practitioner.id
            changed = True

        patient2_email = "monia@diafoot.tn"
        patient2 = (
            await db.execute(select(User).where(User.email == patient2_email))
        ).scalar_one_or_none()
        if patient2 is None:
            patient2 = User(
                email=patient2_email,
                full_name="Monia Trabelsi",
                hashed_password=hash_password(DEMO_PASSWORD),
                role=UserRole.patient,
                diabetes_type=DiabetesType.type_2,
                birth_year=1966,
                neuropathy=True,
                referent_practitioner_id=practitioner.id,
                locale="fr",
                email_verified=True,
                consent_accepted=True,
                consent_accepted_at=datetime.now(timezone.utc),
                onboarding_done=True,
            )
            db.add(patient2)
            await db.flush()
            changed = True
        if patient2.role != UserRole.patient:
            raise RuntimeError(f"Le compte {patient2_email} n'a pas le rôle patient.")
        if not patient2.hashed_password:
            patient2.hashed_password = hash_password(DEMO_PASSWORD)
            changed = True
        if patient2.referent_practitioner_id is None:
            patient2.referent_practitioner_id = practitioner.id
            changed = True

        await db.commit()

    analyzer = get_analyzer()
    images = trajectory_images(count=6)
    images_alt = trajectory_images(count=6, seed=41, mirror=True)[-2:]
    offsets_weeks = [35, 28, 21, 14, 7, 0]
    now = datetime.now(timezone.utc)

    async with SessionLocal() as db:
        patient = (await db.execute(select(User).where(User.email == PATIENT_EMAIL))).scalar_one()
        patient2 = (
            await db.execute(select(User).where(User.email == patient2_email))
        ).scalar_one()

        plans = [
            (patient, WOUNDS[0], list(zip(images, offsets_weeks)), False),
            (patient, WOUNDS[1], list(zip(images_alt, offsets_weeks[-2:])), False),
            (
                patient2,
                ("Ulcère métatarsien — pied droit", "right", "metatarsal", 3),
                [(images[1], None)],
                True,
            ),
        ]
        for owner, wound_data, measurements, force_high_risk in plans:
            label, side, site, grade = wound_data
            wound = (
                await db.execute(
                    select(Wound).where(Wound.owner_id == owner.id, Wound.label == label)
                )
            ).scalar_one_or_none()
            if wound is None:
                wound = Wound(
                    owner_id=owner.id,
                    label=label,
                    anatomical_site=site,
                    foot_side=side,
                    wagner_grade=grade,
                    created_at=now - timedelta(weeks=35),
                )
                db.add(wound)
                await db.flush()
                changed = True

            count = (
                await db.execute(
                    select(func.count(WoundAnalysis.id)).where(
                        WoundAnalysis.wound_id == wound.id
                    )
                )
            ).scalar_one()
            if count == 0:
                for img_bytes, weeks_ago in measurements:
                    captured_at = (
                        now - timedelta(weeks=weeks_ago)
                        if weeks_ago is not None
                        else now - timedelta(days=3)
                    )
                    await _insert_analysis(
                        db,
                        analyzer,
                        wound,
                        owner,
                        img_bytes,
                        captured_at=captured_at,
                        force_high_risk=force_high_risk,
                    )
                    await db.commit()
                    changed = True

        ready_count = (
            await db.execute(
                select(func.count(func.distinct(Wound.id)))
                .join(WoundAnalysis, WoundAnalysis.wound_id == Wound.id)
                .where(Wound.owner_id.in_([patient.id, patient2.id]))
            )
        ).scalar_one()
        if ready_count < 3:
            raise RuntimeError("Le jeu de démonstration n'a pas pu créer les trois plaies suivies.")
        _report_ready()

    if changed:
        print("[DiaFoot] Jeu de démonstration prêt : comptes et mesures complétés.")
    return changed


async def _insert_analysis(
    db,
    analyzer,
    wound: Wound,
    owner: User,
    image_bytes: bytes,
    *,
    captured_at: datetime,
    force_high_risk: bool = False,
) -> None:
    patient_context = {
        "neuropathy": owner.neuropathy,
        "peripheral_artery_disease": owner.peripheral_artery_disease,
        "age_over_65": bool(owner.birth_year and (datetime.now().year - owner.birth_year) > 65),
        "diabetes_type": owner.diabetes_type.value,
    }
    result = await asyncio.to_thread(
        analyzer.analyze,
        image_bytes,
        scale_ref_cm=2.0,
        manual_segment_px=None,
        patient_context=patient_context,
        with_heatmap=True,
    )
    p = result.payload
    stored = storage.save_image(image_bytes, wound.owner_id)
    variant_keys = storage.save_variants(p.get("images", {}), wound.owner_id)

    risk = p["risk"]
    level = risk["risk_level"]
    if force_high_risk and level != "high":
        level = "high"

    row = WoundAnalysis(
        wound_id=wound.id,
        owner_id=wound.owner_id,
        image_key=stored.key,
        image_sha256=stored.sha256,
        area_cm2=p["metrics"]["area_cm2"],
        perimeter_cm=p["metrics"]["perimeter_cm"],
        pixels_per_cm=p["metrics"]["pixels_per_cm"],
        calibration_method=p["calibration"]["method"],
        tissue_composition=p["tissues"]["composition"],
        infection_risk=min(1.0, risk["infection_risk"] + (0.22 if force_high_risk else 0.0)),
        ischemia_risk=risk["ischemia_risk"],
        uncertainty=risk["uncertainty"],
        risk_level=RiskLevel(level),
        risk_factors=risk["factors"],
        quality_score=p["quality"]["score"],
        quality_report=p["quality"],
        explainability={
            "method": p["explainability"]["method"],
            "target": p["explainability"]["target"],
            "stats": p["explainability"]["stats"],
            "variants": variant_keys,
        },
        engine=result.engine,
        recommendations=p["recommendations"],
        push_score=p["push_score"],
        processing_ms=result.processing_ms,
        captured_at=captured_at,
    )
    db.add(row)
    await db.flush()
