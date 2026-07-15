from __future__ import annotations

import json
from typing import Any

from fetcher import fetch_prices
from profile_builder import FetchProfile
from config import (
    DEFAULT_DAYS_AHEAD,
    DEFAULT_SLEEP_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    STORAGE_ACCOUNT_NAME,
    STORAGE_CONTAINER,
)


class UploadError(RuntimeError):
    pass


def storage_account_url() -> str:
    return f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"


def managed_identity_credential() -> Any:
    try:
        from azure.identity import DefaultAzureCredential
    except ModuleNotFoundError as exc:
        raise UploadError("Azure Identity SDK is not installed.") from exc

    return DefaultAzureCredential()


def blob_service_client() -> Any:
    try:
        from azure.storage.blob import BlobServiceClient
    except ModuleNotFoundError as exc:
        raise UploadError("Azure Storage SDK is not installed.") from exc

    return BlobServiceClient(
        account_url=storage_account_url(),
        credential=managed_identity_credential(),
    )


def upload_json(payload: dict[str, Any], blob_name: str) -> dict[str, Any]:
    try:
        from azure.storage.blob import ContentSettings
    except ModuleNotFoundError as exc:
        raise UploadError("Azure Storage SDK is not installed.") from exc

    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    blob = blob_service_client().get_blob_client(container=STORAGE_CONTAINER, blob=blob_name)
    blob.upload_blob(
        body,
        overwrite=True,
        content_settings=ContentSettings(
            content_type="application/json; charset=utf-8",
            cache_control="no-cache",
        ),
    )
    return {
        "container": STORAGE_CONTAINER,
        "blob_name": blob_name,
        "bytes_written": len(body),
    }


def refresh_prices(profile: FetchProfile) -> dict[str, Any]:
    payload = fetch_prices(
        profile=profile,
        days_ahead=DEFAULT_DAYS_AHEAD,
        sleep_seconds=DEFAULT_SLEEP_SECONDS,
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    upload = upload_json(payload, profile.blob_name)
    return {
        "profile": profile.key,
        "schedule_name": profile.schedule_name,
        "journeys_fetched": len(payload["trains"]),
        "last_updated": payload["last_updated"],
        **upload,
    }
