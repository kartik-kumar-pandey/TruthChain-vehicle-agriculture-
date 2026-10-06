"""
TruthChain Agriculture
Copernicus Sentinel-2 STAC Client
=================================

Client for discovering Sentinel-2 L2A observations from the
Copernicus Data Space STAC API.

Responsibilities of this module:

- validate search geometry
- normalize search dates
- query Copernicus Data Space
- validate STAC responses
- extract scene metadata
- select a suitable scene
- inspect available scene assets

This module does NOT:

- download satellite rasters
- preprocess raster data
- calculate ML features
- load the crop model
- make a fraud decision

Those responsibilities belong to later pipeline modules.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

import requests


# ============================================================
# Configuration
# ============================================================

DEFAULT_STAC_URL = os.getenv(
    "CDSE_STAC_URL",
    "https://stac.dataspace.copernicus.eu/v1/search",
)

DEFAULT_COLLECTION = "sentinel-2-l2a"

DEFAULT_MAX_CLOUD = float(
    os.getenv(
        "CDSE_MAX_CLOUD",
        "20",
    )
)

DEFAULT_LIMIT = int(
    os.getenv(
        "CDSE_STAC_LIMIT",
        "20",
    )
)

REQUEST_TIMEOUT_SECONDS = int(
    os.getenv(
        "CDSE_STAC_TIMEOUT",
        "60",
    )
)


# ============================================================
# Errors
# ============================================================

class STACClientError(RuntimeError):
    """Base error for Sentinel-2 STAC operations."""


class STACRequestError(STACClientError):
    """Raised when the STAC service cannot be queried."""


class NoScenesFoundError(STACClientError):
    """Raised when no Sentinel-2 scenes satisfy the search."""


class InvalidSTACResponseError(STACClientError):
    """Raised when the STAC service returns an unexpected structure."""


# ============================================================
# Geometry validation
# ============================================================

def _validate_geometry(
    field_geojson: dict[str, Any],
) -> None:
    """
    Validate the minimum GeoJSON structure required by STAC.

    Supported geometry types:

        Point
        Polygon
        MultiPolygon
    """

    if not isinstance(field_geojson, dict):
        raise TypeError(
            "field_geojson must be a dictionary."
        )

    geometry_type = field_geojson.get("type")

    if geometry_type not in {
        "Point",
        "Polygon",
        "MultiPolygon",
    }:
        raise ValueError(
            "field_geojson must be a GeoJSON Point, "
            "Polygon, or MultiPolygon."
        )

    if "coordinates" not in field_geojson:
        raise ValueError(
            "field_geojson is missing 'coordinates'."
        )

    coordinates = field_geojson["coordinates"]

    if coordinates is None:
        raise ValueError(
            "field_geojson coordinates cannot be null."
        )


# ============================================================
# Date handling
# ============================================================

def _parse_date_value(
    value: str | date | datetime,
) -> date:
    """
    Convert supported date input into a Python date object.

    Accepted inputs:

        date
        datetime
        YYYY-MM-DD
        ISO-8601 datetime
    """

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        value = value.strip()

        if not value:
            raise ValueError(
                "Date value cannot be empty."
            )

        # First try YYYY-MM-DD.
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass

        # Then try a full ISO-8601 datetime.
        try:
            parsed = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )

            return parsed.date()

        except ValueError as exc:
            raise ValueError(
                "Invalid date value. Expected YYYY-MM-DD "
                "or an ISO-8601 datetime."
            ) from exc

    raise TypeError(
        "Date must be a string, date, or datetime."
    )


def _date_to_utc_start(
    value: date,
) -> str:
    """
    Convert a date to the beginning of that UTC day.

    Example:

        2026-09-01
        ->
        2026-09-01T00:00:00Z
    """

    dt = datetime(
        value.year,
        value.month,
        value.day,
        0,
        0,
        0,
        tzinfo=timezone.utc,
    )

    return dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _date_to_utc_end(
    value: date,
) -> str:
    """
    Convert a date to the end of that UTC day.

    Example:

        2026-09-23
        ->
        2026-09-23T23:59:59Z
    """

    dt = datetime(
        value.year,
        value.month,
        value.day,
        23,
        59,
        59,
        tzinfo=timezone.utc,
    )

    return dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def build_datetime_interval(
    start_date: str | date | datetime,
    end_date: str | date | datetime,
) -> str:
    """
    Build a complete UTC datetime interval for the STAC API.

    Example:

        build_datetime_interval(
            "2026-09-01",
            "2026-09-23",
        )

    returns:

        2026-09-01T00:00:00Z/2026-09-23T23:59:59Z
    """

    start = _parse_date_value(
        start_date
    )

    end = _parse_date_value(
        end_date
    )

    if end < start:
        raise ValueError(
            "end_date cannot be earlier than start_date."
        )

    return (
        f"{_date_to_utc_start(start)}/"
        f"{_date_to_utc_end(end)}"
    )


# ============================================================
# STAC search
# ============================================================

def search_sentinel2(
    field_geojson: dict[str, Any],
    start_date: str | date | datetime,
    end_date: str | date | datetime,
    *,
    max_cloud: float = DEFAULT_MAX_CLOUD,
    limit: int = DEFAULT_LIMIT,
    stac_url: str = DEFAULT_STAC_URL,
) -> list[dict[str, Any]]:
    """
    Search Copernicus Data Space for Sentinel-2 L2A scenes
    intersecting the supplied farm geometry.

    Args:
        field_geojson:
            GeoJSON geometry dictionary.

        start_date:
            Beginning of search period.

        end_date:
            End of search period.

        max_cloud:
            Maximum scene-level cloud-cover percentage.

        limit:
            Maximum number of returned scenes.

        stac_url:
            Copernicus Data Space STAC endpoint.

    Returns:
        List of STAC Feature dictionaries.
    """

    _validate_geometry(
        field_geojson
    )

    if not isinstance(
        stac_url,
        str,
    ):
        raise TypeError(
            "stac_url must be a string."
        )

    stac_url = stac_url.strip()

    if not stac_url:
        raise ValueError(
            "stac_url cannot be empty."
        )

    if not 0 <= max_cloud <= 100:
        raise ValueError(
            "max_cloud must be between 0 and 100."
        )

    if limit < 1:
        raise ValueError(
            "limit must be at least 1."
        )

    datetime_interval = build_datetime_interval(
        start_date,
        end_date,
    )

    payload = {
        "collections": [
            DEFAULT_COLLECTION,
        ],
        "intersects": field_geojson,
        "datetime": datetime_interval,
        "query": {
            "eo:cloud_cover": {
                "lte": float(max_cloud),
            },
        },
        "limit": int(limit),
    }

    try:
        response = requests.post(
            stac_url,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    except requests.Timeout as exc:
        raise STACRequestError(
            "Sentinel-2 STAC request timed out."
        ) from exc

    except requests.ConnectionError as exc:
        raise STACRequestError(
            "Unable to connect to the Sentinel-2 STAC service."
        ) from exc

    except requests.RequestException as exc:
        raise STACRequestError(
            f"Sentinel-2 STAC request failed: {exc}"
        ) from exc

    if response.status_code >= 400:
        body = response.text[:2000]

        raise STACRequestError(
            "Sentinel-2 STAC request failed "
            f"with HTTP {response.status_code}: {body}"
        )

    try:
        result = response.json()

    except ValueError as exc:
        raise InvalidSTACResponseError(
            "Sentinel-2 STAC service returned invalid JSON."
        ) from exc

    if not isinstance(
        result,
        dict,
    ):
        raise InvalidSTACResponseError(
            "Sentinel-2 STAC response must be a JSON object."
        )

    features = result.get(
        "features"
    )

    if not isinstance(
        features,
        list,
    ):
        raise InvalidSTACResponseError(
            "Sentinel-2 STAC response does not contain "
            "a valid 'features' list."
        )

    valid_features: list[dict[str, Any]] = []

    for feature in features:

        if not isinstance(
            feature,
            dict,
        ):
            continue

        if feature.get("type") not in {
            None,
            "Feature",
        }:
            continue

        if not feature.get("id"):
            continue

        valid_features.append(
            feature
        )

    return valid_features


# ============================================================
# Scene metadata
# ============================================================

def scene_id(
    scene: dict[str, Any],
) -> str | None:
    """
    Return the STAC scene identifier.
    """

    value = scene.get(
        "id"
    )

    if value is None:
        return None

    return str(value)


def scene_datetime(
    scene: dict[str, Any],
) -> datetime | None:
    """
    Extract the acquisition datetime from a STAC scene.

    Returns:
        timezone-aware datetime when possible.
    """

    properties = scene.get(
        "properties",
        {},
    )

    if not isinstance(
        properties,
        dict,
    ):
        return None

    value = properties.get(
        "datetime"
    )

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed


def scene_cloud_cover(
    scene: dict[str, Any],
) -> float | None:
    """
    Extract scene-level EO cloud cover.
    """

    properties = scene.get(
        "properties",
        {},
    )

    if not isinstance(
        properties,
        dict,
    ):
        return None

    value = properties.get(
        "eo:cloud_cover"
    )

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def scene_collection(
    scene: dict[str, Any],
) -> str | None:
    """
    Extract the collection identifier.
    """

    value = scene.get(
        "collection"
    )

    if value is not None:
        return str(value)

    collections = scene.get(
        "collections"
    )

    if isinstance(
        collections,
        list,
    ) and collections:
        return str(
            collections[0]
        )

    return None


# ============================================================
# Scene sorting / selection
# ============================================================

def _scene_sort_key(
    scene: dict[str, Any],
) -> tuple[float, float]:
    """
    Build a deterministic scene sorting key.

    Priority:

        1. lowest cloud cover
        2. newest acquisition time
    """

    cloud = scene_cloud_cover(
        scene
    )

    if cloud is None:
        cloud_value = 999999.0
    else:
        cloud_value = cloud

    acquired = scene_datetime(
        scene
    )

    if acquired is None:
        timestamp = float(
            "-inf"
        )
    else:
        timestamp = acquired.timestamp()

    return (
        cloud_value,
        -timestamp,
    )


def sort_scenes(
    scenes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Return scenes sorted by:

        lowest cloud cover
        then newest acquisition time
    """

    if not isinstance(
        scenes,
        list,
    ):
        raise TypeError(
            "scenes must be a list."
        )

    return sorted(
        scenes,
        key=_scene_sort_key,
    )


