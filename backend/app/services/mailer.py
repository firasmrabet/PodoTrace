"""Envoi d'emails transactionnels (code OTP) — SMTP asynchrone.

En développement (SMTP_HOST vide), le code est simplement journalisé et, si
`EXPOSE_OTP_IN_RESPONSE` est actif, renvoyé par l'API pour les tests E2E.
"""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Optional

from app.core.config import settings


def _build_otp_email(to: str, code: str, full_name: str = "") -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"DiaFoot Sentinel — votre code de vérification : {code}"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.set_content(
        f"""Bonjour {full_name or ''},

Votre code de vérification DiaFoot Sentinel est :

    {code}

Il expire dans {settings.OTP_TTL_MINUTES} minutes.
Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.

— DiaFoot Sentinel
Surveillance clinique des plaies du pied diabétique.
Ce service est un outil d'aide à la décision et ne remplace pas un avis médical.
"""
    )
    msg.add_alternative(
        f"""<html><body style="font-family:Georgia,serif;background:#150C14;padding:32px">
        <div style="max-width:520px;margin:auto;background:#1E121C;border:1px solid #C9924E55;
                    border-radius:16px;padding:32px;color:#F3E9E2">
          <p style="letter-spacing:.28em;font-size:11px;color:#C9924E;margin:0 0 18px">
            DIAFOOT SENTINEL</p>
          <h1 style="font-size:24px;margin:0 0 12px">Votre code de vérification</h1>
          <p style="color:#C9B8AE;line-height:1.6">Saisissez ce code pour activer votre compte.</p>
          <div style="font-size:38px;letter-spacing:.22em;color:#E8B87F;font-weight:600;
                      padding:18px 0">{code}</div>
          <p style="color:#8C7A72;font-size:12px">Expire dans {settings.OTP_TTL_MINUTES} minutes.</p>
        </div></body></html>""",
        subtype="html",
    )
    return msg


async def send_otp_email(to: str, code: str, full_name: str = "") -> bool:
    """Retourne True si l'email a été remis au serveur SMTP."""
    if not settings.SMTP_HOST:
        print(f"[DiaFoot][MAIL-DEV] OTP pour {to} : {code}")
        return False

    msg = _build_otp_email(to, code, full_name)

    def _send() -> None:
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
                if settings.SMTP_USER:
                    s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
                s.starttls()
                if settings.SMTP_USER:
                    s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)

    try:
        await asyncio.to_thread(_send)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[DiaFoot][MAIL] Échec d'envoi à {to} : {exc}")
        return False


async def send_share_email(to: str, subject: str, body: str, attachment: Optional[bytes] = None,
                           filename: str = "rapport.pdf") -> bool:
    if not settings.SMTP_HOST:
        print(f"[DiaFoot][MAIL-DEV] Partage '{subject}' → {to} ({len(attachment or b'')} octets)")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.set_content(body)
    if attachment:
        msg.add_attachment(attachment, maintype="application", subtype="pdf", filename=filename)

    def _send() -> None:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
            s.starttls()
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)

    try:
        await asyncio.to_thread(_send)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[DiaFoot][MAIL] Échec partage : {exc}")
        return False
