"""
TruthChain Agriculture
Satellite Evidence Orchestrator
================================

Production orchestration for Sentinel-2 satellite crop evidence.

Pipeline:

    STAC scene search
        ->
    model-band asset resolution
        ->
    verified local download
        ->
    common 10 m field grid
        ->
    field pixels
        ->
    production 77-feature extraction
        ->
    satellite crop inference

This module produces satellite evidence only.
It does not make a fraud or insurance claim decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from shapely.geometry import Point, shape
from shapely.ops import transform

from agriculture.satellite.assets import (
    resolve_model_bands,
)
from agriculture.satellite.downloader import (
    download_scene_assets_verified,
)
from agriculture.satellite.features import (
    FEATURE_NAMES,
    extract_feature_vector,
)
from agriculture.satellite.inference import (
    SatelliteCropInference,
    SatelliteInferenceResult,
)
from agriculture.satellite.stac_client import (
    search_sentinel2,
)


SENTINEL_SCALE = 0.01
TARGET_RESOLUTION = 10.0

SOURCE_CRS = "EPSG:4326"

BANDS = (
    "B01",
    "B02",
    "B03",
    "B04",
    "B05",
    "B06",
    "B07",
    "B08",
    "B8A",
    "B09",
    "B11",
    "B12",
)

SOURCE_RESOLUTION = {
    "B01": 60.0,
    "B02": 10.0,
    "B03": 10.0,
    "B04": 10.0,
    "B05": 20.0,
    "B06": 20.0,
    "B07": 20.0,
    "B08": 10.0,
    "B8A": 20.0,
    "B09": 60.0,
    "B11": 20.0,
    "B12": 20.0,
}


class SatelliteEvidenceError(RuntimeError):
    """Base error for satellite evidence processing."""


class SatelliteFieldError(SatelliteEvidenceError):
    """Raised when the supplied field geometry is invalid."""


@dataclass(frozen=True)
class DownloadEvidence:
    """Integrity metadata for one downloaded Sentinel-2 asset."""

    logical_name: str
    source_uri: str
    local_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class SatelliteEvidenceResult:
    """Complete satellite crop-evidence result."""

    scene_id: str
    scene_datetime: str | None
    cloud_cover: float | None

    field_area_m2: float
    field_pixel_count: int
    target_resolution_m: float

    feature_count: int
    features: tuple[float, ...]

    inference: SatelliteInferenceResult

    downloads: tuple[DownloadEvidence, ...]


def _scene_datetime(
    scene: Mapping[str, Any],
) -> str | None:
    value = scene.get("datetime")

    if value is None:
        properties = scene.get(
            "properties",
            {},
        )

        if isinstance(properties, Mapping):
            value = properties.get(
                "datetime"
            )

    if value is None:
        return None

    return str(value)


def _scene_cloud_cover(
    scene: Mapping[str, Any],
) -> float | None:
    properties = scene.get(
        "properties",
        {},
    )

    if not isinstance(
        properties,
        Mapping,
    ):
        return None

    value = properties.get(
        "eo:cloud_cover"
    )

    if value is None:
        value = properties.get(
            "cloud_cover"
        )

    if value is None:
        return None

    return float(value)


def _normalise_date(
    value: str | date | datetime,
) -> str:
    if isinstance(
        value,
        datetime,
    ):
        return value.date().isoformat()

    if isinstance(
        value,
        date,
    ):
        return value.isoformat()

    return str(value)


def _validate_field_geojson(
    field_geojson: Mapping[str, Any],
):
    if not isinstance(
        field_geojson,
        Mapping,
    ):
        raise SatelliteFieldError(
            "field_geojson must be a mapping."
        )

    if field_geojson.get("type") == "Feature":
        geometry = field_geojson.get(
            "geometry"
        )
    else:
        geometry = field_geojson

    if not isinstance(
        geometry,
        Mapping,
    ):
        raise SatelliteFieldError(
            "field_geojson must contain a GeoJSON "
            "geometry or Feature."
        )

    try:
        field = shape(geometry)
    except Exception as exc:
        raise SatelliteFieldError(
            "Unable to construct field geometry."
        ) from exc

    if field.is_empty:
        raise SatelliteFieldError(
            "Field geometry is empty."
        )

    if not field.is_valid:
        raise SatelliteFieldError(
            "Field geometry is invalid."
        )

    if field.geom_type not in {
        "Polygon",
        "MultiPolygon",
    }:
        raise SatelliteFieldError(
            "Field geometry must be a Polygon "
            "or MultiPolygon."
        )

    return field


def _project_field(
    field_wgs84,
    target_crs,
):
    transformer = Transformer.from_crs(
        SOURCE_CRS,
        target_crs,
        always_xy=True,
    )

    field_projected = transform(
        transformer.transform,
        field_wgs84,
    )

    if field_projected.is_empty:
        raise SatelliteFieldError(
            "Projected field geometry is empty."
        )

    if not field_projected.is_valid:
        raise SatelliteFieldError(
            "Projected field geometry is invalid."
        )

    return field_projected


def _target_grid(
    field_projected,
):
    min_x, min_y, max_x, max_y = (
        field_projected.bounds
    )

    width = int(
        round(
            (max_x - min_x)
            / TARGET_RESOLUTION
        )
    )

    height = int(
        round(
            (max_y - min_y)
            / TARGET_RESOLUTION
        )
    )

    if width <= 0 or height <= 0:
        raise SatelliteFieldError(
            "Field geometry produces an empty "
            "10 m target grid."
        )

    transform_out = from_origin(
        min_x,
        max_y,
        TARGET_RESOLUTION,
        TARGET_RESOLUTION,
    )

    return (
        transform_out,
        width,
        height,
    )


def _read_band(
    path: Path,
    band: str,
    target_crs,
    target_transform,
    target_width: int,
    target_height: int,
) -> np.ndarray:
    expected_resolution = (
        SOURCE_RESOLUTION[band]
    )

    with rasterio.open(path) as src:
        if src.crs is None:
            raise SatelliteEvidenceError(
                f"{band}: raster has no CRS."
            )

        if not np.issubdtype(
            np.dtype(src.dtypes[0]),
            np.integer,
        ):
            raise SatelliteEvidenceError(
                f"{band}: expected integer Sentinel-2 "
                f"DN raster, got {src.dtypes[0]}."
            )

        actual_resolution = src.res

        if not (
            abs(
                actual_resolution[0]
                - expected_resolution
            )
            < 0.01
            and abs(
                actual_resolution[1]
                - expected_resolution
            )
            < 0.01
        ):
            raise SatelliteEvidenceError(
                f"{band}: expected "
                f"{expected_resolution} m source "
                f"resolution, got "
                f"{actual_resolution}."
            )

        if src.crs != target_crs:
            raise SatelliteEvidenceError(
                f"{band}: raster CRS {src.crs} "
                f"does not match target CRS "
                f"{target_crs}."
            )

        destination = np.zeros(
            (
                target_height,
                target_width,
            ),
            dtype=np.float32,
        )

        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            resampling=Resampling.bilinear,
        )

        if not np.isfinite(
            destination
        ).all():
            raise SatelliteEvidenceError(
                f"{band}: resampled field contains "
                "NaN or Inf."
            )

        return destination


def _build_center_mask(
    field_projected,
    target_transform,
    width: int,
    height: int,
) -> np.ndarray:
    """
    Build a boolean mask using the center point
    of every target-grid pixel.

    rasterio.transform.xy() returns coordinate
    arrays matching the input row/column arrays.
    We therefore flatten the generated coordinate
    arrays before constructing the mask.
    """

    rows, cols = np.indices(
        (height, width)
    )

    rows_flat = rows.ravel()
    cols_flat = cols.ravel()

    xs, ys = rasterio.transform.xy(
        target_transform,
        rows_flat,
        cols_flat,
        offset="center",
    )

    xs = np.asarray(xs)
    ys = np.asarray(ys)

    pixel_mask_flat = np.zeros(
        rows_flat.shape,
        dtype=bool,
    )

    for index in range(
        rows_flat.size
    ):
        point = Point(
            float(xs[index]),
            float(ys[index]),
        )

        if field_projected.contains(
            point
        ):
            pixel_mask_flat[index] = True

    return pixel_mask_flat.reshape(
        height,
        width,
    )


def _extract_field_arrays(
    downloads: Mapping[str, Any],
    field_projected,
    target_crs,
) -> tuple[dict[str, np.ndarray], int]:
    """
    Resample all twelve downloaded bands to one
    common 10 m grid and select pixels whose
    centers fall inside the field polygon.
    """

    b04_result = downloads.get(
        "B04"
    )

    if b04_result is None:
        raise SatelliteEvidenceError(
            "Downloaded assets do not contain B04."
        )

    b04_path = Path(
        b04_result.local_path
    )

    with rasterio.open(
        b04_path
    ) as src:
        if src.crs is None:
            raise SatelliteEvidenceError(
                "B04 raster has no CRS."
            )

        raster_crs = src.crs

    if raster_crs != target_crs:
        raise SatelliteEvidenceError(
            f"Raster CRS {raster_crs} does not "
            f"match target CRS {target_crs}."
        )

    target_transform, width, height = (
        _target_grid(field_projected)
    )

    pixel_mask = _build_center_mask(
        field_projected,
        target_transform,
        width,
        height,
    )

    pixel_count = int(
        pixel_mask.sum()
    )

    if pixel_count == 0:
        raise SatelliteFieldError(
            "No target-grid pixels fall inside "
            "the supplied field."
        )

    arrays = {}

    for band in BANDS:
        result = downloads.get(
            band
        )

        if result is None:
            raise SatelliteEvidenceError(
                f"Missing downloaded band: {band}"
            )

        array = _read_band(
            Path(result.local_path),
            band,
            target_crs,
            target_transform,
            width,
            height,
        )

        field_values = array[
            pixel_mask
        ]

        if field_values.shape != (
            pixel_count,
        ):
            raise SatelliteEvidenceError(
                f"{band}: inconsistent field pixel "
                f"shape {field_values.shape}."
            )

        arrays[band] = field_values

    return (
        arrays,
        pixel_count,
    )


class SatelliteEvidenceAgent:
    """
    Production satellite evidence agent.

    This class orchestrates the existing validated
    STAC, asset-resolution, download, feature, and
    inference components.
    """

    def __init__(
        self,
        *,
        model_path: str | Path | None = None,
    ) -> None:
        if model_path is None:
            self.inference = (
                SatelliteCropInference()
            )
        else:
            self.inference = (
                SatelliteCropInference(
                    model_path
                )
            )

    def run(
        self,
        *,
        field_geojson: Mapping[str, Any],
        start_date: str | date | datetime,
        end_date: str | date | datetime,
        claimed_source_id: int | None = None,
        max_cloud: float = 20.0,
        output_directory: str | Path = (
            "data/satellite/evidence"
        ),
        limit: int = 20,
    ) -> SatelliteEvidenceResult:
        """
        Run the complete satellite evidence pipeline.

        The first STAC result is used after the supplied
        cloud/date filters have been applied.
        """

        field_wgs84 = (
            _validate_field_geojson(
                field_geojson
            )
        )

        search_results = search_sentinel2(
            field_geojson,
            _normalise_date(start_date),
            _normalise_date(end_date),
            max_cloud=max_cloud,
            limit=limit,
        )

        if not search_results:
            raise SatelliteEvidenceError(
                "No Sentinel-2 scenes matched the "
                "field and requested date/cloud filters."
            )

        scene = search_results[0]

        scene_id = str(
            scene.get("id")
        )

        if not scene_id:
            raise SatelliteEvidenceError(
                "Selected STAC scene has no ID."
            )

        assets = resolve_model_bands(
            scene
        )

        if set(assets) != set(BANDS):
            raise SatelliteEvidenceError(
                "Resolved scene does not contain "
                "exactly the required twelve model bands."
            )

        scene_directory = (
            Path(output_directory)
            / scene_id
        )

        downloads = (
            download_scene_assets_verified(
                assets,
                scene_directory,
            )
        )

        b04_path = Path(
            downloads["B04"].local_path
        )

        with rasterio.open(
            b04_path
        ) as src:
            raster_crs = src.crs

        if raster_crs is None:
            raise SatelliteEvidenceError(
                "B04 raster has no CRS."
            )

        field_projected = _project_field(
            field_wgs84,
            raster_crs,
        )

        field_area_m2 = float(
            field_projected.area
        )

        field_arrays, pixel_count = (
            _extract_field_arrays(
                downloads,
                field_projected,
                raster_crs,
            )
        )

        scaled_arrays = {
            band: values.astype(
                np.float64
            ) * SENTINEL_SCALE
            for band, values in (
                field_arrays.items()
            )
        }

        feature_vector = (
            extract_feature_vector(
                scaled_arrays
            )
        )

        if feature_vector.shape != (
            len(FEATURE_NAMES),
        ):
            raise SatelliteEvidenceError(
                "Production feature extractor returned "
                f"{feature_vector.shape}; expected "
                f"({len(FEATURE_NAMES)},)."
            )

        inference = self.inference.predict(
            feature_vector,
            claimed_source_id=claimed_source_id,
        )

        download_records = tuple(
            DownloadEvidence(
                logical_name=logical_name,
                source_uri=str(
                    result.source_uri
                ),
                local_path=str(
                    result.local_path
                ),
                size_bytes=int(
                    result.size_bytes
                ),
                sha256=str(
                    result.sha256
                ),
            )
            for logical_name, result
            in downloads.items()
        )

        return SatelliteEvidenceResult(
            scene_id=scene_id,
            scene_datetime=_scene_datetime(
                scene
            ),
            cloud_cover=_scene_cloud_cover(
                scene
            ),
            field_area_m2=field_area_m2,
            field_pixel_count=pixel_count,
            target_resolution_m=TARGET_RESOLUTION,
            feature_count=len(
                FEATURE_NAMES
            ),
            features=tuple(
                float(value)
                for value in feature_vector
            ),
            inference=inference,
            downloads=download_records,
        )


__all__ = [
    "SENTINEL_SCALE",
    "TARGET_RESOLUTION",
    "BANDS",
    "SOURCE_RESOLUTION",
    "SatelliteEvidenceError",
    "SatelliteFieldError",
    "DownloadEvidence",
    "SatelliteEvidenceResult",
    "SatelliteEvidenceAgent",
]