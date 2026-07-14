from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

from app.settings import settings


DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive"
]


def get_drive_service():
    credentials_path = settings.google_application_credentials

    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Google service account file not found: {credentials_path}"
        )

    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=DRIVE_SCOPES
    )

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False
    )


def list_folder_files(folder_id: str) -> list[dict[str, Any]]:
    service = get_drive_service()

    files: list[dict[str, Any]] = []
    page_token = None

    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            spaces="drive",
            fields=(
                "nextPageToken,"
                "files("
                "id,"
                "name,"
                "mimeType,"
                "size,"
                "modifiedTime,"
                "webViewLink"
                ")"
            ),
            pageToken=page_token
        ).execute()

        files.extend(response.get("files", []))

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return files


def download_file(
    file_id: str,
    destination: Path
) -> Path:
    service = get_drive_service()

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    request = service.files().get_media(
        fileId=file_id
    )

    with destination.open("wb") as file_handle:
        downloader = MediaIoBaseDownload(
            file_handle,
            request
        )

        done = False

        while not done:
            _, done = downloader.next_chunk()

    return destination


def upload_video(
    local_file: Path,
    output_folder_id: str
) -> dict[str, Any]:
    if not local_file.exists():
        raise FileNotFoundError(
            f"Upload file not found: {local_file}"
        )

    service = get_drive_service()

    metadata = {
        "name": local_file.name,
        "parents": [output_folder_id]
    }

    media = MediaFileUpload(
        str(local_file),
        mimetype="video/mp4",
        resumable=True
    )

    uploaded = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,webViewLink"
    ).execute()

    return uploaded