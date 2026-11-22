"""Recherche géolocalisée des soins via OpenStreetMap / Overpass API.

Aucune clé API payante (contrairement à Google Maps). En cas d'indisponibilité
réseau, un jeu de données local (Grand Tunis) garantit un parcours fonctionnel
hors ligne — indispensable en démonstration et en zone à faible connectivité.
"""
from __future__ import annotations

import math
import time
from typing import Any, Optional

import httpx

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

CATEGORY_LABELS: dict[str, str] = {
    "hospital": "Hôpital",
    "clinic": "Clinique",
    "wound_center": "Centre plaies & cicatrisation",
    "podiatrist": "Podologue",
    "diabetologist": "Diabétologue",
    "pharmacy": "Pharmacie",
    "emergency": "Urgences",
}

EMERGENCY_VALUES = {"yes", "24/7", "24h", "emergency"}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 3)


def _classify(tags: dict[str, str]) -> Optional[str]:
    healthcare = tags.get("healthcare", "")
    amenity = tags.get("amenity", "")
    speciality = tags.get("healthcare:speciality", "") + " " + tags.get("speciality", "")
    name = (tags.get("name", "") + " " + tags.get("name:fr", "")).lower()

    if any(k in speciality.lower() or k in name for k in ("podolog", "podiatr", "pédicure", "pedicure")):
        return "podiatrist"
    if "diabet" in speciality.lower() or "diabétolog" in name or "diabetolog" in name:
        return "diabetologist"
    if any(k in name for k in ("plaie", "cicatris", "wound", "ulcère", "ulcere")):
        return "wound_center"
    if healthcare in {"hospital"} or amenity == "hospital":
        return "hospital"
    if healthcare in {"clinic"} or amenity == "clinic":
        return "clinic"
    if amenity == "pharmacy" or healthcare == "pharmacy":
        return "pharmacy"
    if healthcare in {"doctor", "centre"}:
        return "clinic"
    return None


def _is_emergency(tags: dict[str, str]) -> bool:
    for k in ("emergency", "opening_hours", "healthcare:emergency", "emergency:phone"):
        v = tags.get(k, "").lower()
        if any(e in v for e in EMERGENCY_VALUES) or "24/7" in v:
            return True
    return tags.get("amenity") == "hospital" and tags.get("emergency") == "yes"


async def overpass_search(
    lat: float, lon: float, radius_km: float = 25.0, limit: int = 60
) -> list[dict[str, Any]]:
    radius_m = int(radius_km * 1000)
    query = f"""
    [out:json][timeout:8];
    (
      node["amenity"~"hospital|clinic|pharmacy"](around:{radius_m},{lat},{lon});
      way["amenity"~"hospital|clinic"](around:{radius_m},{lat},{lon});
      node["healthcare"](around:{radius_m},{lat},{lon});
      way["healthcare"](around:{radius_m},{lat},{lon});
    );
    out center tags {limit};
    """
    # Budget temps court : l'interface ne doit jamais attendre Overpass plus de
    # quelques secondes avant de basculer sur le référentiel local.
    deadline = 2.5
    started = time.perf_counter()
    for url in OVERPASS_ENDPOINTS:
        remaining = deadline - (time.perf_counter() - started)
        if remaining <= 0.4:
            break
        try:
            async with httpx.AsyncClient(timeout=remaining) as client:
                r = await client.post(url, data={"data": query})
                if r.status_code != 200:
                    continue
                elements = r.json().get("elements", [])
                places = _parse_elements(elements, lat, lon)
                if places:
                    return places
        except Exception as exc:  # noqa: BLE001
            print(f"[DiaFoot][Geo] Overpass {url} indisponible : {exc}")
    return []


def _parse_elements(elements: list[dict[str, Any]], lat: float, lon: float) -> list[dict[str, Any]]:
    places: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name:fr") or tags.get("name") or tags.get("operator")
        if not name:
            continue
        category = _classify(tags)
        if not category:
            continue
        plat = el.get("lat") or (el.get("center") or {}).get("lat")
        plon = el.get("lon") or (el.get("center") or {}).get("lon")
        if plat is None or plon is None:
            continue
        key = f"{name}|{round(plat, 3)}"
        if key in seen:
            continue
        seen.add(key)
        address = " ".join(
            filter(None, [tags.get("addr:housenumber"), tags.get("addr:street"),
                          tags.get("addr:city") or tags.get("addr:town")])
        ) or tags.get("address")
        places.append({
            "id": f"osm-{el.get('type', 'node')}-{el.get('id')}",
            "name": name,
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, category),
            "lat": float(plat),
            "lon": float(plon),
            "distance_km": haversine_km(lat, lon, float(plat), float(plon)),
            "address": address or None,
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "opening_hours": tags.get("opening_hours"),
            "emergency_24_7": _is_emergency(tags),
            "website": tags.get("website") or tags.get("contact:website"),
        })
    places.sort(key=lambda p: p["distance_km"])
    return places


