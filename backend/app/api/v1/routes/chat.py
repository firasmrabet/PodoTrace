"""Assistant médical IA (RAG IWGDF) + détection d'urgence + historique."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_owned_wound
from app.models.entities import ChatMessage, Wound, WoundAnalysis
from app.schemas.schemas import ChatMessageOut, ChatRequest, ChatResponse
from app.services.llm import answer_question, suggestions_for

router = APIRouter(prefix="/chat", tags=["Assistant IA"])


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, user: CurrentUser, db: DbSession):
    wound_ctx: Optional[dict[str, Any]] = None
    trend: Optional[str] = None

    target_wound_id = payload.wound_id
    if not target_wound_id and user.role.value == "patient":
        latest_w = (
            await db.execute(
                select(Wound)
                .where(Wound.owner_id == user.id, Wound.archived.is_(False))
                .order_by(Wound.created_at.desc())
            )
        ).scalars().first()
        if latest_w:
            target_wound_id = latest_w.id

    if target_wound_id:
        wound = await get_owned_wound(target_wound_id, db, user)
        rows = (
            await db.execute(
                select(WoundAnalysis)
                .where(WoundAnalysis.wound_id == wound.id)
                .order_by(WoundAnalysis.captured_at)
            )
        ).scalars().all()
        latest = rows[-1] if rows else None
        if len(rows) >= 2 and rows[0].area_cm2 > 0 and latest:
            delta = (rows[0].area_cm2 - latest.area_cm2) / rows[0].area_cm2 * 100
            trend = f"{delta:+.1f} % de surface depuis la première mesure"
        wound_ctx = {
            "label": wound.label,
            "anatomical_site": wound.anatomical_site,
            "foot_side": wound.foot_side,
            "wagner_grade": wound.wagner_grade,
            "area_cm2": round(latest.area_cm2, 2) if latest else None,
            "infection_risk": latest.infection_risk if latest else None,
            "ischemia_risk": latest.ischemia_risk if latest else None,
            "risk_level": latest.risk_level.value if latest else None,
            "composition": latest.tissue_composition if latest else None,
            "trend": trend,
        }

    history_query = select(ChatMessage).where(
        ChatMessage.user_id == user.id,
        ChatMessage.wound_id == target_wound_id
        if target_wound_id is not None
        else ChatMessage.wound_id.is_(None),
    )
    history_rows = (
        await db.execute(history_query.order_by(ChatMessage.created_at.desc()).limit(8))
    ).scalars().all()
    history = [
        {"role": m.role, "content": m.content} for m in reversed(history_rows)
    ]

    result = await answer_question(
        payload.message,
        wound=wound_ctx,
        user={
            "diabetes_type": user.diabetes_type.value,
            "neuropathy": user.neuropathy,
            "peripheral_artery_disease": user.peripheral_artery_disease,
        },
        history=history,
        locale=payload.locale,
    )

    db.add(ChatMessage(user_id=user.id, wound_id=target_wound_id, role="user",
                       content=payload.message, red_flag=result.red_flag))
    db.add(ChatMessage(user_id=user.id, wound_id=target_wound_id, role="assistant",
                       content=result.reply, red_flag=result.red_flag,
                       sources=result.sources))
    await db.commit()

    return ChatResponse(
        reply=result.reply,
        red_flag=result.red_flag,
        red_flag_terms=result.red_flag_terms,
        emergency_message=result.emergency_message,
        sources=result.sources,
        provider=result.provider,
        suggestions=result.suggestions,
    )


@router.get("/history", response_model=list[ChatMessageOut])
async def history(
    user: CurrentUser, db: DbSession, wound_id: Optional[int] = Query(None),
    limit: int = Query(100, le=300),
):
    stmt = select(ChatMessage).where(ChatMessage.user_id == user.id)
    if wound_id is not None:
        await get_owned_wound(wound_id, db, user)
        stmt = stmt.where(ChatMessage.wound_id == wound_id)
    else:
        stmt = stmt.where(ChatMessage.wound_id.is_(None))
    rows = (
        await db.execute(stmt.order_by(ChatMessage.created_at.desc()).limit(limit))
    ).scalars().all()
    return [ChatMessageOut.model_validate(r) for r in reversed(rows)]


@router.get("/suggestions")
async def suggestions(locale: str = "fr"):
    return {"suggestions": suggestions_for(locale)}
