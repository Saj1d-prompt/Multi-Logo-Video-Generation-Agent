import shutil
import uuid
from pathlib import Path
from typing import Any

from app.clickup_client import get_tasks_by_list_name
from app.drive_client import (
    download_file,
    find_file_by_exact_name,
    find_logo_folder,
    list_folder_files,
    upload_video,
)
from app.matching import build_dry_run_plan
from app.renderer import add_full_frame_logo, check_ffmpeg
from app.settings import settings


def process_batch(request) -> dict[str, Any]:
    check_ffmpeg()

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job_folder = (
        settings.workspace_root
        / "jobs"
        / job_id
    )

    downloads_folder = job_folder / "downloads"
    outputs_folder = job_folder / "outputs"

    downloads_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    outputs_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    try:
        video_files = [
            file
            for file in list_folder_files(
                request.video_folder_id
            )
            if file.get(
                "mimeType",
                "",
            ).startswith("video/")
        ]

        logo_folder = find_logo_folder(
            request.assets_folder_id
        )

        if not logo_folder:
            raise RuntimeError(
                "Logos folder not found"
            )

        logo_files = [
            file
            for file in list_folder_files(
                logo_folder["id"]
            )
            if file.get("mimeType") in {
                "image/png",
                "image/jpeg",
                "image/webp",
            }
        ]

        clickup_result = get_tasks_by_list_name(
            workspace_id=request.clickup_workspace_id,
            list_name=request.clickup_list_name,
        )

        plan = build_dry_run_plan(
            videos=video_files,
            logo_files=logo_files,
            tasks=clickup_result["tasks"],
        )

        for item in plan["items"]:
            if item["status"] != "ready":
                results.append(item)
                continue

            video = item["video"]

            local_video = (
                downloads_folder
                / video["name"]
            )

            download_file(
                video["id"],
                local_video,
            )

            variant_results = []

            for logo in item["matched_logos"]:
                output_name = next(
                    output
                    for output in item["planned_outputs"]
                    if Path(logo["name"]).stem
                    in output
                )

                existing = find_file_by_exact_name(
                    request.output_folder_id,
                    output_name,
                )

                if (
                    existing
                    and request.render_settings.existing_policy
                    == "skip"
                ):
                    variant_results.append({
                        "status": "skipped",
                        "reason": "output_exists",
                        "output_name": output_name,
                        "existing_file": existing,
                    })
                    continue

                local_logo = (
                    downloads_folder
                    / logo["name"]
                )

                download_file(
                    logo["id"],
                    local_logo,
                )

                local_output = (
                    outputs_folder
                    / output_name
                )

                try:
                    add_full_frame_logo(
                        source_video=local_video,
                        logo_file=local_logo,
                        output_video=local_output,
                    )

                    uploaded = upload_video(
                        local_output,
                        request.output_folder_id,
                    )

                    variant_results.append({
                        "status": "success",
                        "logo": logo["name"],
                        "output_name": output_name,
                        "uploaded_file": uploaded,
                    })

                except Exception as error:
                    variant_results.append({
                        "status": "failed",
                        "logo": logo["name"],
                        "output_name": output_name,
                        "error": str(error),
                    })

            results.append({
                "status": "processed",
                "video": video,
                "task": item["task"],
                "variants": variant_results,
            })

        return {
            "status": "success",
            "job_id": job_id,
            "dry_run_summary": {
                "total_videos": plan["total_videos"],
                "ready_videos": plan["ready_videos"],
                "planned_outputs": plan["planned_outputs"],
            },
            "results": results,
        }

    finally:
        shutil.rmtree(
            job_folder,
            ignore_errors=True,
        )