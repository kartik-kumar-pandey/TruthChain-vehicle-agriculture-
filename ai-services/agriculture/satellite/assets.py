"""
TruthChain Agriculture
Sentinel-2 STAC Asset Resolver
==============================

Resolves the actual Sentinel-2 L2A assets needed by the Agriculture
satellite evidence pipeline.

Required imagery:

    B01
    B02
    B03
    B04
    B05
    B06
    B07
    B08
    B8A
    B09
    B11
    B12

Required quality layer:

    SCL

Optional quality layer:

    dataMask

This module does NOT download files.

It only:

    1. validates a STAC scene
    2. identifies required assets
    3. resolves asset hrefs
    4. produces an auditable asset manifest
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from agriculture.core.constants import SENTINEL_BANDS


# ============================================================
# Configuration
# ============================================================

REQUIRED_BANDS: tuple[str, ...] = tuple(
    SENTINEL_BANDS
)

QUALITY_ASSET = "SCL"

OPTIONAL_QUALITY_ASSET = "dataMask"


# ============================================================
# Asset aliases
# ============================================================

# STAC providers may expose slightly different naming
# conventions. We first prefer exact names and then inspect
# metadata / hrefs.

ASSET_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "B01": (
        "B01",
        "b01",
        "B01_60m",
        "b01_60m",
    ),
    "B02": (
        "B02",
        "b02",
        "B02_10m",
        "b02_10m",
    ),
    "B03": (
        "B03",
        "b03",
        "B03_10m",
        "b03_10m",
    ),
    "B04": (
        "B04",
        "b04",
        "B04_10m",
        "b04_10m",
    ),
    "B05": (
        "B05",
        "b05",
        "B05_20m",
        "b05_20m",
    ),
    "B06": (
        "B06",
        "b06",
        "B06_20m",
        "b06_20m",
    ),
    "B07": (
        "B07",
        "b07",
        "B07_20m",
        "b07_20m",
    ),
    "B08": (
        "B08",
        "b08",
        "B08_10m",
        "b08_10m",
    ),
    "B8A": (
        "B8A",
        "b8a",
        "B8A_20m",
        "b8a_20m",
    ),
    "B09": (
        "B09",
        "b09",
        "B09_60m",
        "b09_60m",
    ),
    "B11": (
        "B11",
        "b11",
        "B11_20m",
        "b11_20m",
    ),
    "B12": (
        "B12",
        "b12",
        "B12_20m",
        "b12_20m",
    ),
    "SCL": (
        "SCL",
        "scl",
        "SCL_20m",
        "scl_20m",
    ),
    "dataMask": (
        "dataMask",
        "datamask",
        "DATA_MASK",
        "data_mask",
    ),
}


# ============================================================
# Errors
# ============================================================

class AssetResolverError(RuntimeError):
    """Base exception for Sentinel-2 asset resolution."""


class InvalidSceneError(AssetResolverError):
    """Raised when the STAC scene structure is invalid."""


class MissingAssetError(AssetResolverError):
    """Raised when a required satellite asset is missing."""


class InvalidAssetError(AssetResolverError):
    """Raised when a resolved asset does not contain a usable href."""


# ============================================================
# Asset descriptor
# ============================================================

@dataclass(frozen=True)
class ResolvedAsset:
    """
    Immutable description of one resolved satellite asset.
    """

    logical_name: str
    stac_key: str
    href: str
    media_type: str | None
    title: str | None
    roles: tuple[str, ...]
    extra_fields: dict[str, Any]

    @property
    def scheme(self) -> str:
        """
        Return the URI scheme.

        Examples:

            https
            s3
            file
        """

        parsed = urlparse(
            self.href
        )

        if parsed.scheme:
            return parsed.scheme

        return "file"


# ============================================================
# Scene validation
# ============================================================

def validate_scene(
    scene: Mapping[str, Any],
) -> None:
    """
    Validate the minimum STAC Item structure required for asset
    resolution.
    """

    if not isinstance(
        scene,
        Mapping,
    ):
        raise InvalidSceneError(
            "STAC scene must be a mapping."
        )

    if not scene.get("id"):
        raise InvalidSceneError(
            "STAC scene is missing its 'id'."
        )

    assets = scene.get(
        "assets"
    )

    if not isinstance(
        assets,
        Mapping,
    ):
        raise InvalidSceneError(
            "STAC scene does not contain a valid 'assets' mapping."
        )


# ============================================================
# Helpers
# ============================================================

def _normalise_asset_name(
    value: str,
) -> str:
    """
    Normalize an asset name for comparison.
    """

    return "".join(
        char.lower()
        for char in value
        if char.isalnum()
    )


def _asset_href(
    asset: Mapping[str, Any],
) -> str | None:
    """
    Extract an asset href.
    """

    href = asset.get(
        "href"
    )

    if href is None:
        return None

    if not isinstance(
        href,
        str,
    ):
        href = str(href)

    href = href.strip()

    if not href:
        return None

    return href


def _asset_title(
    asset: Mapping[str, Any],
) -> str | None:
    """
    Extract asset title.
    """

    value = asset.get(
        "title"
    )

    if value is None:
        return None

    return str(value)


def _asset_media_type(
    asset: Mapping[str, Any],
) -> str | None:
    """
    Extract asset media type.
    """

    value = asset.get(
        "type"
    )

    if value is None:
        return None

    return str(value)


def _asset_roles(
    asset: Mapping[str, Any],
) -> tuple[str, ...]:
    """
    Extract asset roles.
    """

    roles = asset.get(
        "roles"
    )

    if not isinstance(
        roles,
        (list, tuple),
    ):
        return ()

    return tuple(
        str(role)
        for role in roles
        if role is not None
    )


# ============================================================
# Exact asset lookup
# ============================================================

def _find_exact_key(
    assets: Mapping[str, Any],
    logical_name: str,
) -> str | None:
    """
    Find a direct or case-insensitive asset-key match.
    """

    aliases = ASSET_NAME_ALIASES.get(
        logical_name,
        (logical_name,),
    )

    # --------------------------------------------------------
    # Exact key matching
    # --------------------------------------------------------

    for alias in aliases:
        if alias in assets:
            return alias

    # --------------------------------------------------------
    # Case-insensitive matching
    # --------------------------------------------------------

    lowered = {
        str(key).lower(): str(key)
        for key in assets.keys()
    }

    for alias in aliases:
        found = lowered.get(
            alias.lower()
        )

        if found is not None:
            return found

    return None


# ============================================================
# Metadata / href lookup
# ============================================================

def _matches_logical_band(
    logical_name: str,
    stac_key: str,
    asset: Mapping[str, Any],
) -> bool:
    """
    Determine whether a STAC asset represents a requested
    Sentinel-2 logical band.
    """

    normalized_target = _normalise_asset_name(
        logical_name
    )

    candidates = [
        stac_key,
        str(
            asset.get(
                "title",
                ""
            )
        ),
        str(
            asset.get(
                "description",
                ""
            )
        ),
        str(
            asset.get(
                "common_name",
                ""
            )
        ),
        str(
            asset.get(
                "name",
                ""
            )
        ),
        str(
            asset.get(
                "href",
                ""
            )
        ),
    ]

    aliases = ASSET_NAME_ALIASES.get(
        logical_name,
        (logical_name,),
    )

    normalized_aliases = {
        _normalise_asset_name(alias)
        for alias in aliases
    }

    # --------------------------------------------------------
    # Direct normalized match
    # --------------------------------------------------------

    for candidate in candidates:

        normalized_candidate = _normalise_asset_name(
            candidate
        )

        if normalized_candidate in normalized_aliases:
            return True

    # --------------------------------------------------------
    # Token / filename match
    # --------------------------------------------------------

    for candidate in candidates:

        candidate_lower = candidate.lower()

        if logical_name.lower() in candidate_lower:
            return True

        for alias in aliases:
            if alias.lower() in candidate_lower:
                return True

    # --------------------------------------------------------
    # Exact normalized target
    # --------------------------------------------------------

    for candidate in candidates:

        normalized_candidate = _normalise_asset_name(
            candidate
        )

        if normalized_target in normalized_candidate:
            return True

    return False


def _find_by_metadata(
    assets: Mapping[str, Any],
    logical_name: str,
) -> str | None:
    """
    Search STAC asset metadata when the key itself does not
    directly identify the band.
    """

    for key, value in assets.items():

        if not isinstance(
            value,
            Mapping,
        ):
            continue

        if _matches_logical_band(
            logical_name,
            str(key),
            value,
        ):
            return str(key)

    return None


# ============================================================
# Resolve one asset
# ============================================================

def resolve_asset_key(
    scene: Mapping[str, Any],
    logical_name: str,
) -> str | None:
    """
    Resolve a logical Sentinel-2 asset name to the actual STAC key.

    Example:

        B08 -> B08
        B8A -> b8a

    Returns:
        Actual STAC asset key or None.
    """

    validate_scene(
        scene
    )

    assets = scene["assets"]

    if not isinstance(
        assets,
        Mapping,
    ):
        return None

    # Prefer exact known keys.
    exact = _find_exact_key(
        assets,
        logical_name,
    )

    if exact is not None:
        return exact

    # Fall back to metadata/href inspection.
    return _find_by_metadata(
        assets,
        logical_name,
    )


# ============================================================
# Resolve one complete asset
# ============================================================

def resolve_asset(
    scene: Mapping[str, Any],
    logical_name: str,
) -> ResolvedAsset:
    """
    Resolve and validate one logical Sentinel-2 asset.
    """

    validate_scene(
        scene
    )

    key = resolve_asset_key(
        scene,
        logical_name,
    )

    if key is None:
        raise MissingAssetError(
            f"Required Sentinel-2 asset not found: "
            f"{logical_name}"
        )

    asset = scene["assets"][key]

    if not isinstance(
        asset,
        Mapping,
    ):
        raise InvalidAssetError(
            f"STAC asset '{key}' is not a valid mapping."
        )

    href = _asset_href(
        asset
    )

    if href is None:
        raise InvalidAssetError(
            f"STAC asset '{key}' does not contain a usable href."
        )

    return ResolvedAsset(
        logical_name=logical_name,
        stac_key=str(key),
        href=href,
        media_type=_asset_media_type(
            asset
        ),
        title=_asset_title(
            asset
        ),
        roles=_asset_roles(
            asset
        ),
        extra_fields={
            str(k): v
            for k, v in asset.items()
            if k
            not in {
                "href",
                "type",
                "title",
                "roles",
            }
        },
    )


# ============================================================
# Resolve required satellite assets
# ============================================================

def resolve_satellite_assets(
    scene: Mapping[str, Any],
    *,
    require_scl: bool = True,
    require_data_mask: bool = False,
) -> dict[str, ResolvedAsset]:
    """
    Resolve the complete satellite asset set required by the
    Agriculture pipeline.

    Required:

        twelve Sentinel-2 bands

    Usually required:

        SCL

    Optional:

        dataMask
    """

    validate_scene(
        scene
    )

    resolved: dict[str, ResolvedAsset] = {}

    # --------------------------------------------------------
    # Twelve model bands
    # --------------------------------------------------------

    for band in REQUIRED_BANDS:

        resolved[band] = resolve_asset(
            scene,
            band,
        )

    # --------------------------------------------------------
    # SCL quality layer
    # --------------------------------------------------------

    if require_scl:

        resolved[QUALITY_ASSET] = resolve_asset(
            scene,
            QUALITY_ASSET,
        )

    # --------------------------------------------------------
    # Optional data mask
    # --------------------------------------------------------

    if require_data_mask:

        resolved[OPTIONAL_QUALITY_ASSET] = resolve_asset(
            scene,
            OPTIONAL_QUALITY_ASSET,
        )

    return resolved


# ============================================================
# Resolve only model bands
# ============================================================

def resolve_model_bands(
    scene: Mapping[str, Any],
) -> dict[str, ResolvedAsset]:
    """
    Resolve only the twelve Sentinel-2 bands used by the
    agriculture satellite model.
    """

    return resolve_satellite_assets(
        scene,
        require_scl=False,
        require_data_mask=False,
    )


# ============================================================
# Manifest generation
# ============================================================

def build_asset_manifest(
    scene: Mapping[str, Any],
    *,
    require_scl: bool = True,
    require_data_mask: bool = False,
) -> dict[str, Any]:
    """
    Build an audit-friendly asset manifest.

    The manifest contains no raster data.
    It records only metadata and references.
    """

    validate_scene(
        scene
    )

    resolved = resolve_satellite_assets(
        scene,
        require_scl=require_scl,
        require_data_mask=require_data_mask,
    )

    scene_identifier = str(
        scene["id"]
    )

    manifest_assets: dict[str, Any] = {}

    for logical_name, asset in resolved.items():

        manifest_assets[logical_name] = {
            "stac_key": asset.stac_key,
            "href": asset.href,
            "scheme": asset.scheme,
            "media_type": asset.media_type,
            "title": asset.title,
            "roles": list(
                asset.roles
            ),
        }

    return {
        "scene_id": scene_identifier,
        "collection": scene.get(
            "collection"
        ),
        "assets": manifest_assets,
        "required_model_bands": list(
            REQUIRED_BANDS
        ),
        "required_quality_asset": (
            QUALITY_ASSET
            if require_scl
            else None
        ),
        "optional_quality_asset": (
            OPTIONAL_QUALITY_ASSET
            if require_data_mask
            else None
        ),
    }


# ============================================================
# Local-file utility
# ============================================================

def asset_href_to_local_path(
    asset: ResolvedAsset,
) -> Path | None:
    """
    Convert a local/file URI asset into a Path.

    Remote assets return None.

    This helper does NOT download anything.
    """

    scheme = asset.scheme.lower()

    if scheme == "file":

        parsed = urlparse(
            asset.href
        )

        if parsed.scheme == "file":

            return Path(
                parsed.path
            )

        return Path(
            asset.href
        )

    return None


def is_remote_asset(
    asset: ResolvedAsset,
) -> bool:
    """
    Return True for remote HTTP(S), S3, or other URI assets.
    """

    return (
        asset.scheme.lower()
        not in {
            "",
            "file",
        }
    )


# ============================================================
# Public exports
# ============================================================

__all__ = [
    "REQUIRED_BANDS",
    "QUALITY_ASSET",
    "OPTIONAL_QUALITY_ASSET",
    "ASSET_NAME_ALIASES",
    "AssetResolverError",
    "InvalidSceneError",
    "MissingAssetError",
    "InvalidAssetError",
    "ResolvedAsset",
    "validate_scene",
    "resolve_asset_key",
    "resolve_asset",
    "resolve_satellite_assets",
    "resolve_model_bands",
    "build_asset_manifest",
    "asset_href_to_local_path",
    "is_remote_asset",
]