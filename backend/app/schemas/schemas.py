"""Schémas Pydantic v2 (contrats d'API publics)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ------------------------------ Auth ---------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=160)
    role: Literal["patient", "practitioner"] = "patient"
    specialty: Optional[
        Literal["physician", "podiatrist", "nurse", "diabetologist", "other"]
    ] = None
    diabetes_type: Literal["type_1", "type_2", "gestational", "other", "none"] = "none"
    birth_year: Optional[int] = Field(default=None, ge=1900, le=2026)
    locale: str = "fr"
    consent_accepted: bool = False

    @field_validator("consent_accepted")
    @classmethod
    def _consent_required(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Le consentement éclairé (RGPD / SaMD) est obligatoire.")
        return v


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"
    dev_otp: Optional[str] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    specialty: Optional[str] = None
    diabetes_type: str
    birth_year: Optional[int] = None
    neuropathy: bool = False
    peripheral_artery_disease: bool = False
    email_verified: bool
    consent_accepted: bool
    onboarding_done: bool
    biometric_enabled: bool
    locale: str
    created_at: datetime


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    diabetes_type: Optional[Literal["type_1", "type_2", "gestational", "other", "none"]] = None
    birth_year: Optional[int] = Field(default=None, ge=1900, le=2026)
    neuropathy: Optional[bool] = None
    peripheral_artery_disease: Optional[bool] = None
    locale: Optional[str] = None
    biometric_enabled: Optional[bool] = None
    onboarding_done: Optional[bool] = None


class OtpIssued(BaseModel):
    message: str
    email: EmailStr
    expires_in_minutes: int
    dev_otp: Optional[str] = None


# ------------------------------ Wounds -------------------------------------
class WoundCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    anatomical_site: str = Field(default="hallux", max_length=64)
    foot_side: Literal["left", "right"] = "right"
    wagner_grade: Optional[int] = Field(default=None, ge=0, le=5)
    texas_class: Optional[str] = None


class WoundUpdate(BaseModel):
    label: Optional[str] = None
    anatomical_site: Optional[str] = None
    wagner_grade: Optional[int] = Field(default=None, ge=0, le=5)
    texas_class: Optional[str] = None
    archived: Optional[bool] = None


class WoundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    label: str
    anatomical_site: str
    foot_side: str
    wagner_grade: Optional[int]
    texas_class: Optional[str]
    created_at: datetime
    archived: bool
    # Agrégats (calculés par l'API)
    latest_area_cm2: Optional[float] = None
    latest_risk_level: Optional[str] = None
    latest_infection_risk: Optional[float] = None
    analysis_count: int = 0
    trend_pct: Optional[float] = None
    sparkline: list[float] = Field(default_factory=list)


# ------------------------------ Analysis -----------------------------------
class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wound_id: int
    area_cm2: float
    perimeter_cm: float
    pixels_per_cm: float
    calibration_method: str
    tissue_composition: dict[str, Any]
    infection_risk: float
    ischemia_risk: float
    uncertainty: float
    risk_level: str
    risk_factors: list[dict[str, Any]]
    quality_score: float
    explainability: dict[str, Any]
    engine: str
    recommendations: list[str]
    push_score: Optional[int]
    doctor_notes: Optional[str] = None
    doctor_validated: bool = False
    doctor_override_level: Optional[str] = None
    dressing_prescription: Optional[str] = None
    captured_at: datetime
    processing_ms: int


class FullAnalysisResponse(BaseModel):
    analysis: AnalysisOut
    images: dict[str, str]
    metrics: dict[str, Any]
    tissues: dict[str, Any]
    risk: dict[str, Any]
    quality: dict[str, Any]
    calibration: dict[str, Any]
    explainability: dict[str, Any]
    recommendations: list[str]
    disclaimer: str
    processing_ms: int


class DoctorReview(BaseModel):
    doctor_notes: Optional[str] = None
    doctor_override_level: Optional[Literal["low", "moderate", "high"]] = None
    dressing_prescription: Optional[str] = None
    validate_review: bool = Field(default=True, alias="validate")

    model_config = ConfigDict(populate_by_name=True)


class TrendResponse(BaseModel):
    wound_id: int
    label: str
    status: str
    label_status: str
    reduction_pct: float
    weeks_followed: float
    rate_cm2_per_week: float
    push_score: int
    gilman_index: float
    alerts: list[str]
    series: list[dict[str, Any]]


class DashboardStats(BaseModel):
    active_wounds: int
    total_analyses: int
    last_area_cm2: Optional[float]
    trend_pct: Optional[float]
    global_status: Literal["stable", "improving", "alert", "no_data"]
    banner_message: str
    critical_wounds: int
    next_follow_up_days: Optional[int] = None


# ------------------------------ Chat ---------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    wound_id: Optional[int] = None
    locale: str = "fr"


class ChatResponse(BaseModel):
    reply: str
    red_flag: bool
    red_flag_terms: list[str] = Field(default_factory=list)
    emergency_message: Optional[str] = None
    sources: list[str] = Field(default_factory=list)
    provider: str = "heuristic"
    suggestions: list[str] = Field(default_factory=list)


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    red_flag: bool
    sources: list[str]
    created_at: datetime


# ------------------------------ Geo ----------------------------------------
class PlaceOut(BaseModel):
    id: str
    name: str
    category: str
    category_label: str
    lat: float
    lon: float
    distance_km: float
    address: Optional[str] = None
    phone: Optional[str] = None
    opening_hours: Optional[str] = None
    emergency_24_7: bool = False
    website: Optional[str] = None


class GeoSearchResponse(BaseModel):
    origin: dict[str, float]
    radius_km: float
    count: int
    source: str
    places: list[PlaceOut]
