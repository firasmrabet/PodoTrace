"""Authentification : inscription, OTP email, login, Google, profil."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, audit
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_otp,
    hash_otp,
    hash_password,
    password_strength,
    verify_otp,
    verify_password,
)
from app.models.entities import (
    DiabetesType,
    OtpCode,
    PractitionerSpecialty,
    User,
    UserRole,
)
from app.schemas.schemas import (
    GoogleLoginRequest,
    LoginRequest,
    OtpIssued,
    ProfileUpdate,
    RegisterRequest,
    TokenResponse,
    UserOut,
    VerifyOtpRequest,
)
from app.services.mailer import send_otp_email

router = APIRouter(prefix="/auth", tags=["Authentification"])


def _token_response(user: User, dev_otp: str | None = None) -> TokenResponse:
    token = create_access_token(
        str(user.id), {"role": user.role.value, "email": user.email}
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
        dev_otp=dev_otp,
    )


async def _issue_otp(db: DbSession, user: User, purpose: str = "email_verification") -> str:
    code = generate_otp()
    db.add(
        OtpCode(
            user_id=user.id,
            code_hash=hash_otp(code),
            purpose=purpose,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.OTP_TTL_MINUTES),
        )
    )
    await db.flush()
    await send_otp_email(user.email, code, user.full_name)
    return code


@router.post("/register", response_model=OtpIssued, status_code=201)
async def register(payload: RegisterRequest, db: DbSession, request: Request):
    existing = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cette adresse email.",
        )
    strong, issues = password_strength(payload.password)
    if not strong:
        raise HTTPException(
            status_code=422,
            detail="Mot de passe trop faible : il manque " + ", ".join(issues) + ".",
        )

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name or payload.email.split("@")[0],
        hashed_password=hash_password(payload.password),
        role=UserRole(payload.role),
        specialty=PractitionerSpecialty(payload.specialty) if payload.specialty else None,
        diabetes_type=DiabetesType(payload.diabetes_type),
        birth_year=payload.birth_year,
        locale=payload.locale,
        consent_accepted=payload.consent_accepted,
        consent_accepted_at=datetime.now(timezone.utc) if payload.consent_accepted else None,
    )
    db.add(user)
    await db.flush()
    code = await _issue_otp(db, user)
    await audit(db, request, "auth.register", user.id, f"user:{user.id}")
    await db.commit()

    return OtpIssued(
        message="Compte créé. Un code de vérification à 6 chiffres vous a été envoyé.",
        email=user.email,
        expires_in_minutes=settings.OTP_TTL_MINUTES,
        dev_otp=code if settings.EXPOSE_OTP_IN_RESPONSE else None,
    )


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_email(payload: VerifyOtpRequest, db: DbSession, request: Request):
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    otp = (
        await db.execute(
            select(OtpCode)
            .where(OtpCode.user_id == user.id, OtpCode.consumed.is_(False))
            .order_by(OtpCode.created_at.desc())
        )
    ).scalars().first()
    if not otp or otp.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400, detail="Code expiré ou inexistant. Demandez un nouveau code."
        )
    if not verify_otp(payload.code.strip(), otp.code_hash):
        raise HTTPException(status_code=400, detail="Code de vérification incorrect.")

    otp.consumed = True
    user.email_verified = True
    await audit(db, request, "auth.verify_otp", user.id, f"user:{user.id}")
    await db.commit()
    await db.refresh(user)
    return _token_response(user)


@router.post("/resend-otp", response_model=OtpIssued)
async def resend_otp(payload: VerifyOtpRequest, db: DbSession):
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    if user.email_verified:
        return OtpIssued(
            message="Adresse email déjà vérifiée.",
            email=user.email,
            expires_in_minutes=0,
        )
    code = await _issue_otp(db, user)
    await db.commit()
    return OtpIssued(
        message="Nouveau code envoyé.",
        email=user.email,
        expires_in_minutes=settings.OTP_TTL_MINUTES,
        dev_otp=code if settings.EXPOSE_OTP_IN_RESPONSE else None,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DbSession, request: Request):
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if not user or not user.hashed_password or not verify_password(
        payload.password, user.hashed_password
    ):
        await audit(db, request, "auth.login_failed", user.id if user else None, payload.email)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )
    if not user.email_verified:
        code = await _issue_otp(db, user)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "email_not_verified",
                "message": "Adresse email non vérifiée : saisissez le code reçu.",
                "dev_otp": code if settings.EXPOSE_OTP_IN_RESPONSE else None,
            },
        )
    await audit(db, request, "auth.login", user.id, f"user:{user.id}")
    await db.commit()
    await db.refresh(user)
    return _token_response(user)


@router.post("/google", response_model=TokenResponse)
async def google_login(payload: GoogleLoginRequest, db: DbSession, request: Request):
    """Vérifie le jeton Google (GIS / mobile) puis crée ou rattache le compte."""
    claims: dict = {}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                "https://oauth2.googleapis.com/tokeninfo", params={"id_token": payload.id_token}
            )
            if r.status_code == 200:
                claims = r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[PodoTrace][Google] Vérification impossible : {exc}")

    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de vérifier l'identité Google pour le moment.",
        )
    if claims.get("email_verified") not in (True, "true", "1"):
        raise HTTPException(status_code=401, detail="Adresse Google non vérifiée.")
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status_code=401, detail="Jeton Google non valide.")
    if settings.GOOGLE_CLIENT_ID and claims.get("aud") not in (None, settings.GOOGLE_CLIENT_ID):
        raise HTTPException(status_code=401, detail="Jeton Google destiné à une autre application.")

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            full_name=claims.get("name", email.split("@")[0]),
            role=UserRole.patient,
            google_sub=claims.get("sub"),
            email_verified=True,
            consent_accepted=True,
            consent_accepted_at=datetime.now(timezone.utc),
        )
        db.add(user)
    else:
        user.google_sub = user.google_sub or claims.get("sub")
        user.email_verified = True
    await audit(db, request, "auth.google", user.id, email)
    await db.commit()
    await db.refresh(user)
    return _token_response(user)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(payload: ProfileUpdate, user: CurrentUser, db: DbSession):
    data = payload.model_dump(exclude_unset=True)
    if "diabetes_type" in data and data["diabetes_type"]:
        data["diabetes_type"] = DiabetesType(data["diabetes_type"])
    for key, value in data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)
