import shutil
import tempfile
from pathlib import Path

import httpx
from fastapi import (
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse

from app.clickup_client import (
    discover_workspace_lists,
    get_tasks_by_list_name,
)
from app.drive_client import (
    find_logo_folder,
    list_folder_files,
)
from app.matching import build_dry_run_plan
from app.models import BatchRequest
from app.renderer import (
    RenderError,
    add_full_frame_logo,
    check_ffmpeg,
)
from app.settings import settings


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
)


def verify_api_key(api_key: str | None) -> None:
    if api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )


def safe_filename(file_name: str) -> str:
    """
    Prevent directory traversal and keep only a filename.
    """

    cleaned_name = Path(file_name).name

    if not cleaned_name:
        raise ValueError("Output filename cannot be empty")

    if not cleaned_name.lower().endswith(".mp4"):
        cleaned_name = f"{cleaned_name}.mp4"

    return cleaned_name


async def save_upload_file(
    upload: UploadFile,
    destination: Path,
) -> None:
    """
    Save an uploaded file in chunks instead of loading
    the complete video into memory.
    """

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with destination.open("wb") as file_handle:
        while True:
            chunk = await upload.read(
                1024 * 1024
            )

            if not chunk:
                break

            file_handle.write(chunk)

    await upload.close()


@app.on_event("startup")
def validate_runtime() -> None:
    settings.workspace_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    check_ffmpeg()


@app.get("/")
def root():
    return {
        "application": settings.app_name,
        "environment": settings.app_env,
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": settings.app_name,
    }


@app.get("/drive/folders/{folder_id}/files")
def get_drive_folder_files(
    folder_id: str,
    x_api_key: str | None = Header(
        default=None
    ),
):
    verify_api_key(x_api_key)

    try:
        files = list_folder_files(
            folder_id
        )

        return {
            "status": "success",
            "folder_id": folder_id,
            "total_files": len(files),
            "files": files,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@app.get("/drive/assets/{assets_folder_id}")
def get_assets_folder(
    assets_folder_id: str,
    x_api_key: str | None = Header(
        default=None
    ),
):
    verify_api_key(x_api_key)

    try:
        logo_folder = find_logo_folder(
            assets_folder_id
        )

        if not logo_folder:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Logos folder not found "
                    "inside Assets folder"
                ),
            )

        return {
            "status": "success",
            "assets_folder_id": (
                assets_folder_id
            ),
            "folders": {
                "logos": logo_folder,
            },
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@app.get(
    "/clickup/workspaces/{workspace_id}/lists"
)
def get_clickup_workspace_lists(
    workspace_id: str,
    x_api_key: str | None = Header(
        default=None
    ),
):
    verify_api_key(x_api_key)

    try:
        lists = discover_workspace_lists(
            workspace_id
        )

        return {
            "status": "success",
            "workspace_id": workspace_id,
            "total_lists": len(lists),
            "lists": lists,
        }

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=(
                error.response.status_code
            ),
            detail=error.response.text,
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@app.get(
    "/clickup/workspaces/"
    "{workspace_id}/lists/by-name/tasks"
)
def get_clickup_tasks_by_list_name(
    workspace_id: str,
    list_name: str,
    x_api_key: str | None = Header(
        default=None
    ),
):
    verify_api_key(x_api_key)

    try:
        result = get_tasks_by_list_name(
            workspace_id=workspace_id,
            list_name=list_name,
        )

        return {
            "status": "success",
            "workspace_id": workspace_id,
            "list": result["list"],
            "total_tasks": len(
                result["tasks"]
            ),
            "tasks": result["tasks"],
        }

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=(
                error.response.status_code
            ),
            detail=error.response.text,
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@app.post("/dry-run")
def dry_run(
    request: BatchRequest,
    x_api_key: str | None = Header(
        default=None
    ),
):
    verify_api_key(x_api_key)

    try:
        video_folder_files = (
            list_folder_files(
                request.video_folder_id
            )
        )

        videos = [
            file
            for file in video_folder_files
            if file.get(
                "mimeType",
                "",
            ).startswith("video/")
        ]

        logo_folder = find_logo_folder(
            request.assets_folder_id
        )

        if not logo_folder:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Logos folder not found "
                    "inside Assets folder"
                ),
            )

        asset_files = list_folder_files(
            logo_folder["id"]
        )

        logo_files = [
            file
            for file in asset_files
            if file.get("mimeType") in {
                "image/png",
                "image/jpeg",
                "image/webp",
            }
        ]

        clickup_result = (
            get_tasks_by_list_name(
                workspace_id=(
                    request
                    .clickup_workspace_id
                ),
                list_name=(
                    request
                    .clickup_list_name
                ),
            )
        )

        plan = build_dry_run_plan(
            videos=videos,
            logo_files=logo_files,
            tasks=clickup_result["tasks"],
        )

        return {
            "status": "success",
            "video_folder_id": (
                request.video_folder_id
            ),
            "assets_folder_id": (
                request.assets_folder_id
            ),
            "output_folder_id": (
                request.output_folder_id
            ),
            "clickup_list": (
                clickup_result["list"]
            ),
            "total_logo_files": len(
                logo_files
            ),
            **plan,
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=(
                error.response.status_code
            ),
            detail=error.response.text,
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@app.post("/render-one")
async def render_one(
    background_tasks: BackgroundTasks,
    source_video: UploadFile = File(...),
    logo_file: UploadFile = File(...),
    output_file_name: str = Form(...),
    x_api_key: str | None = Header(
        default=None
    ),
):
    """
    Receive one video and one full-frame transparent
    logo image, render the result, and return an MP4.

    Google Drive downloading and uploading are handled
    by n8n, not by this endpoint.
    """

    verify_api_key(x_api_key)

    temp_directory = Path(
        tempfile.mkdtemp(
            prefix="render_",
            dir=str(
                settings.workspace_root
            ),
        )
    )

    try:
        output_name = safe_filename(
            output_file_name
        )

        source_extension = (
            Path(
                source_video.filename
                or "source.mp4"
            ).suffix
            or ".mp4"
        )

        logo_extension = (
            Path(
                logo_file.filename
                or "logo.png"
            ).suffix
            or ".png"
        )

        source_path = (
            temp_directory
            / f"source{source_extension}"
        )

        logo_path = (
            temp_directory
            / f"logo{logo_extension}"
        )

        output_path = (
            temp_directory
            / output_name
        )

        await save_upload_file(
            source_video,
            source_path,
        )

        await save_upload_file(
            logo_file,
            logo_path,
        )

        add_full_frame_logo(
            source_video=source_path,
            logo_file=logo_path,
            output_video=output_path,
        )

        if not output_path.exists():
            raise RuntimeError(
                "Rendered video was not created"
            )

        if output_path.stat().st_size == 0:
            raise RuntimeError(
                "Rendered video is empty"
            )

        background_tasks.add_task(
            shutil.rmtree,
            temp_directory,
            True,
        )

        return FileResponse(
            path=output_path,
            media_type="video/mp4",
            filename=output_name,
            background=background_tasks,
        )

    except RenderError as error:
        shutil.rmtree(
            temp_directory,
            ignore_errors=True,
        )

        raise HTTPException(
            status_code=500,
            detail=f"FFmpeg error: {error}",
        ) from error

    except Exception as error:
        shutil.rmtree(
            temp_directory,
            ignore_errors=True,
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error