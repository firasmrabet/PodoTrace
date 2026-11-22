"""Pipeline d'analyse : upload multipart universel (bytes) → inférence → résultat."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, ImageUser, audit, get_owned_wound
from app.core import storage
from app.core.config import settings
from app.inference.pipeline import ImageQualityError, analyze_async, get_analyzer
from app.models.entities import RiskLevel, User, Wound, WoundAnalysis
from app.schemas.schemas import AnalysisOut, DoctorReview, FullAnalysisResponse

router = APIRouter(prefix="/analysis", tags=["Analyse IA"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/jpg", "image/bmp"}


@router.get("/engine/status")
async def engine_status():
    """Diagnostic du moteur d'inférence (poids chargés, OpenCV, PyTorch)."""
    return get_analyzer().status()


@router.get("/sample-image")
async def sample_image(user: CurrentUser, variant: int = Query(0, ge=0, le=5)):
    """Photographie de plaie synthétique calibrée (bouton « image de test »).

    Sert à démontrer le pipeline complet sans caméra : l'image est produite par
    le même générateur que le jeu de démonstration (peau texturée, érythème,
    berge épithélialisée, gommette verte de 2 cm).
    """
    from app.services.demo_images import make_wound_image

    profiles = [
        dict(fibrin=0.42, necrosis=0.16, radius_scale=0.85),
        dict(fibrin=0.30, necrosis=0.05, radius_scale=0.70),
        dict(fibrin=0.18, necrosis=0.00, radius_scale=0.55),
    ]
    profile = profiles[variant % len(profiles)]
    jpeg = make_wound_image(seed=100 + variant, mirror=bool(variant % 2), **profile)
    return Response(content=jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/full-analysis", response_model=FullAnalysisResponse)
async def full_analysis(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    wound_id: int = Form(...),
    file: UploadFile = File(...),
    scale_ref: float = Form(2.0),
    manual_segment_px: Optional[float] = Form(None),
    aruco_size_cm: Optional[float] = Form(None),
):
    """Analyse complète d'une photographie de plaie (multipart/form-data)."""
    wound = await get_owned_wound(wound_id, db, user)

    payload_bytes = await file.read()
    if not payload_bytes:
        raise HTTPException(status_code=400, detail="Fichier image vide.")
    if len(payload_bytes) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Image trop volumineuse (max {settings.MAX_UPLOAD_MB} Mo).",
        )
    if file.content_type and file.content_type.lower() not in ALLOWED_TYPES:
        # Certains clients Web envoient application/octet-stream : on tolère,
        # le décodage Pillow reste le juge de paix.
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=415,
                detail="Format non pris en charge. Envoyez une image JPEG ou PNG.",
            )

    owner = await db.get(User, wound.owner_id)
    patient_context = {
        "neuropathy": bool(owner.neuropathy) if owner else False,
        "peripheral_artery_disease": bool(owner.peripheral_artery_disease) if owner else False,
        "age_over_65": bool(owner.birth_year and (datetime.now().year - owner.birth_year) > 65)
        if owner and owner.birth_year
        else False,
        "diabetes_type": owner.diabetes_type.value if owner else "none",
    }

    try:
        result = await analyze_async(
            payload_bytes,
            scale_ref_cm=scale_ref,
            manual_segment_px=manual_segment_px,
            patient_context=patient_context,
            with_heatmap=True,
        )
    except ImageQualityError as exc:
        await audit(db, request, "analysis.rejected", user.id, f"wound:{wound_id}",
                    exc.payload())
        await db.commit()
        raise HTTPException(status_code=422, detail=exc.payload()) from exc

    p = result.payload
    stored = storage.save_image(payload_bytes, wound.owner_id)
    variant_keys = storage.save_variants(p.get("images", {}), wound.owner_id)

    analysis = WoundAnalysis(
        wound_id=wound_id,
        owner_id=wound.owner_id,
        image_key=stored.key,
        image_sha256=stored.sha256,
        area_cm2=p["metrics"]["area_cm2"],
        perimeter_cm=p["metrics"]["perimeter_cm"],
        pixels_per_cm=p["metrics"]["pixels_per_cm"],
        calibration_method=p["calibration"]["method"],
        tissue_composition=p["tissues"]["composition"],
        infection_risk=p["risk"]["infection_risk"],
        ischemia_risk=p["risk"]["ischemia_risk"],
        uncertainty=p["risk"]["uncertainty"],
        risk_level=RiskLevel(p["risk"]["risk_level"]),
        risk_factors=p["risk"]["factors"],
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
    )
    db.add(analysis)
    await db.flush()
    await audit(db, request, "analysis.create", user.id, f"analysis:{analysis.id}")
    await db.commit()
    await db.refresh(analysis)

    return FullAnalysisResponse(
        analysis=AnalysisOut.model_validate(analysis),
        images=p["images"],
        metrics=p["metrics"],
        tissues=p["tissues"],
        risk=p["risk"],
        quality=p["quality"],
        calibration=p["calibration"],
        explainability=p["explainability"],
        recommendations=p["recommendations"],
        disclaimer=p["disclaimer"],
        processing_ms=result.processing_ms,
    )