def choose_best_scene(
    scenes: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Select one candidate Sentinel-2 scene.

    First implementation rule:

        1. lowest scene-level cloud cover
        2. newest acquisition time as tie-breaker

    For actual insurance verification, the later pipeline will
    add incident-relative selection such as:

        pre-event
        event-period
        post-event

    rather than automatically using the newest observation.
    """

    if not scenes:
        raise NoScenesFoundError(
            "No suitable Sentinel-2 scenes found."
        )

    return sort_scenes(
        scenes
    )[0]


# ============================================================
# Asset inspection
# ============================================================

def list_scene_assets(
    scene: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    Return the assets attached to a STAC scene.

    No network download occurs here.
    """

    assets = scene.get(
        "assets"
    )

    if not isinstance(
        assets,
        dict,
    ):
        return {}

    result: dict[str, dict[str, Any]] = {}

    for name, asset in assets.items():

        if not isinstance(
            asset,
            dict,
        ):
            continue

        result[str(name)] = asset

    return result


def get_asset(
    scene: dict[str, Any],
    asset_name: str,
) -> dict[str, Any] | None:
    """
    Return one scene asset by name.
    """

    if not isinstance(
        asset_name,
        str,
    ):
        raise TypeError(
            "asset_name must be a string."
        )

    assets = list_scene_assets(
        scene
    )

    return assets.get(
        asset_name
    )


# ============================================================
# Human-readable summaries
# ============================================================

def summarize_scene(
    scene: dict[str, Any],
) -> dict[str, Any]:
    """
    Create a compact audit-friendly scene summary.
    """

    acquired = scene_datetime(
        scene
    )

    return {
        "scene_id": scene_id(
            scene
        ),
        "collection": scene_collection(
            scene
        ),
        "datetime": (
            acquired.isoformat()
            if acquired is not None
            else None
        ),
        "cloud_cover": scene_cloud_cover(
            scene
        ),
        "asset_count": len(
            list_scene_assets(scene)
        ),
    }


def summarize_scenes(
    scenes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Create compact summaries for multiple scenes.
    """

    return [
        summarize_scene(
            scene
        )
        for scene in scenes
    ]


# ============================================================
# Public exports
# ============================================================

__all__ = [
    "DEFAULT_STAC_URL",
    "DEFAULT_COLLECTION",
    "DEFAULT_MAX_CLOUD",
    "DEFAULT_LIMIT",
    "REQUEST_TIMEOUT_SECONDS",
    "STACClientError",
    "STACRequestError",
    "NoScenesFoundError",
    "InvalidSTACResponseError",
    "build_datetime_interval",
    "search_sentinel2",
    "scene_id",
    "scene_datetime",
    "scene_cloud_cover",
    "scene_collection",
    "sort_scenes",
    "choose_best_scene",
    "list_scene_assets",
    "get_asset",
    "summarize_scene",
    "summarize_scenes",
]