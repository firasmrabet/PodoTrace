"""Modèles ORM : utilisateurs, plaies, analyses, suivi, chat, OTP."""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    patient = "patient"
    practitioner = "practitioner"
    admin = "admin"


class PractitionerSpecialty(str, enum.Enum):
    physician = "physician"
    podiatrist = "podiatrist"
    nurse = "nurse"
    diabetologist = "diabetologist"
    other = "other"


class DiabetesType(str, enum.Enum):
    type_1 = "type_1"
    type_2 = "type_2"
    gestational = "gestational"
    other = "other"
    none = "none"


class RiskLevel(str, enum.Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.patient)
    specialty: Mapped[Optional[PractitionerSpecialty]] = mapped_column(
        Enum(PractitionerSpecialty), nullable=True
    )
    locale: Mapped[str] = mapped_column(String(8), default="fr")

    # Profil clinique (patient)
    diabetes_type: Mapped[DiabetesType] = mapped_column(
        Enum(DiabetesType), default=DiabetesType.none
    )
    birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    neuropathy: Mapped[bool] = mapped_column(Boolean, default=False)
    peripheral_artery_disease: Mapped[bool] = mapped_column(Boolean, default=False)
    referent_practitioner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Conformité
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    google_sub: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    biometric_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    wounds: Mapped[list["Wound"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", foreign_keys="Wound.owner_id"
    )

    @property
    def is_practitioner(self) -> bool:
        return self.role in (UserRole.practitioner, UserRole.admin)


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(String(128))
    purpose: Mapped[str] = mapped_column(String(32), default="email_verification")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Wound(Base):
    """Une plaie suivie (localisation anatomique du pied diabétique)."""

    __tablename__ = "wounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(120))
    anatomical_site: Mapped[str] = mapped_column(String(64), default="hallux")
    foot_side: Mapped[str] = mapped_column(String(8), default="right")
    wagner_grade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    texas_class: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    owner: Mapped["User"] = relationship(back_populates="wounds", foreign_keys=[owner_id])
    analyses: Mapped[list["WoundAnalysis"]] = relationship(
        back_populates="wound",
        cascade="all, delete-orphan",
        order_by="WoundAnalysis.captured_at",
    )


class WoundAnalysis(Base):
    """Résultat complet d'un pipeline d'inférence (immuable côté patient)."""

    __tablename__ = "wound_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    wound_id: Mapped[int] = mapped_column(
        ForeignKey("wounds.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Image chiffrée au repos + dérivés (masque, heatmap) en JSON/base64
    image_key: Mapped[str] = mapped_column(String(255))
    image_sha256: Mapped[str] = mapped_column(String(64), default="")

    # Métriques quantitatives
    area_cm2: Mapped[float] = mapped_column(Float, default=0.0)
    perimeter_cm: Mapped[float] = mapped_column(Float, default=0.0)
    pixels_per_cm: Mapped[float] = mapped_column(Float, default=0.0)
    calibration_method: Mapped[str] = mapped_column(String(32), default="manual")

    # Composition tissulaire (fractions 0..1 — somme = 1)
    tissue_composition: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Risques
    infection_risk: Mapped[float] = mapped_column(Float, default=0.0)
    ischemia_risk: Mapped[float] = mapped_column(Float, default=0.0)
    uncertainty: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.low)
    risk_factors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    # Qualité image & explicabilité
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    quality_report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    explainability: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    engine: Mapped[str] = mapped_column(String(48), default="simulation-calibrated")
    recommendations: Mapped[list[str]] = mapped_column(JSON, default=list)
    push_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Human-in-the-loop praticien
    doctor_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doctor_notes_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    doctor_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    doctor_override_level: Mapped[Optional[RiskLevel]] = mapped_column(
        Enum(RiskLevel), nullable=True
    )
    dressing_prescription: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    processing_ms: Mapped[int] = mapped_column(Integer, default=0)

    wound: Mapped["Wound"] = relationship(back_populates="analyses")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    wound_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("wounds.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    red_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Traçabilité SaMD (accès aux données de santé — exigence HDS)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str] = mapped_column(String(120), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
