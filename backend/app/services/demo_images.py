"""Génération d'images de plaie synthétiques — jeu de démonstration.

Aucune dépendance à un jeu de données externe : les images sont calculées
localement (peau texturée, halo d'érythème, berges épithélialisées, lit de
granulation, plages de fibrine et de nécrose, gommette verte de calibration).

Le rendu vise la **plausibilité clinique** (et non la photoréalité absolue) afin
que la segmentation, la planimétrie et la colorimétrie produites par le moteur
aient un comportement comparable à celui obtenu sur une vraie photographie.

Ces images servent uniquement à amorcer une base de démonstration et à permettre
un test de bout en bout sans caméra.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageFilter


# ---------------------------------------------------------------------------
# Bruit de valeur multi-échelles (aspect « peau » sans dépendance externe)
# ---------------------------------------------------------------------------
def _value_noise(rng: np.random.Generator, size: int, cells: int) -> np.ndarray:
    """Bruit lissé 0..1 par interpolation bilinéaire d'une grille aléatoire."""
    grid = rng.random((cells + 1, cells + 1)).astype(np.float32)
    img = Image.fromarray((grid * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def _fbm(rng: np.random.Generator, size: int, octaves=(6, 14, 34, 80)) -> np.ndarray:
    """Somme pondérée d'échelles de bruit → texture organique."""
    acc = np.zeros((size, size), np.float32)
    weight = 1.0
    total = 0.0
    for cells in octaves:
        acc += _value_noise(rng, size, cells) * weight
        total += weight
        weight *= 0.55
    out = acc / total
    out -= out.min()
    out /= out.max() + 1e-8
    return out


def _blob(rng: np.random.Generator, size: int, cells: int = 4) -> np.ndarray:
    """Champ de blobs 0..1 : permet des plages tissulaires contiguës."""
    field = _fbm(rng, size, octaves=(3, 7, 13))
    field = field * 0.75 + _value_noise(rng, size, cells) * 0.25
    field -= field.min()
    field /= field.max() + 1e-8
    return field


def _smooth(mask: np.ndarray, size: int, sigma_ratio: float) -> np.ndarray:
    """Adoucit un masque 0..1 (rayon proportionnel à la taille de l'image)."""
    if mask.max() <= 0:
        return mask
    pil = Image.fromarray(np.clip(mask * 255, 0, 255).astype(np.uint8))
    pil = pil.filter(ImageFilter.GaussianBlur(max(1.0, size * sigma_ratio)))
    return np.asarray(pil, np.float32) / 255.0


def _smoothstep(field: np.ndarray, lo: float, hi: float) -> np.ndarray:
    x = np.clip((field - lo) / max(1e-6, hi - lo), 0, 1)
    return x * x * (3 - 2 * x)


def make_wound_image(
    *,
    size: int = 900,
    fibrin: float = 0.32,
    necrosis: float = 0.10,
    green_dot_diameter_cm: float = 2.0,
    pixels_per_cm: float = 40.0,
    radius_scale: float = 1.0,
    mirror: bool = False,
    seed: int = 7,
) -> bytes:
    """Retourne les octets JPEG d'une plaie synthétique calibrée."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)

    # ── 1. Peau : teinte chaude, mottling basse fréquence, rides, vignettage ──
    base = np.array([146, 168, 202], np.float32)          # BGR ≈ peau claire
    mottle = (_fbm(rng, size, (5, 11, 26)) - 0.5)
    pores = (_fbm(rng, size, (40, 90)) - 0.5)
    skin = np.empty((size, size, 3), np.float32)
    skin[..., 0] = base[0] + mottle * 26 + pores * 12          # B
    skin[..., 1] = base[1] + mottle * 22 + pores * 10          # G
    skin[..., 2] = base[2] + mottle * 18 + pores * 8           # R

    # rides plantaires (arcs sinueux) — très légères
    creases = np.zeros((size, size), np.float32)
    ang = rng.uniform(0, np.pi)
    freq = rng.uniform(2.2, 4.0)
    phase = rng.uniform(0, 6.28)
    wave = np.sin((xx * np.cos(ang) + yy * np.sin(ang)) / size * 6.28 * freq
                  + np.sin(yy / size * 6.28 * 1.7 + phase) * 1.4)
    creases += np.clip(wave - 0.86, 0, 1) * 16
    for _ in range(3):
        a2 = rng.uniform(0, np.pi)
        f2 = rng.uniform(3.0, 6.0)
        w2 = np.sin((xx * np.cos(a2) + yy * np.sin(a2)) / size * 6.28 * f2 + rng.uniform(0, 6.28))
        creases += np.clip(w2 - 0.9, 0, 1) * 12
    creases = np.asarray(
        Image.fromarray(np.clip(creases, 0, 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(1.2)), np.float32)
    skin -= creases[..., None] * np.array([0.9, 1.0, 1.1], np.float32)

    # vignettage doux + lumière directionnelle
    nx, ny = xx / size - 0.5, yy / size - 0.5
    vign = 1.0 - 0.22 * np.sqrt(nx ** 2 + ny ** 2)
    light = 1.0 + 0.10 * (-nx * 0.6 - ny * 0.8)
    skin *= (vign * light)[..., None]

    # ── 2. Plaie : contour irrégulier, érythème, berge, lit, plages tissulaires
    cx = size * (0.63 if mirror else 0.44)
    cy = size * 0.52
    r_outer = size * 0.155 * radius_scale

    theta = np.arctan2(yy - cy, xx - cx)
    wobble = np.zeros_like(theta)
    for k, amp in ((2, 0.14), (3, 0.10), (5, 0.07), (8, 0.04), (13, 0.022)):
        wobble += amp * np.sin(k * theta + rng.uniform(0, 6.28))
    r_field = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (1.0 + wobble)
    t = r_field / r_outer                                   # 0 au centre, 1 au bord

    # halo d'érythème péri-lésionnel (rougeur diffuse)
    halo = np.clip(1.0 - (t - 1.0) / 0.85, 0, 1) ** 1.6
    halo = np.where(t > 1.0, halo, 0.0)
    skin += np.asarray(
        Image.fromarray((halo * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(size * 0.02)),
        np.float32)[..., None] / 255.0 * np.array([-26, -34, -8], np.float32)

    bed = t < 0.84
    bed_soft = _smooth(bed.astype(np.float32), size, 0.010)

    # plages tissulaires : granulation par défaut, fibrine et nécrose en nappes
    # aux bords organiques (fondu progressif, pas de seuil net).
    f_field = _blob(rng, size, 4)
    n_field = _blob(rng, size, 3)
    fb = np.quantile(f_field[bed], min(0.985, max(0.0, 1.0 - fibrin)))
    nb = np.quantile(n_field[bed], min(0.99, max(0.0, 1.0 - necrosis)))
    a_fibrin = _smoothstep(f_field, fb - 0.04, fb + 0.04) * bed_soft
    a_necro = _smoothstep(n_field, nb - 0.04, nb + 0.04) * bed_soft * (1.0 - a_fibrin * 0.85)

    gran_tex = (_fbm(rng, size, (24, 56, 130)) - 0.5)
    speck = np.clip((_fbm(rng, size, (90, 190)) - 0.60) * 3.0, 0, 1)
    gran = np.empty((size, size, 3), np.float32)
    gran[..., 0] = 58 + gran_tex * 30 + speck * 46
    gran[..., 1] = 54 + gran_tex * 26 + speck * 40
    gran[..., 2] = 168 + gran_tex * 24 + speck * 30

    fibr_tex = (_fbm(rng, size, (20, 48, 110)) - 0.5)
    fibr = np.empty((size, size, 3), np.float32)
    fibr[..., 0] = 164 + fibr_tex * 26
    fibr[..., 1] = 196 + fibr_tex * 22
    fibr[..., 2] = 224 + fibr_tex * 18

    necr_tex = (_fbm(rng, size, (16, 40)) - 0.5)
    necr = np.empty((size, size, 3), np.float32)
    necr[..., 0] = 48 + necr_tex * 18
    necr[..., 1] = 42 + necr_tex * 14
    necr[..., 2] = 46 + necr_tex * 14

    depth = (0.80 + 0.28 * np.clip(t, 0, 1))[..., None]      # lit plus sombre au centre

    bed_a = bed_soft[..., None]
    fib_a = a_fibrin[..., None]
    nec_a = a_necro[..., None]
    skin = skin * (1 - bed_a) + gran * depth * bed_a
    skin = skin * (1 - fib_a) + fibr * depth * fib_a
    skin = skin * (1 - nec_a) + necr * depth * nec_a

    # berge épithélialisée : anneau interne rosé (fermeture depuis les bords)
    epi_band = np.clip((t - 0.56) / 0.10, 0, 1) * np.clip((0.88 - t) / 0.08, 0, 1)
    epi_a = _smooth(epi_band, size, 0.006)[..., None]
    epi_tex = (_fbm(rng, size, (22, 52)) - 0.5)
    epi = np.empty((size, size, 3), np.float32)
    epi[..., 0] = 172 + epi_tex * 18       # B
    epi[..., 1] = 168 + epi_tex * 16       # G
    epi[..., 2] = 216 + epi_tex * 14       # R  → L≈73, a*≈18, b*≈5 (classe épithéliale)
    skin = skin * (1 - epi_a) + epi * (0.92 + 0.16 * np.clip(t, 0, 1))[..., None] * epi_a

    # bourrelet : léger sillon sombre juste à l'intérieur de la berge
    inner_shadow = np.clip((t - 0.62) / 0.16, 0, 1) * np.clip((0.90 - t) / 0.10, 0, 1)
    skin -= _smooth(inner_shadow, size, 0.008)[..., None] * 34

    img = np.clip(skin, 0, 255).astype(np.uint8)

    # ── 3. Gommette de calibration : pastille verte cerclée de blanc ─────────
    dot_r = int(pixels_per_cm * green_dot_diameter_cm / 2)
    dot_cx, dot_cy = int(size * 0.82), int(size * 0.19)
    d2 = (xx - dot_cx) ** 2 + (yy - dot_cy) ** 2
    dot = (d2 < dot_r ** 2)
    # Pas de cerclage blanc : le détecteur de gommette affine le rayon par
    # Hough et prendrait le cerclage pour la gommette (erreur d'échelle).
    shade = 1.0 - 0.07 * np.clip((yy - (dot_cy - dot_r)) / (2 * dot_r), 0, 1)
    green = np.array([68, 176, 46], np.float32)[None, :]
    img[dot] = np.clip(green * shade[dot][:, None]
                       + rng.normal(0, 4, (int(dot.sum()), 3)), 0, 255).astype(np.uint8)

    pil = Image.fromarray(img[..., ::-1]).filter(ImageFilter.GaussianBlur(radius=0.5))
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def trajectory_images(count: int = 6, *, seed: int = 11, mirror: bool = False) -> list[bytes]:
    """Série réaliste de cicatrisation : la plaie se referme mesure après mesure."""
    scales = [1.0, 0.90, 0.79, 0.66, 0.52, 0.42]
    fibrins = [0.46, 0.40, 0.33, 0.24, 0.16, 0.11]
    necroses = [0.20, 0.14, 0.08, 0.04, 0.01, 0.0]
    out: list[bytes] = []
    for i in range(min(count, len(scales))):
        out.append(
            make_wound_image(
                radius_scale=scales[i],
                fibrin=fibrins[i],
                necrosis=necroses[i],
                mirror=mirror,
                seed=seed + i,
            )
        )
    return out
