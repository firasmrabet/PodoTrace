"""Génération du rapport PDF médical (ReportLab) — identité visuelle Bio-Luxe."""
from __future__ import annotations

import base64
import io
from datetime import datetime
from typing import Any, Optional

from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PLUM = colors.HexColor("#1E121C")
PLUM_DEEP = colors.HexColor("#150C14")
COPPER = colors.HexColor("#C9924E")
COPPER_LIGHT = colors.HexColor("#E8B87F")
CREAM = colors.HexColor("#F3E9E2")
MUTED = colors.HexColor("#8C7A72")
DANGER = colors.HexColor("#C0392B")
WARN = colors.HexColor("#E0A33E")
OK = colors.HexColor("#4E8C6A")

RISK_COLOR = {"low": OK, "moderate": WARN, "high": DANGER}
RISK_FR = {"low": "Faible", "moderate": "Modéré", "high": "Élevé"}
TISSUE_FR = {
    "necrosis": "Nécrose",
    "fibrin": "Fibrine",
    "granulation": "Granulation",
    "epithelial": "Épithélialisation",
}


def _styles() -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "dfTitle", parent=ss["Title"], fontName="Times-Bold", fontSize=21,
            leading=25, textColor=PLUM, spaceAfter=2, alignment=TA_LEFT,
        ),
        "brand": ParagraphStyle(
            "dfBrand", parent=ss["Normal"], fontName="Times-Roman", fontSize=8.5,
            textColor=COPPER, spaceAfter=0,
        ),
        "h2": ParagraphStyle(
            "dfH2", parent=ss["Heading2"], fontName="Times-Bold", fontSize=12.5,
            textColor=PLUM, spaceBefore=12, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "dfBody", parent=ss["Normal"], fontName="Helvetica", fontSize=8.8,
            leading=12.5, textColor=colors.HexColor("#2B2029"),
        ),
        "small": ParagraphStyle(
            "dfSmall", parent=ss["Normal"], fontName="Helvetica", fontSize=7.2,
            leading=9.6, textColor=MUTED,
        ),
        "cell": ParagraphStyle(
            "dfCell", parent=ss["Normal"], fontName="Helvetica", fontSize=7.8,
            leading=10, textColor=colors.HexColor("#2B2029"),
        ),
        "thumb_caption": ParagraphStyle(
            "dfThumb", parent=ss["Normal"], fontName="Times-Italic", fontSize=7.6,
            textColor=MUTED, alignment=TA_CENTER,
        ),
    }


def _decode_data_uri(uri: Optional[str]) -> Optional[io.BytesIO]:
    if not uri or not uri.startswith("data:image"):
        return None
    try:
        payload = base64.b64decode(uri.split(",", 1)[1])
        return io.BytesIO(payload)
    except Exception:  # noqa: BLE001
        return None


def _sparkline(series: list[dict[str, Any]], width: float = 480, height: float = 90) -> Drawing:
    """Courbe d'évolution de la surface (cm²) dessinée nativement."""
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#FBF7F3"),
               strokeColor=colors.HexColor("#E7DCD2"), strokeWidth=0.6))
    if len(series) < 2:
        d.add(String(width / 2 - 70, height / 2, "Historique insuffisant pour tracer une courbe",
                     fontName="Helvetica-Oblique", fontSize=7.5, fillColor=MUTED))
        return d

    areas = [float(s.get("area_cm2", 0)) for s in series]
    amax, amin = max(areas) or 1, min(areas)
    span = max(amax - amin, 0.5)
    pad = 12
    pts: list[float] = []
    for i, a in enumerate(areas):
        x = pad + (width - 2 * pad) * i / (len(areas) - 1)
        y = pad + (height - 2 * pad) * (a - amin) / span
        pts.extend([x, y])

    d.add(Line(pad, pad, width - pad, pad, strokeColor=colors.HexColor("#E0D3C8"), strokeWidth=0.5))
    d.add(PolyLine(pts, strokeColor=COPPER, strokeWidth=1.9, strokeLineJoin=1))
    for i in range(0, len(pts), 2):
        d.add(Rect(pts[i] - 1.6, pts[i + 1] - 1.6, 3.2, 3.2, fillColor=PLUM, strokeColor=None))
    d.add(String(pad, height - 10, f"Surface (cm²) — max {amax:.2f}", fontName="Helvetica",
                fontSize=6.8, fillColor=MUTED))
    d.add(String(width - pad - 60, 2.5, f"dernière : {areas[-1]:.2f} cm²", fontName="Helvetica",
                fontSize=6.8, fillColor=COPPER))
    return d