# ---------------------------------------------------------------------------
# Référentiel médical national de secours — Tunisie (Hôpitaux, Urgences 24/7, Diabétologie)
# ---------------------------------------------------------------------------
FALLBACK_PLACES: list[dict[str, Any]] = [
    # --- SOUSSE & SAHEL (Position de l'utilisateur) ---
    {"id": "tn-sahloul", "name": "CHU Sahloul — Urgences & Réanimation 24/7", "category": "hospital",
     "lat": 35.8354, "lon": 10.5926, "address": "Route Ceinture C118, Sahloul, Sousse",
     "phone": "+216 73 369 300", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-farhat-hached", "name": "CHU Farhat Hached — Urgences & Diabétologie", "category": "hospital",
     "lat": 35.8276, "lon": 10.6348, "address": "Rue Ibn El Jazzar, Sousse Centre",
     "phone": "+216 73 221 411", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-les-oliviers", "name": "Polyclinique Les Oliviers — Urgences 24/7", "category": "clinic",
     "lat": 35.8488, "lon": 10.6120, "address": "Boulevard du 14 Janvier, Sousse",
     "phone": "+216 73 242 711", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-essalem-sousse", "name": "Clinique Essalem Sousse", "category": "clinic",
     "lat": 35.8398, "lon": 10.6276, "address": "Avenue Léopold Senghor, Sousse",
     "phone": "+216 73 211 400", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-podo-sousse", "name": "Centre de Soins du Pied & Podologie Sousse", "category": "podiatrist",
     "lat": 35.8320, "lon": 10.6250, "address": "Avenue Habib Bourguiba, Sousse Ville",
     "phone": "+216 73 228 100", "opening_hours": "Mo-Fr 08:30-17:30", "emergency_24_7": False},
    {"id": "tn-diabete-sahloul", "name": "Unité de Diabétologie & Plaies Complexes Sahloul", "category": "diabetologist",
     "lat": 35.8380, "lon": 10.5980, "address": "Avenue Yasser Arafat, Sahloul, Sousse",
     "phone": "+216 73 368 400", "opening_hours": "Mo-Fr 08:00-16:00", "emergency_24_7": False},
    {"id": "tn-pharmacie-sahloul", "name": "Pharmacie de Garde Sahloul (Nuit & 24/7)", "category": "pharmacy",
     "lat": 35.8360, "lon": 10.5940, "address": "En face CHU Sahloul, Sousse",
     "phone": "+216 73 369 111", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-msaken", "name": "Hôpital Régional de M'saken", "category": "hospital",
     "lat": 35.7310, "lon": 10.5820, "address": "M'saken, Sousse",
     "phone": "+216 73 260 400", "opening_hours": "24/7", "emergency_24_7": True},

    # --- MONASTIR ---
    {"id": "tn-fattouma-bourguiba", "name": "CHU Fattouma Bourguiba — Urgences 24/7", "category": "hospital",
     "lat": 35.7745, "lon": 10.8285, "address": "Rue 1er Juin 1955, Monastir",
     "phone": "+216 73 461 144", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-podo-monastir", "name": "Cabinet de Podologie & Pédicurie Monastir", "category": "podiatrist",
     "lat": 35.7710, "lon": 10.8260, "address": "Avenue de la République, Monastir",
     "phone": "+216 73 460 300", "opening_hours": "Mo-Fr 08:30-17:00", "emergency_24_7": False},

    # --- MAHDIA & KAIROUAN ---
    {"id": "tn-taher-sfar", "name": "Hôpital Universitaire Taher Sfar — Mahdia", "category": "hospital",
     "lat": 35.5080, "lon": 11.0450, "address": "Boulevard Taher Sfar, Mahdia",
     "phone": "+216 73 671 500", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-ibn-jazzar-kairouan", "name": "Hôpital Régional Ibn El Jazzar — Kairouan", "category": "hospital",
     "lat": 35.6780, "lon": 10.1010, "address": "Avenue Ali Zouaoui, Kairouan",
     "phone": "+216 77 230 444", "opening_hours": "24/7", "emergency_24_7": True},

    # --- SFAX ---
    {"id": "tn-habib-bourguiba-sfax", "name": "CHU Habib Bourguiba — Sfax", "category": "hospital",
     "lat": 34.7430, "lon": 10.7580, "address": "Route El Ain Km 0.5, Sfax",
     "phone": "+216 74 241 511", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-hedi-chaker-sfax", "name": "CHU Hédi Chaker — Sfax", "category": "hospital",
     "lat": 34.7410, "lon": 10.7550, "address": "Route El Ain Km 0.5, Sfax",
     "phone": "+216 74 246 899", "opening_hours": "24/7", "emergency_24_7": True},

    # --- GRAND TUNIS ---
    {"id": "tn-charles-nicolle", "name": "Hôpital Charles-Nicolle — Urgences 24/7", "category": "hospital",
     "lat": 36.8028, "lon": 10.1717, "address": "Boulevard du 9 Avril 1938, Tunis",
     "phone": "+216 71 578 000", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-rabta", "name": "Hôpital La Rabta — Urgences 24/7", "category": "hospital",
     "lat": 36.8099, "lon": 10.1652, "address": "Rue Thameur Jabbès, Bab Saadoun, Tunis",
     "phone": "+216 71 578 666", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-aziza", "name": "Hôpital Aziza Othmana", "category": "hospital",
     "lat": 36.7986, "lon": 10.1690, "address": "Place Bab Saadoun, Tunis",
     "phone": "+216 71 577 966", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-mongi-slim", "name": "Hôpital Mongi Slim — La Marsa", "category": "hospital",
     "lat": 36.8871, "lon": 10.3246, "address": "Sidi Daoud, La Marsa",
     "phone": "+216 71 774 000", "opening_hours": "24/7", "emergency_24_7": True},
    {"id": "tn-nutrition", "name": "Institut National de Nutrition — Diabétologie", "category": "diabetologist",
     "lat": 36.8161, "lon": 10.1592, "address": "11 Rue Djebel Lakhdhar, Bab Saadoun, Tunis",
     "phone": "+216 71 260 880", "opening_hours": "Mo-Fr 08:00-16:00", "emergency_24_7": False},
    {"id": "tn-cicatrisation", "name": "Centre de Plaies & Cicatrisation — Berges du Lac",
     "category": "wound_center", "lat": 36.8378, "lon": 10.2762,
     "address": "Rue du Lac Turkana, Les Berges du Lac, Tunis",
     "phone": "+216 71 962 000", "opening_hours": "Mo-Sa 08:00-18:00", "emergency_24_7": False},
    {"id": "tn-podo-hannibal", "name": "Cabinet de Podologie Hannibal", "category": "podiatrist",
     "lat": 36.8185, "lon": 10.2151, "address": "Avenue Hannibal, Menzah 6, Tunis",
     "phone": "+216 71 234 567", "opening_hours": "Mo-Fr 09:00-18:00", "emergency_24_7": False},
    {"id": "tn-clinique-ariana", "name": "Clinique Ariana — Urgences 24/7", "category": "clinic",
     "lat": 36.8622, "lon": 10.1929, "address": "Avenue Habib Bourguiba, Ariana",
     "phone": "+216 71 700 000", "opening_hours": "24/7", "emergency_24_7": True},
]


