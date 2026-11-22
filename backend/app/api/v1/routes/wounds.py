"""Gestion des plaies suivies + tableaux de bord (patient & praticien)."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, Practitioner, get_owned_wound
from app.models.entities import RiskLevel, User, UserRole, Wound, WoundAnalysis
from app.schemas.schemas import (
    DashboardStats,
    WoundCreate,
    WoundOut,
    WoundUpdate,
)
from app.inference.temporal import TrajectoryPoint, healing_trajectory

router = APIRouter(prefix="/wounds", tags=["Plaies"])


def _aggregate(wound: Wound, analyses: Optional[list[WoundAnalysis]] = None) -> WoundOut:
    if analyses is None:
        analyses = list(wound.__dict__.get("analyses") or [])
    analyses = sorted(analyses, key=lambda a: a.captured_at)
    latest = analyses[-1] if analyses else None
    trend = None
    if len(analyses) >= 2 and analyses[0].area_cm2 > 0:
        trend = round(
            (analyses[0].area_cm2 - latest.area_cm2) / analyses[0].area_cm2 * 100, 2
        )
    out = WoundOut.model_validate(wound)
    out.latest_area_cm2 = round(latest.area_cm2, 2) if latest else None
    out.latest_risk_level = latest.risk_level.value if latest else None
    out.latest_infection_risk = round(latest.infection_risk, 3) if latest else None
    out.analysis_count = len(analyses)
    out.trend_pct = trend
    out.sparkline = [round(a.area_cm2, 2) for a in analyses[-10:]]
    return out


def _dashboard_trend(wounds: list[Wound]) -> Optional[float]:
    baseline_area = 0.0
    latest_area = 0.0
    tracked_wounds = 0
    for wound in wounds:
        analyses = sorted(wound.analyses or [], key=lambda a: a.captured_at)
        if len(analyses) < 2 or analyses[0].area_cm2 <= 0:
            continue
        baseline_area += analyses[0].area_cm2
        latest_area += analyses[-1].area_cm2
        tracked_wounds += 1
    if not tracked_wounds or baseline_area <= 0:
        return None
    return round((baseline_area - latest_area) / baseline_area * 100, 2)


@router.get("", response_model=list[WoundOut])
async def list_wounds(
    user: CurrentUser,
    db: DbSession,
    include_archived: bool = Query(False),
    patient_id: Optional[int] = Query(None, description="Praticien : dossier d'un patient"),
):
    stmt = select(Wound).options(selectinload(Wound.analyses))
    if patient_id is not None:
        if user.role == UserRole.patient:
            raise HTTPException(status_code=403, detail="Réservé aux professionnels de santé.")
        if user.role == UserRole.practitioner:
            assigned_patient_id = (
                await db.execute(
                    select(User.id).where(
                        User.id == patient_id,
                        User.referent_practitioner_id == user.id,
                    )
                )
            ).scalar_one_or_none()
            if assigned_patient_id is None:
                raise HTTPException(status_code=403, detail="Accès non autorisé à ce dossier.")
        stmt = stmt.where(Wound.owner_id == patient_id)
    elif user.role == UserRole.patient:
        stmt = stmt.where(Wound.owner_id == user.id)
    elif user.role == UserRole.practitioner:
        stmt = stmt.join(User, User.id == Wound.owner_id).where(
            User.referent_practitioner_id == user.id
        )
    if not include_archived:
        stmt = stmt.where(Wound.archived.is_(False))
    wounds = (await db.execute(stmt.order_by(Wound.created_at.desc()))).scalars().all()
    return [_aggregate(w) for w in wounds]


@router.post("", response_model=WoundOut, status_code=201)
async def create_wound(payload: WoundCreate, user: CurrentUser, db: DbSession):
    wound = Wound(owner_id=user.id, **payload.model_dump())
    db.add(wound)
    await db.commit()
    wound = (
        await db.execute(
            select(Wound).options(selectinload(Wound.analyses)).where(Wound.id == wound.id)
        )
    ).scalar_one()
    return _aggregate(wound)


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(user: CurrentUser, db: DbSession):
    stmt = (
        select(Wound)
        .options(selectinload(Wound.analyses))
        .where(Wound.owner_id == user.id, Wound.archived.is_(False))
    )
    wounds = (await db.execute(stmt)).scalars().all()
    analyses = [a for w in wounds for a in (w.analyses or [])]
    analyses.sort(key=lambda a: a.captured_at)

    latest = analyses[-1] if analyses else None
    trend = _dashboard_trend(wounds)

    critical = sum(
        1
        for w in wounds
        if w.analyses and w.analyses[-1].risk_level == RiskLevel.high
    )
    if not analyses:
        status = "no_data"
        message = "Réalisez votre première analyse pour activer la télésurveillance."
    elif critical:
        status = "alert"
        message = (
            f"Alerte : {critical} plaie(s) à risque infectieux élevé. "
            "Un avis médical est recommandé sous 24 h."
        )
    elif trend is not None and trend > 10:
        status = "improving"
        message = f"Amélioration : surface réduite de {trend:.0f} % depuis la première mesure."
    else:
        status = "stable"
        message = "État stable : poursuivez la décharge et la surveillance hebdomadaire."

    return DashboardStats(
        active_wounds=len(wounds),
        total_analyses=len(analyses),
        last_area_cm2=round(latest.area_cm2, 2) if latest else None,
        trend_pct=trend,
        global_status=status,
        banner_message=message,
        critical_wounds=critical,
        next_follow_up_days=7 if analyses else None,
    )


@router.get("/{wound_id}", response_model=WoundOut)
async def get_wound(wound_id: int, user: CurrentUser, db: DbSession):
    stmt = select(Wound).options(selectinload(Wound.analyses)).where(Wound.id == wound_id)
    wound = (await db.execute(stmt)).scalar_one_or_none()
    if wound is None:
        raise HTTPException(status_code=404, detail="Plaie introuvable")
    await get_owned_wound(wound_id, db, user)
    return _aggregate(wound)


@router.patch("/{wound_id}", response_model=WoundOut)
async def update_wound(wound_id: int, payload: WoundUpdate, user: CurrentUser, db: DbSession):
    wound = await get_owned_wound(wound_id, db, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(wound, key, value)
    await db.commit()
    wound = (
        await db.execute(
            select(Wound).options(selectinload(Wound.analyses)).where(Wound.id == wound_id)
        )
    ).scalar_one()
    return _aggregate(wound)


@router.delete("/{wound_id}", status_code=204)
async def archive_wound(wound_id: int, user: CurrentUser, db: DbSession):
    wound = await get_owned_wound(wound_id, db, user)
    wound.archived = True
    await db.commit()
    return None


@router.get("/{wound_id}/trend")
async def wound_trend(wound_id: int, user: CurrentUser, db: DbSession) -> dict[str, Any]:
    wound = await get_owned_wound(wound_id, db, user)

    rows = (
        await db.execute(
            select(WoundAnalysis)
            .where(WoundAnalysis.wound_id == wound_id)
            .order_by(WoundAnalysis.captured_at)
        )
    ).scalars().all()

    points = [
        TrajectoryPoint(
            date=r.captured_at,
            area_cm2=r.area_cm2,
            infection_risk=r.infection_risk,
            ischemia_risk=r.ischemia_risk,
            composition=r.tissue_composition or {},
        )
        for r in rows
    ]
    result = healing_trajectory(points)
    return {"wound_id": wound_id, "label": wound.label, **result}


# ---------------------------------------------------------------------------
# Espace praticien
# ---------------------------------------------------------------------------
practitioner_router = APIRouter(prefix="/practitioner", tags=["Praticien"])


@practitioner_router.get("/patients")
async def list_patients(user: Practitioner, db: DbSession):
    stmt = (
        select(User)
        .where(User.role == UserRole.patient)
        .options(selectinload(User.wounds).selectinload(Wound.analyses))
    )
    if user.role != UserRole.admin:
        stmt = stmt.where(User.referent_practitioner_id == user.id)
    patients = (await db.execute(stmt)).scalars().all()

    out = []
    for p in patients:
        analyses = sorted(
            [a for w in (p.wounds or []) for a in (w.analyses or [])],
            key=lambda a: a.captured_at,
        )
        latest = analyses[-1] if analyses else None
        out.append({
            "id": p.id,
            "full_name": p.full_name or p.email,
            "email": p.email,
            "diabetes_type": p.diabetes_type.value,
            "wounds_count": len(p.wounds or []),
            "analyses_count": len(analyses),
            "latest_area_cm2": round(latest.area_cm2, 2) if latest else None,
            "risk_level": latest.risk_level.value if latest else None,
            "infection_risk": round(latest.infection_risk, 3) if latest else None,
            "last_analysis_at": latest.captured_at.isoformat() if latest else None,
            "pending_reviews": sum(1 for a in analyses if not a.doctor_validated),
        })
    order = {"high": 0, "moderate": 1, "low": 2, None: 3}
    out.sort(key=lambda x: (order.get(x["risk_level"], 3), -(x["latest_area_cm2"] or 0)))
    return {"count": len(out), "patients": out}


@practitioner_router.get("/pending")
async def pending_reviews(user: Practitioner, db: DbSession):
    stmt = (
        select(WoundAnalysis)
        .join(User, User.id == WoundAnalysis.owner_id)
        .where(WoundAnalysis.doctor_validated.is_(False))
    )
    if user.role != UserRole.admin:
        stmt = stmt.where(User.referent_practitioner_id == user.id)
    rows = (
        await db.execute(
            stmt
            .order_by(WoundAnalysis.infection_risk.desc())
            .limit(50)
        )
    ).scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "analysis_id": r.id,
                "wound_id": r.wound_id,
                "patient_id": r.owner_id,
                "risk_level": r.risk_level.value,
                "infection_risk": round(r.infection_risk, 3),
                "area_cm2": round(r.area_cm2, 2),
                "captured_at": r.captured_at.isoformat(),
            }
            for r in rows
        ],
    }