def _header_footer(canvas, doc, meta: dict[str, Any]) -> None:
    canvas.saveState()
    w, h = A4
    # Bandeau supérieur prune
    canvas.setFillColor(PLUM_DEEP)
    canvas.rect(0, h - 26 * mm, w, 26 * mm, stroke=0, fill=1)
    canvas.setFillColor(COPPER)
    canvas.rect(0, h - 27.2 * mm, w, 1.2 * mm, stroke=0, fill=1)
    # Monogramme
    canvas.setFillColor(COPPER)
    canvas.circle(20 * mm, h - 13 * mm, 6.2 * mm, stroke=0, fill=1)
    canvas.setFillColor(PLUM_DEEP)
    canvas.setFont("Times-Bold", 12)
    canvas.drawCentredString(20 * mm, h - 15 * mm, "DF")
    # Titres
    canvas.setFillColor(CREAM)
    canvas.setFont("Times-Bold", 15)
    canvas.drawString(30 * mm, h - 11.6 * mm, "DiaFoot Sentinel")
    canvas.setFont("Helvetica", 6.8)
    canvas.setFillColor(COPPER_LIGHT)
    canvas.drawString(30 * mm, h - 15.4 * mm,
                      "RAPPORT DE TÉLÉSURVEILLANCE  ·  ULCÈRE DU PIED DIABÉTIQUE")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#B9A79E"))
    canvas.drawRightString(w - 14 * mm, h - 11.6 * mm,
                           datetime.now().strftime("Émis le %d/%m/%Y à %H:%M").encode(
                               "latin-1", "replace").decode("latin-1"))
    canvas.drawRightString(w - 14 * mm, h - 15.4 * mm, f"Réf. {meta.get('ref', '—')}")

    # Pied de page
    canvas.setStrokeColor(colors.HexColor("#E7DCD2"))
    canvas.setLineWidth(0.5)
    canvas.line(14 * mm, 16 * mm, w - 14 * mm, 16 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.2)
    canvas.drawString(14 * mm, 11.5 * mm,
                      "Document d'aide en phase de validation clinique — ne constitue pas un diagnostic. "
                      "Données de santé chiffrées au repos.")
    canvas.drawString(14 * mm, 8 * mm,
                      "DiaFoot Sentinel v1.0 · Conforme RGPD / référentiel HDS · IWGDF 2023")
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(PLUM)
    canvas.drawRightString(w - 14 * mm, 9.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_report(
    *,
    patient: dict[str, Any],
    practitioner: Optional[dict[str, Any]],
    wound: dict[str, Any],
    analyses: list[dict[str, Any]],
    images: Optional[dict[str, str]] = None,
    trajectory: Optional[dict[str, Any]] = None,
    observations: Optional[str] = None,
) -> bytes:
    """Construit le PDF complet et retourne les octets."""
    st = _styles()
    buf = io.BytesIO()
    meta = {"ref": f"DFS-{wound.get('id', 0):04d}-{datetime.now():%Y%m%d%H%M}"}
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=32 * mm, bottomMargin=20 * mm,
        title=f"Rapport DiaFoot Sentinel — {wound.get('label', 'Plaie')}",
        author="DiaFoot Sentinel",
    )
    story: list[Any] = []
    latest = analyses[-1] if analyses else {}
    level = latest.get("risk_level", "low")

    # --- Bloc identité -----------------------------------------------------
    story.append(Paragraph("Rapport clinique de suivi", st["title"]))
    story.append(Paragraph(
        f"Plaie « {wound.get('label', '—')} » · pied {wound.get('foot_side', '—')} · "
        f"{wound.get('anatomical_site', '—')} · Wagner {wound.get('wagner_grade', '—')}",
        st["brand"]))
    story.append(Spacer(1, 7))

    ident = [
        [
            Paragraph("<b>Patient</b>", st["cell"]), Paragraph(patient.get("full_name") or "—", st["cell"]),
            Paragraph("<b>Praticien référent</b>", st["cell"]),
            Paragraph((practitioner or {}).get("full_name") or "Non renseigné", st["cell"]),
        ],
        [
            Paragraph("<b>Type de diabète</b>", st["cell"]),
            Paragraph(str(patient.get("diabetes_type", "—")).replace("_", " ").title(), st["cell"]),
            Paragraph("<b>Neuropathie / AOMI</b>", st["cell"]),
            Paragraph(
                f"{'Oui' if patient.get('neuropathy') else 'Non'} / "
                f"{'Oui' if patient.get('peripheral_artery_disease') else 'Non'}",
                st["cell"]),
        ],
        [
            Paragraph("<b>Analyses</b>", st["cell"]),
            Paragraph(f"{len(analyses)} au total", st["cell"]),
            Paragraph("<b>Niveau de risque actuel</b>", st["cell"]),
            Paragraph(
                f"<font color='{RISK_COLOR.get(level, OK).hexval()}'><b>"
                f"{RISK_FR.get(level, level)}</b></font>",
                st["cell"]),
        ],
    ]
    t = Table(ident, colWidths=[30 * mm, 50 * mm, 36 * mm, 66 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBF7F3")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#E7DCD2")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#EFE6DD")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    # --- Synthèse ----------------------------------------------------------
    story.append(Paragraph("Synthèse clinique", st["h2"]))
    synth = (
        f"Dernière mesure : <b>{latest.get('area_cm2', '—')} cm²</b>, périmètre "
        f"{latest.get('perimeter_cm', '—')} cm. Risque infectieux "
        f"<b>{float(latest.get('infection_risk', 0)):.0%}</b>, risque ischémique "
        f"<b>{float(latest.get('ischemia_risk', 0)):.0%}</b> "
        f"(incertitude du modèle ±{float(latest.get('uncertainty', 0)):.2f})."
    )
    if trajectory:
        synth += (
            f"<br/><br/>Trajectoire : <b>{trajectory.get('label', '—')}</b> — réduction de "
            f"{trajectory.get('reduction_pct', 0):.1f} % sur "
            f"{trajectory.get('weeks_followed', 0):.1f} semaines "
            f"({trajectory.get('rate_cm2_per_week', 0):+.2f} cm²/semaine), "
            f"score PUSH estimé {trajectory.get('push_score', '—')}/17."
        )
    story.append(Paragraph(synth, st["body"]))

    # --- Tableau chronologique --------------------------------------------
    story.append(Paragraph("Mesures chronologiques", st["h2"]))
    head = ["Date", "Surface (cm²)", "Périmètre (cm)", "Infectieux", "Ischémique",
            "Nécrose", "Fibrine", "Granulation", "Épith."]
    rows = [head]
    for a in analyses[-12:]:
        comp = a.get("tissue_composition") or {}
        rows.append([
            str(a.get("captured_at", ""))[:10],
            f"{float(a.get('area_cm2', 0)):.2f}",
            f"{float(a.get('perimeter_cm', 0)):.2f}",
            f"{float(a.get('infection_risk', 0)):.0%}",
            f"{float(a.get('ischemia_risk', 0)):.0%}",
            f"{comp.get('necrosis', 0)*100:.0f}%",
            f"{comp.get('fibrin', 0)*100:.0f}%",
            f"{comp.get('granulation', 0)*100:.0f}%",
            f"{comp.get('epithelial', 0)*100:.0f}%",
        ])
    if len(rows) == 1:
        rows.append(["—"] * len(head))
    tbl = Table(rows, colWidths=[19 * mm, 19 * mm, 18 * mm, 16 * mm, 16 * mm,
                                 14 * mm, 14 * mm, 18 * mm, 12 * mm], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), PLUM),
        ("TEXTCOLOR", (0, 0), (-1, 0), CREAM),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.2),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.0),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E7DCD2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBF7F3")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    tbl.setStyle(TableStyle(style))
    story.append(tbl)

    # --- Courbe ------------------------------------------------------------
    if trajectory and trajectory.get("series"):
        story.append(Paragraph("Évolution de la surface", st["h2"]))
        story.append(_sparkline(trajectory["series"]))

    # --- Comparaison visuelle ---------------------------------------------
    imgs = images or {}
    if imgs.get("initial") or imgs.get("current"):
        cells, caps = [], []
        for key, label in (("initial", "Photo initiale"), ("current", "Photo actuelle"),
                           ("segmentation", "Segmentation tissulaire")):
            bio = _decode_data_uri(imgs.get(key))
            if bio is None:
                cells.append(Paragraph("—", st["cell"]))
            else:
                cells.append(RLImage(bio, width=50 * mm, height=50 * mm, kind="bound"))
            caps.append(Paragraph(label, st["thumb_caption"]))
        cmp_tbl = Table([cells, caps], colWidths=[56 * mm] * 3)
        cmp_tbl.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, 0), 0.5, colors.HexColor("#E7DCD2")),
        ]))
        story.append(KeepTogether([
            Paragraph("Comparaison photographique", st["h2"]), cmp_tbl
        ]))

    # --- Facteurs & recommandations ---------------------------------------
    factors = latest.get("risk_factors") or []
    recos = latest.get("recommendations") or []
    if factors or recos:
        story.append(Paragraph("Points d'attention et conduite à tenir", st["h2"]))
        for f in factors[:6]:
            color = {"critical": DANGER, "warning": WARN, "positive": OK}.get(
                f.get("severity", "warning"), WARN)
            story.append(Paragraph(
                f"<font color='{color.hexval()}'>■</font> <b>{f.get('label', '')}</b> — "
                f"{f.get('detail', '')}", st["body"]))
        if recos:
            story.append(Spacer(1, 5))
            for i, r in enumerate(recos[:6], 1):
                story.append(Paragraph(f"{i}. {r}", st["body"]))

    # --- Observations praticien + signature -------------------------------
    story.append(Paragraph("Observations du praticien", st["h2"]))
    obs = observations or latest.get("doctor_notes") or " "
    box = Table(
        [[Paragraph(obs.replace("\n", "<br/>")[:1400], st["body"])]],
        colWidths=[182 * mm], rowHeights=[26 * mm],
    )
    box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D9CCC1")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFDFB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(box)
    story.append(Spacer(1, 8))

    sig = Table(
        [[Paragraph("Cachet et signature du praticien", st["small"]), ""]],
        colWidths=[92 * mm, 90 * mm], rowHeights=[20 * mm],
    )
    sig.setStyle(TableStyle([
        ("BOX", (0, 0), (0, 0), 0.6, colors.HexColor("#D9CCC1")),
        ("BOX", (1, 0), (1, 0), 0.6, colors.HexColor("#D9CCC1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(sig)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Avertissement réglementaire — DiaFoot Sentinel est un logiciel d'aide à la décision "
        "médicale en phase de validation clinique. Les scores produits par l'IA ne constituent ni un "
        "diagnostic ni une prescription. Toute décision thérapeutique relève du jugement "
        "clinique du professionnel de santé. En cas de signes généraux (fièvre, altération "
        "de l'état général) ou d'aggravation locale rapide, contactez immédiatement les "
        "urgences (15 / 190).", st["small"]))

    doc.build(
        story,
        onFirstPage=lambda c, d: _header_footer(c, d, meta),
        onLaterPages=lambda c, d: _header_footer(c, d, meta),
    )
    return buf.getvalue()