def fallback_places(lat: float, lon: float) -> list[dict[str, Any]]:
    out = []
    for p in FALLBACK_PLACES:
        item = dict(p)
        item["category_label"] = CATEGORY_LABELS.get(p["category"], p["category"])
        item["distance_km"] = haversine_km(lat, lon, p["lat"], p["lon"])
        item.setdefault("website", None)
        out.append(item)
    out.sort(key=lambda p: p["distance_km"])
    return out


_CACHE: dict[tuple[float, float, float], tuple[float, list[dict[str, Any]], str]] = {}
_CACHE_TTL = 600.0  # secondes


async def search_nearby(
    lat: float, lon: float, radius_km: float = 25.0, category: Optional[str] = None
) -> tuple[list[dict[str, Any]], str]:
    key = (round(lat, 3), round(lon, 3), float(radius_km))
    hit = _CACHE.get(key)
    if hit and (time.perf_counter() - hit[0]) < _CACHE_TTL:
        raw_places, source = hit[1], hit[2]
    else:
        raw_places = await overpass_search(lat, lon, radius_km)
        source = "openstreetmap-overpass"
        if not raw_places:
            raw_places = fallback_places(lat, lon)
            source = "local-fallback"
        _CACHE[key] = (time.perf_counter(), raw_places, source)
    
    # 1. Filtre par distance (rayon demandé)
    filtered = [p for p in raw_places if p["distance_km"] <= radius_km]
    # Si aucun établissement dans le rayon immédiat, renvoyer les plus proches
    if not filtered and raw_places:
        filtered = list(raw_places[:10])

    # 2. Filtre par catégorie
    if category and category not in {"all", "tous"}:
        if category == "emergency":
            filtered = [p for p in filtered if p.get("emergency_24_7")]
        elif category == "wound_care":
            filtered = [p for p in filtered if p.get("category") in {"wound_center", "podiatrist", "diabetologist", "hospital", "clinic"}]
        else:
            filtered = [p for p in filtered if p.get("category") == category]

    return filtered, source
