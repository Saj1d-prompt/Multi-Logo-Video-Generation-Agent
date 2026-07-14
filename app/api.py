from fastapi import FastAPI, Header, HTTPException

from app.models import BatchRequest
from app.settings import settings
from app.drive_client import list_folder_files
from app.drive_client import find_asset_folders
from app.drive_client import find_logo_folder


app = FastAPI(
    title=settings.app_name,
    version="1.0.0"
)


def verify_api_key(api_key: str | None) -> None:
    if api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )


@app.get("/")
def root():
    return {
        "application": settings.app_name,
        "environment": settings.app_env,
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": settings.app_name
    }

@app.get("/drive/folders/{folder_id}/files")
def get_drive_folder_files(
    folder_id: str,
    x_api_key: str | None = Header(default=None)
):
    verify_api_key(x_api_key)

    try:
        files = list_folder_files(folder_id)

        return {
            "status": "success",
            "folder_id": folder_id,
            "total_files": len(files),
            "files": files
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


@app.post("/dry-run")
def dry_run(
    request: BatchRequest,
    x_api_key: str | None = Header(default=None)
):
    verify_api_key(x_api_key)

    return {
        "status": "success",
        "message": "Request accepted for testing",
        "received": request.model_dump()
    }

@app.get("/drive/assets/{assets_folder_id}")
def get_asset_folders(
    assets_folder_id: str,
    x_api_key: str | None = Header(default=None)
):
    verify_api_key(x_api_key)

    folders = find_asset_folders(assets_folder_id)

    return {
        "status": "success",
        "assets_folder_id": assets_folder_id,
        "folders": folders
    }

@app.get("/drive/assets/{assets_folder_id}")
def get_assets_folder(
    assets_folder_id: str,
    x_api_key: str | None = Header(default=None)
):
    verify_api_key(x_api_key)

    try:
        logo_folder = find_logo_folder(assets_folder_id)

        if not logo_folder:
            raise HTTPException(
                status_code=404,
                detail="Logos folder not found inside Assets folder"
            )

        return {
            "status": "success",
            "assets_folder_id": assets_folder_id,
            "folders": {
                "logos": logo_folder
            }
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )