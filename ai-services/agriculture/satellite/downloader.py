"""
TruthChain Agriculture
======================

Copernicus EOData Downloader

Downloads Sentinel-2 assets referenced by Copernicus Data Space
STAC items.

Supported asset references:

    s3://...
    https://...
    http://...

For external CDSE S3 access, credentials are read from:

    CDSE_S3_ACCESS_KEY
    CDSE_S3_SECRET_KEY

Optional:

    CDSE_S3_ENDPOINT
    CDSE_S3_REGION
    CDSE_DOWNLOAD_TIMEOUT
    CDSE_DOWNLOAD_RETRIES
    CDSE_DOWNLOAD_BACKOFF

The downloader:

- never hardcodes credentials
- streams large files to disk
- writes through a temporary file
- computes SHA-256 while downloading
- avoids accepting a partial file as complete
- retries transient network failures
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests


# ============================================================
# Configuration
# ============================================================

DEFAULT_S3_ENDPOINT = (
    "https://eodata.dataspace.copernicus.eu"
)

DEFAULT_S3_REGION = "default"

DEFAULT_DOWNLOAD_TIMEOUT = int(
    os.getenv(
        "CDSE_DOWNLOAD_TIMEOUT",
        "300",
    )
)

DEFAULT_DOWNLOAD_RETRIES = int(
    os.getenv(
        "CDSE_DOWNLOAD_RETRIES",
        "3",
    )
)

DEFAULT_DOWNLOAD_BACKOFF = float(
    os.getenv(
        "CDSE_DOWNLOAD_BACKOFF",
        "2",
    )
)

DOWNLOAD_CHUNK_SIZE = 1024 * 1024


# ============================================================
# Errors
# ============================================================


class DownloadError(RuntimeError):
    """Base download error."""


class DownloadCredentialsError(DownloadError):
    """Raised when S3 credentials are missing."""


class InvalidAssetURIError(DownloadError):
    """Raised when an asset URI cannot be interpreted."""


class DownloadHTTPError(DownloadError):
    """Raised when a remote download returns an error."""


class DownloadIntegrityError(DownloadError):
    """Raised when a downloaded file fails an integrity check."""


# ============================================================
# Download result
# ============================================================


@dataclass(frozen=True)
class DownloadedAsset:
    """
    Metadata for a successfully downloaded asset.
    """

    source_uri: str
    local_path: Path
    size_bytes: int
    sha256: str


# ============================================================
# Environment
# ============================================================


def get_s3_access_key() -> str | None:
    """
    Return CDSE S3 access key from the environment.
    """

    value = os.getenv(
        "CDSE_S3_ACCESS_KEY"
    )

    if value is None:
        return None

    value = value.strip()

    return value or None


def get_s3_secret_key() -> str | None:
    """
    Return CDSE S3 secret key from the environment.
    """

    value = os.getenv(
        "CDSE_S3_SECRET_KEY"
    )

    if value is None:
        return None

    value = value.strip()

    return value or None


def get_s3_endpoint() -> str:
    """
    Return the configured CDSE S3 endpoint.
    """

    value = os.getenv(
        "CDSE_S3_ENDPOINT",
        DEFAULT_S3_ENDPOINT,
    ).strip()

    return value.rstrip("/")


def get_s3_region() -> str:
    """
    Return the configured S3 signing region.
    """

    value = os.getenv(
        "CDSE_S3_REGION",
        DEFAULT_S3_REGION,
    ).strip()

    return value or DEFAULT_S3_REGION


def has_s3_credentials() -> bool:
    """
    Return True when both S3 credentials are available.
    """

    return bool(
        get_s3_access_key()
        and get_s3_secret_key()
    )


# ============================================================
# Retry helpers
# ============================================================


def get_download_retries() -> int:
    """
    Return the maximum number of retries after the initial request.

    Example:
        retries = 3

    means up to 4 total attempts.
    """

    value = os.getenv(
        "CDSE_DOWNLOAD_RETRIES",
        str(DEFAULT_DOWNLOAD_RETRIES),
    )

    try:
        retries = int(value)
    except (TypeError, ValueError):
        retries = DEFAULT_DOWNLOAD_RETRIES

    return max(0, retries)


def get_download_backoff() -> float:
    """
    Return the base exponential backoff delay in seconds.
    """

    value = os.getenv(
        "CDSE_DOWNLOAD_BACKOFF",
        str(DEFAULT_DOWNLOAD_BACKOFF),
    )

    try:
        backoff = float(value)
    except (TypeError, ValueError):
        backoff = DEFAULT_DOWNLOAD_BACKOFF

    return max(0.0, backoff)


def _retry_delay(attempt: int) -> float:
    """
    Calculate exponential retry delay.

    attempt=1 -> base delay
    attempt=2 -> 2 * base delay
    attempt=3 -> 4 * base delay
    """

    base = get_download_backoff()

    if base <= 0:
        return 0.0

    return base * (2 ** max(0, attempt - 1))


def _is_retryable_status(status_code: int) -> bool:
    """
    Return True for transient HTTP status codes.
    """

    return status_code in {
        408,
        425,
        429,
        500,
        502,
        503,
        504,
        507,
        509,
        520,
        521,
        522,
        523,
        524,
    }


def _sleep_before_retry(
    attempt: int,
    *,
    context: str,
) -> None:
    """
    Sleep before retrying a failed download attempt.
    """

    delay = _retry_delay(attempt)

    if delay <= 0:
        return

    print(
        f"[Downloader] Retry {attempt} for {context} "
        f"in {delay:.1f}s..."
    )

    time.sleep(delay)


# ============================================================
# URI parsing
# ============================================================


def parse_s3_uri(
    uri: str,
) -> tuple[str, str]:
    """
    Parse an S3 URI.

    Example:

        s3://eodata/path/to/file.jp2

    returns:

        ("eodata", "path/to/file.jp2")
    """

    if not isinstance(
        uri,
        str,
    ):
        raise TypeError(
            "S3 URI must be a string."
        )

    uri = uri.strip()

    parsed = urlparse(
        uri
    )

    if parsed.scheme.lower() != "s3":
        raise InvalidAssetURIError(
            f"Expected an s3:// URI, got: {uri}"
        )

    bucket = parsed.netloc

    key = parsed.path.lstrip("/")

    if not bucket:
        raise InvalidAssetURIError(
            f"S3 URI is missing bucket: {uri}"
        )

    if not key:
        raise InvalidAssetURIError(
            f"S3 URI is missing object key: {uri}"
        )

    return bucket, key


# ============================================================
# General URI helpers
# ============================================================


def is_s3_uri(
    uri: str,
) -> bool:
    """
    Return True for s3:// URIs.
    """

    if not isinstance(
        uri,
        str,
    ):
        return False

    return uri.lower().startswith(
        "s3://"
    )


def is_http_uri(
    uri: str,
) -> bool:
    """
    Return True for HTTP(S) URIs.
    """

    if not isinstance(
        uri,
        str,
    ):
        return False

    return uri.lower().startswith(
        (
            "http://",
            "https://",
        )
    )


# ============================================================
# Filename helpers
# ============================================================


def _filename_from_uri(
    uri: str,
) -> str:
    """
    Extract a safe filename from an asset URI.
    """

    parsed = urlparse(
        uri
    )

    if parsed.scheme.lower() == "s3":
        key = parsed.path.rstrip("/")

        if not key:
            raise InvalidAssetURIError(
                f"Asset URI does not contain a filename: {uri}"
            )

        name = Path(
            key
        ).name

    else:
        name = Path(
            parsed.path
        ).name

    if not name:
        raise InvalidAssetURIError(
            f"Unable to determine filename from URI: {uri}"
        )

    return name


def ensure_local_directory(
    directory: str | Path,
) -> Path:
    """
    Create and return a local download directory.
    """

    path = Path(
        directory
    )

    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


# ============================================================
# SHA-256 helpers
# ============================================================


def _stream_to_file(
    response: requests.Response,
    destination: Path,
) -> tuple[int, str]:
    """
    Stream an HTTP response to disk while computing SHA-256.

    Any network error raised while consuming the response is
    propagated to the caller so the caller can retry safely.

    The caller is responsible for removing the temporary file
    after a failed attempt.
    """

    digest = hashlib.sha256()

    size_bytes = 0

    with destination.open(
        "wb"
    ) as output:

        for chunk in response.iter_content(
            chunk_size=DOWNLOAD_CHUNK_SIZE
        ):

            if not chunk:
                continue

            output.write(
                chunk
            )

            digest.update(
                chunk
            )

            size_bytes += len(
                chunk
            )

        output.flush()

        os.fsync(
            output.fileno()
        )

    return (
        size_bytes,
        digest.hexdigest(),
    )


def _hash_file(
    path: Path,
) -> str:
    """
    Calculate SHA-256 of a local file.
    """

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as source:

        while True:

            chunk = source.read(
                DOWNLOAD_CHUNK_SIZE
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


# ============================================================
# AWS Signature Version 4
# ============================================================


def _hmac_sha256(
    key: bytes,
    message: str,
) -> bytes:
    """
    Return HMAC-SHA256 bytes.
    """

    return hmac.new(
        key,
        message.encode(
            "utf-8"
        ),
        hashlib.sha256,
    ).digest()


def _aws_v4_signing_key(
    secret_key: str,
    date_stamp: str,
    region: str,
    service: str,
) -> bytes:
    """
    Derive the AWS Signature Version 4 signing key.
    """

    k_date = _hmac_sha256(
        (
            "AWS4"
            + secret_key
        ).encode(
            "utf-8"
        ),
        date_stamp,
    )

    k_region = hmac.new(
        k_date,
        region.encode(
            "utf-8"
        ),
        hashlib.sha256,
    ).digest()

    k_service = hmac.new(
        k_region,
        service.encode(
            "utf-8"
        ),
        hashlib.sha256,
    ).digest()

    k_signing = hmac.new(
        k_service,
        b"aws4_request",
        hashlib.sha256,
    ).digest()

    return k_signing


def _canonical_uri(
    bucket: str,
    key: str,
) -> str:
    """
    Build the canonical path for path-style S3 access.

    Example:

        /eodata/Sentinel-2/...
    """

    parts = [
        bucket,
        *key.split("/"),
    ]

    encoded = [
        quote(
            part,
            safe="-_.~",
        )
        for part in parts
    ]

    return "/" + "/".join(
        encoded
    )


def _signed_s3_request(
    *,
    bucket: str,
    key: str,
    access_key: str,
    secret_key: str,
    endpoint: str,
    region: str,
) -> requests.Response:
    """
    Make one authenticated S3 GET request using AWS Signature V4.

    The response is returned with streaming enabled.

    Retries are handled by _download_s3(), not here.
    """

    parsed_endpoint = urlparse(
        endpoint
    )

    host = parsed_endpoint.netloc

    service = "s3"

    now = datetime.now(
        timezone.utc
    )

    amz_date = now.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    date_stamp = now.strftime(
        "%Y%m%d"
    )

    canonical_uri = _canonical_uri(
        bucket,
        key,
    )

    payload_hash = hashlib.sha256(
        b""
    ).hexdigest()

    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )

    signed_headers = (
        "host;"
        "x-amz-content-sha256;"
        "x-amz-date"
    )

    canonical_request = "\n".join(
        [
            "GET",
            canonical_uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    credential_scope = (
        f"{date_stamp}/"
        f"{region}/"
        f"{service}/"
        "aws4_request"
    )

    canonical_request_hash = hashlib.sha256(
        canonical_request.encode(
            "utf-8"
        )
    ).hexdigest()

    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            canonical_request_hash,
        ]
    )

    signing_key = _aws_v4_signing_key(
        secret_key,
        date_stamp,
        region,
        service,
    )

    signature = hmac.new(
        signing_key,
        string_to_sign.encode(
            "utf-8"
        ),
        hashlib.sha256,
    ).hexdigest()

    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key}/"
        f"{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    url = (
        endpoint.rstrip("/")
        + canonical_uri
    )

    headers = {
        "Host": host,
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
        "Authorization": authorization,
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        )

    except requests.Timeout as exc:
        raise DownloadError(
            f"S3 download timed out: s3://{bucket}/{key}"
        ) from exc

    except requests.ConnectionError as exc:
        raise DownloadError(
            "Unable to connect to CDSE S3 endpoint."
        ) from exc

    except requests.RequestException as exc:
        raise DownloadError(
            f"S3 request failed: {exc}"
        ) from exc

    return response


# ============================================================
# HTTP download
# ============================================================


def _download_http(
    uri: str,
    destination: Path,
) -> DownloadedAsset:
    """
    Download an HTTP(S) asset without authentication.

    Transient network failures are retried.
    """

    retries = get_download_retries()

    last_error: Exception | None = None

    for attempt in range(
        retries + 1
    ):

        response: requests.Response | None = None

        try:
            response = requests.get(
                uri,
                stream=True,
                timeout=DEFAULT_DOWNLOAD_TIMEOUT,
            )

            if response.status_code >= 400:

                body = response.text[:1000]

                error = DownloadHTTPError(
                    "Asset download failed with "
                    f"HTTP {response.status_code}: {body}"
                )

                if (
                    _is_retryable_status(
                        response.status_code
                    )
                    and attempt < retries
                ):
                    last_error = error

                    _sleep_before_retry(
                        attempt + 1,
                        context=uri,
                    )

                    continue

                raise error

            return _save_response(
                uri,
                response,
                destination,
            )

        except (
            requests.Timeout,
            requests.ConnectionError,
        ) as exc:

            last_error = DownloadError(
                f"HTTP download failed for {uri}: {exc}"
            )

            if attempt >= retries:
                raise last_error from exc

            _sleep_before_retry(
                attempt + 1,
                context=uri,
            )

        except DownloadError as exc:

            last_error = exc

            if attempt >= retries:
                raise

            _sleep_before_retry(
                attempt + 1,
                context=uri,
            )

        finally:

            if response is not None:
                response.close()

    if last_error is not None:
        raise last_error

    raise DownloadError(
        f"HTTP download failed: {uri}"
    )


# ============================================================
# S3 download
# ============================================================


def _download_s3(
    uri: str,
    destination: Path,
) -> DownloadedAsset:
    """
    Download an authenticated CDSE S3 asset.

    Transient connection/read/timeout failures are retried from
    the beginning of the object download.

    Every retry uses a fresh signed request.
    """

    if not has_s3_credentials():
        raise DownloadCredentialsError(
            "CDSE S3 credentials are not configured. "
            "Set CDSE_S3_ACCESS_KEY and "
            "CDSE_S3_SECRET_KEY."
        )

    bucket, key = parse_s3_uri(
        uri
    )

    access_key = get_s3_access_key()
    secret_key = get_s3_secret_key()

    if access_key is None:
        raise DownloadCredentialsError(
            "CDSE_S3_ACCESS_KEY is not configured."
        )

    if secret_key is None:
        raise DownloadCredentialsError(
            "CDSE_S3_SECRET_KEY is not configured."
        )

    retries = get_download_retries()

    last_error: Exception | None = None

    for attempt in range(
        retries + 1
    ):

        response: requests.Response | None = None

        try:
            response = _signed_s3_request(
                bucket=bucket,
                key=key,
                access_key=access_key,
                secret_key=secret_key,
                endpoint=get_s3_endpoint(),
                region=get_s3_region(),
            )

            if response.status_code >= 400:

                body = response.text[:2000]

                error = DownloadHTTPError(
                    "CDSE S3 download failed "
                    f"with HTTP {response.status_code}: {body}"
                )

                if (
                    _is_retryable_status(
                        response.status_code
                    )
                    and attempt < retries
                ):
                    last_error = error

                    _sleep_before_retry(
                        attempt + 1,
                        context=uri,
                    )

                    continue

                raise error

            return _save_response(
                uri,
                response,
                destination,
            )

        except (
            requests.Timeout,
            requests.ConnectionError,
        ) as exc:

            last_error = DownloadError(
                f"S3 download failed for {uri}: {exc}"
            )

            if attempt >= retries:
                raise last_error from exc

            _sleep_before_retry(
                attempt + 1,
                context=uri,
            )

        except (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ContentDecodingError,
        ) as exc:

            last_error = DownloadError(
                f"S3 response stream failed for {uri}: {exc}"
            )

            if attempt >= retries:
                raise last_error from exc

            _sleep_before_retry(
                attempt + 1,
                context=uri,
            )

        except DownloadError as exc:

            last_error = exc

            if attempt >= retries:
                raise

            _sleep_before_retry(
                attempt + 1,
                context=uri,
            )

        finally:

            if response is not None:
                response.close()

    if last_error is not None:
        raise last_error

    raise DownloadError(
        f"S3 download failed: {uri}"
    )


# ============================================================
# Response persistence
# ============================================================


def _save_response(
    source_uri: str,
    response: requests.Response,
    destination: Path,
) -> DownloadedAsset:
    """
    Persist an HTTP response atomically.

    Data is first written to a randomly named temporary file.

    Only after the stream completes successfully is the temporary
    file renamed to its final destination.
    """

    destination = Path(
        destination
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_name = (
        "."
        + destination.name
        + "."
        + secrets.token_hex(8)
        + ".part"
    )

    temporary_path = (
        destination.parent
        / temporary_name
    )

    try:

        size_bytes, sha256 = _stream_to_file(
            response,
            temporary_path,
        )

        if size_bytes == 0:
            raise DownloadIntegrityError(
                f"Downloaded asset is empty: {source_uri}"
            )

        temporary_path.replace(
            destination
        )

        return DownloadedAsset(
            source_uri=source_uri,
            local_path=destination,
            size_bytes=size_bytes,
            sha256=sha256,
        )

    except Exception:

        if temporary_path.exists():

            try:
                temporary_path.unlink()

            except OSError:
                pass

        raise


# ============================================================
# Public download function
# ============================================================


def download_asset(
    uri: str,
    destination: str | Path,
) -> DownloadedAsset:
    """
    Download one asset.

    Supported:

        s3://...
        http://...
        https://...

    Args:
        uri:
            Remote asset URI.

        destination:
            Local file path.

    Returns:
        DownloadedAsset
    """

    if not isinstance(
        uri,
        str,
    ):
        raise TypeError(
            "Asset URI must be a string."
        )

    uri = uri.strip()

    if not uri:
        raise InvalidAssetURIError(
            "Asset URI cannot be empty."
        )

    destination = Path(
        destination
    )

    if is_s3_uri(uri):
        return _download_s3(
            uri,
            destination,
        )

    if is_http_uri(uri):
        return _download_http(
            uri,
            destination,
        )

    raise InvalidAssetURIError(
        "Unsupported asset URI scheme. "
        "Expected s3://, http://, or https://."
    )


# ============================================================
# Download by asset name
# ============================================================


def download_scene_asset(
    asset,
    output_directory: str | Path,
) -> DownloadedAsset:
    """
    Download a ResolvedAsset object from assets.py.

    The function intentionally accepts the object by duck typing
    so downloader.py does not create a circular import with
    assets.py.
    """

    if not hasattr(
        asset,
        "href",
    ):
        raise TypeError(
            "asset must provide an href attribute."
        )

    uri = str(
        asset.href
    )

    output_directory = ensure_local_directory(
        output_directory
    )

    filename = _filename_from_uri(
        uri
    )

    destination = (
        output_directory
        / filename
    )

    return download_asset(
        uri,
        destination,
    )


# ============================================================
# Batch scene download
# ============================================================


def download_scene_assets(
    assets: dict[str, Any],
    output_directory: str | Path,
) -> dict[str, DownloadedAsset]:
    """
    Download multiple resolved scene assets.

    Args:
        assets:
            Mapping such as:

                {
                    "B01": ResolvedAsset(...),
                    ...
                    "SCL": ResolvedAsset(...)
                }

        output_directory:
            Local scene directory.

    Returns:
        Mapping from logical asset name to download result.
    """

    output_directory = ensure_local_directory(
        output_directory
    )

    results: dict[str, DownloadedAsset] = {}

    for logical_name, asset in assets.items():

        results[str(logical_name)] = (
            download_scene_asset(
                asset,
                output_directory,
            )
        )

    return results


# ============================================================
# Existing-file verification
# ============================================================


def verify_download(
    downloaded: DownloadedAsset,
) -> bool:
    """
    Recompute the local SHA-256 and verify the downloaded file.
    """

    path = Path(
        downloaded.local_path
    )

    if not path.exists():
        return False

    if not path.is_file():
        return False

    if path.stat().st_size != downloaded.size_bytes:
        return False

    actual_hash = _hash_file(
        path
    )

    return (
        actual_hash.lower()
        == downloaded.sha256.lower()
    )


# ============================================================
# Safe download helper
# ============================================================


def download_scene_assets_verified(
    assets: dict[str, Any],
    output_directory: str | Path,
) -> dict[str, DownloadedAsset]:
    """
    Download all supplied assets and verify every local file.

    If one file fails integrity verification, an exception is
    raised instead of silently continuing with incomplete evidence.
    """

    results = download_scene_assets(
        assets,
        output_directory,
    )

    for logical_name, result in results.items():

        if not verify_download(
            result
        ):
            raise DownloadIntegrityError(
                "Integrity verification failed for "
                f"{logical_name}: {result.local_path}"
            )

    return results


# ============================================================
# Public exports
# ============================================================

__all__ = [
    "DEFAULT_S3_ENDPOINT",
    "DEFAULT_S3_REGION",
    "DEFAULT_DOWNLOAD_TIMEOUT",
    "DEFAULT_DOWNLOAD_RETRIES",
    "DEFAULT_DOWNLOAD_BACKOFF",
    "DOWNLOAD_CHUNK_SIZE",
    "DownloadError",
    "DownloadCredentialsError",
    "InvalidAssetURIError",
    "DownloadHTTPError",
    "DownloadIntegrityError",
    "DownloadedAsset",
    "get_s3_access_key",
    "get_s3_secret_key",
    "get_s3_endpoint",
    "get_s3_region",
    "has_s3_credentials",
    "get_download_retries",
    "get_download_backoff",
    "parse_s3_uri",
    "is_s3_uri",
    "is_http_uri",
    "ensure_local_directory",
    "download_asset",
    "download_scene_asset",
    "download_scene_assets",
    "verify_download",
    "download_scene_assets_verified",
]