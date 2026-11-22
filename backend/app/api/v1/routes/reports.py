"""Génération et téléchargement des rapports PDF médicaux."""
from __future__ import annotations

import base64
import unicodedata
from urllib.parse import quote
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, audit
from app.core import storage
from app.inference import engine
from app.inference.pipeline import decode_image
from app.models.entities import User, Wound, WoundAnalysis
from app.inference.temporal import TrajectoryPoint, healing_trajectory
from app.services.pdf_report import build_report

router = APIRouter(prefix="/reports", tags=["Rapports PDF"])


def _data_uri(jpeg_bytes: bytes, max_side: int = 700) -> Optional[str]:
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=84, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:  # noqa: BLE001
        return None


@router.get("/wound/{wound_id}/pdf")
async def wound_report(
    wound_id: int, user: CurrentUser, db: DbSession, request: Request, inline: bool = False
):
    wound = await db.get(Wound, wound_id)
    if wound is None:
        raise HTTPException(status_code=404, detail="Plaie introuvable")
    if wound.owner_id != user.id and user.role.value == "patient":
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    rows = (
        await db.execute(
            select(WoundAnalysis)
            .where(WoundAnalysis.wound_id == wound_id)
            .order_by(WoundAnalysis.captured_at)
        )
    ).scalars().all()
    if not rows:
        raise HTTPException(
            status_code=409,
            detail="Aucune analyse disponible : réalisez au moins une mesure avant d'exporter.",
        )

    patient = await db.get(User, wound.owner_id)
    practitioner = (
        await db.get(User, patient.referent_practitioner_id)
        if patient and patient.referent_practitioner_id
        else (user if user.role.value != "patient" else None)
    )

    analyses_payload = [
        {
            "captured_at": r.captured_at.strftime("%Y-%m-%d %H:%M"),
            "area_cm2": r.area_cm2,
            "perimeter_cm": r.perimeter_cm,
            "infection_risk": r.infection_risk,
            "ischemia_risk": r.ischemia_risk,
            "uncertainty": r.uncertainty,
            "risk_level": r.doctor_override_level.value
            if r.doctor_override_level
            else r.risk_level.value,
            "tissue_composition": r.tissue_composition or {},
            "risk_factors": r.risk_factors or [],
            "recommendations": r.recommendations or [],
            "doctor_notes": r.doctor_notes,
        }
        for r in rows
    ]

    points = [
        TrajectoryPoint(
            date=r.captured_at, area_cm2=r.area_cm2, infection_risk=r.infection_risk,
            ischemia_risk=r.ischemia_risk, composition=r.tissue_composition or {},
        )
        for r in rows
    ]
    trajectory = healing_trajectory(points)

    # Images : première analyse, dernière analyse, segmentation régénérée
    images: dict[str, str] = {}
    try:
        first_bytes = storage.load_image(rows[0].image_key)
        images["initial"] = _data_uri(first_bytes) or ""
        last_bytes = storage.load_image(rows[-1].image_key)
        images["current"] = _data_uri(last_bytes) or ""
        bgr = decode_image(last_bytes)
        seg = engine.segment_tissues(bgr)
        overlay = engine.render_tissue_overlay(bgr, seg.mask, alpha=0.6)
        from app.inference.pipeline import _b64_png

        images["segmentation"] = _b64_png(overlay, max_side=700)
    except Exception as exc:  # noqa: BLE001
        print(f"[PodoTrace][PDF] Images indisponibles : {exc}")

    pdf = build_report(
        patient={
            "full_name": patient.full_name or patient.email if patient else "—",
            "diabetes_type": patient.diabetes_type.value if patient else "—",
            "neuropathy": patient.neuropathy if patient else False,
            "peripheral_artery_disease": patient.peripheral_artery_disease if patient else False,
        },
        practitioner={"full_name": practitioner.full_name} if practitioner else None,
        wound={
            "id": wound.id, "label": wound.label, "anatomical_site": wound.anatomical_site,
            "foot_side": "droit" if wound.foot_side == "right" else "gauche",
            "wagner_grade": wound.wagner_grade,
        },
        analyses=analyses_payload,
        images=images,
        trajectory=trajectory,
        observations=analyses_payload[-1].get("doctor_notes"),
    )

    storage.save_report(pdf, f"wound_{wound_id}/{datetime.now():%Y%m%d%H%M%S}.pdf.enc")
    await audit(db, request, "report.export", user.id, f"wound:{wound_id}",
                {"bytes": len(pdf)})
    await db.commit()

    disposition = "inline" if inline else "attachment"
    # Nom de fichier : repli ASCII + encodage RFC 5987 pour les accents
    ascii_label = (
        unicodedata.normalize("NFKD", wound.label)
        .encode("ascii", "ignore")
        .decode()
        .replace(" ", "_")
        or "plaie"
    )
    ascii_name = f"PodoTrace_Sentinel_{ascii_label}_{datetime.now():%Y%m%d}.pdf"
    utf8_name = quote(f"PodoTrace_Sentinel_{wound.label.replace(' ', '_')}_{datetime.now():%Y%m%d}.pdf")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/summary")
async def export_summary(user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Données structurées pour un partage sécurisé (JSON) ou une intégration DPI."""
    rows = (
        await db.execute(
            select(WoundAnalysis)
            .where(WoundAnalysis.owner_id == user.id)
            .order_by(WoundAnalysis.captured_at.desc())
            .limit(200)
        )
    ).scalars().all()
    return {
        "patient": {"id": user.id, "full_name": user.full_name,
                    "diabetes_type": user.diabetes_type.value},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analyses": [
            {
                "id": r.id, "wound_id": r.wound_id,
                "captured_at": r.captured_at.isoformat(),
                "area_cm2": r.area_cm2, "perimeter_cm": r.perimeter_cm,
                "infection_risk": r.infection_risk, "ischemia_risk": r.ischemia_risk,
                "risk_level": r.risk_level.value,
                "tissue_composition": r.tissue_composition,
            }
            for r in rows
        ],
    }
