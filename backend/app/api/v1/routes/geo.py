"""Cartographie des soins (OpenStreetMap / Overpass, sans clé API)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser
from app.schemas.schemas import GeoSearchResponse, PlaceOut
from app.services.geo import CATEGORY_LABELS, search_nearby

router = APIRouter(prefix="/geo", tags=["Géolocalisation"])


@router.get("/nearby", response_model=GeoSearchResponse)
async def nearby(
    user: CurrentUser,
    lat: float = Query(..., ge=-90, le=90, description="Latitude du patient"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude du patient"),
    radius_km: float = Query(25.0, gt=0, le=100),
    category: Optional[str] = Query(
        None, description="all | emergency | wound_care | hospital | clinic | podiatrist | diabetologist"
    ),
):
    places, source = await search_nearby(lat, lon, radius_km, category)
    return GeoSearchResponse(
        origin={"lat": lat, "lon": lon},
        radius_km=radius_km,
        count=len(places),
        source=source,
        places=[PlaceOut(**p) for p in places],
    )


@router.get("/categories")
async def categories():
    return {
        "categories": [
            {"key": "all", "label": "Tous"},
            {"key": "emergency", "label": "Urgences 24/7"},
            {"key": "wound_care", "label": "Plaies & cicatrisation"},
            {"key": "podiatrist", "label": "Podologues"},
            {"key": "diabetologist", "label": "Diabétologues"},
            {"key": "hospital", "label": CATEGORY_LABELS["hospital"]},
        ]
    }
