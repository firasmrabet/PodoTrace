"""Dépendances FastAPI : session DB, utilisateur courant, contrôle d'accès."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.entities import AuditLog, User, UserRole, Wound

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)] = None,
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton d'authentification manquant",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(creds.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_user_from_header_or_query(
    db: DbSession,
    request: Request,
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)] = None,
) -> User:
    """Authentification souple pour les ressources chargées par `<img>`.

    Un élément `<img src="...">` ne peut pas porter d'en-tête `Authorization` :
    le jeton peut donc être fourni en paramètre `?token=`. Il reste vérifié
    exactement comme un jeton d'en-tête, et l'accès au fichier est contrôlé.
    """
    raw = creds.credentials if (creds and creds.credentials) else request.query_params.get("token")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton d'authentification manquant",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(raw)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user


ImageUser = Annotated[User, Depends(get_user_from_header_or_query)]


async def get_verified_user(user: CurrentUser) -> User:
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adresse email non vérifiée : validez le code OTP reçu.",
        )
    return user


VerifiedUser = Annotated[User, Depends(get_verified_user)]


async def require_practitioner(user: CurrentUser) -> User:
    if user.role not in (UserRole.practitioner, UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Espace réservé aux professionnels de santé.",
        )
    return user


Practitioner = Annotated[User, Depends(require_practitioner)]


async def get_owned_wound(wound_id: int, db: DbSession, user: CurrentUser) -> Wound:
    """Un praticien accède aux dossiers de ses patients ; un patient au sien."""
    wound = await db.get(Wound, wound_id)
    if wound is None:
        raise HTTPException(status_code=404, detail="Plaie introuvable")
    if wound.owner_id == user.id:
        return wound
    if user.role == UserRole.admin:
        return wound
    if user.role == UserRole.practitioner:
        owner = await db.get(User, wound.owner_id)
        if owner and owner.referent_practitioner_id == user.id:
            return wound
    raise HTTPException(status_code=403, detail="Accès non autorisé à cette plaie")


async def audit(
    db: AsyncSession, request: Request, action: str, user_id: Optional[int] = None,
    resource: str = "", meta: Optional[dict] = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            ip=request.client.host if request.client else "",
            meta=meta or {},
        )
    )