@router.get("", response_model=list[AnalysisOut])
async def list_analyses(
    user: CurrentUser,
    db: DbSession,
    wound_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
):
    stmt = select(WoundAnalysis).order_by(WoundAnalysis.captured_at.desc()).limit(limit)
    if wound_id is not None:
        await get_owned_wound(wound_id, db, user)
        stmt = stmt.where(WoundAnalysis.wound_id == wound_id)
    elif user.role.value == "patient":
        stmt = stmt.where(WoundAnalysis.owner_id == user.id)
    elif user.role.value == "practitioner":
        stmt = stmt.join(User, User.id == WoundAnalysis.owner_id).where(
            User.referent_practitioner_id == user.id
        )
    rows = (await db.execute(stmt)).scalars().all()
    return [AnalysisOut.model_validate(r) for r in rows]


@router.get("/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(analysis_id: int, user: CurrentUser, db: DbSession):
    row = await db.get(WoundAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable")
    await _assert_access(row, user, db)
    return AnalysisOut.model_validate(row)


@router.get("/{analysis_id}/image/{variant}")
async def get_analysis_image(
    analysis_id: int,
    variant: str,
    user: ImageUser,
    db: DbSession,
):
    """Sert l'image **déchiffrée** à la volée. Accès strictement contrôlé.

    Accepte le jeton dans l'en-tête `Authorization` **ou** dans `?token=`
    (nécessaire pour les balises `<img>`, incapables d'envoyer un en-tête).
    """
    row = await db.get(WoundAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable")
    await _assert_access(row, user, db)

    variant = (variant or "original").lower()
    key = row.image_key
    if variant not in {"original", "source", "photo"}:
        key = (row.explainability or {}).get("variants", {}).get(variant, "")
        if not key:
            raise HTTPException(
                status_code=404,
                detail=f"Couche « {variant} » indisponible pour cette analyse.",
            )
    try:
        data = storage.load_image(key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="Image purgée du stockage") from exc
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=600",
                             "X-Content-Type-Options": "nosniff"})


@router.patch("/{analysis_id}/review", response_model=AnalysisOut)
async def doctor_review(
    analysis_id: int, payload: DoctorReview, user: CurrentUser, db: DbSession, request: Request
):
    """Human-in-the-Loop : correction clinique du résultat IA par le praticien."""
    if user.role.value == "patient":
        raise HTTPException(status_code=403, detail="Réservé aux professionnels de santé.")
    row = await db.get(WoundAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable")
    await _assert_access(row, user, db)
    if payload.doctor_notes is not None:
        row.doctor_notes = payload.doctor_notes
        row.doctor_notes_at = datetime.now(timezone.utc)
    if payload.doctor_override_level:
        row.doctor_override_level = RiskLevel(payload.doctor_override_level)
    if payload.dressing_prescription is not None:
        row.dressing_prescription = payload.dressing_prescription
    row.doctor_validated = payload.validate_review
    await audit(db, request, "analysis.review", user.id, f"analysis:{analysis_id}")
    await db.commit()
    await db.refresh(row)
    return AnalysisOut.model_validate(row)


@router.delete("/{analysis_id}", status_code=204)
async def delete_analysis(analysis_id: int, user: CurrentUser, db: DbSession):
    row = await db.get(WoundAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable")
    if row.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Suppression réservée au propriétaire")
    explainability = row.explainability if isinstance(row.explainability, dict) else {}
    variants = explainability.get("variants")
    image_keys = {row.image_key}
    if isinstance(variants, dict):
        image_keys.update(key for key in variants.values() if isinstance(key, str))
    for key in image_keys:
        storage.purge_image(key)
    await db.delete(row)
    await db.commit()
    return None


async def _assert_access(row: WoundAnalysis, user: User, db: DbSession):
    uid = user.id
    if row.owner_id == uid:
        return
    if user.role.value == "admin":
        return
    if user.role.value in {"practitioner", "admin"}:
        owner = await db.get(User, row.owner_id)
        if owner and owner.referent_practitioner_id == user.id:
            return
    raise HTTPException(status_code=403, detail="Accès non autorisé à cette ressource")
