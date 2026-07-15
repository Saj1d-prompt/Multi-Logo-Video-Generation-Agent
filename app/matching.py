from pathlib import Path
from typing import Any


def get_file_stem(file_name: str) -> str:
    """
    Removes only the final file extension.

    Examples:
    Video01.mp4 -> Video01
    Video-01.mp4 -> Video-01
    Sticker Visa.png -> Sticker Visa
    """

    return Path(file_name).stem


def build_task_index(
    tasks: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Creates an exact, case-sensitive task-name index.
    """

    index: dict[str, list[dict[str, Any]]] = {}

    for task in tasks:
        task_name = task.get("name")

        if not task_name:
            continue

        index.setdefault(
            task_name,
            [],
        ).append(task)

    return index


def build_logo_index(
    logo_files: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Creates an exact, case-sensitive logo index.

    The logo extension is removed before indexing.
    """

    index: dict[str, list[dict[str, Any]]] = {}

    for logo in logo_files:
        logo_name = logo.get("name")

        if not logo_name:
            continue

        logo_stem = get_file_stem(
            logo_name
        )

        index.setdefault(
            logo_stem,
            [],
        ).append(logo)

    return index


def match_video_to_task_and_logos(
    video: dict[str, Any],
    task_index: dict[str, list[dict[str, Any]]],
    logo_index: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    video_name = video.get("name", "")
    video_stem = get_file_stem(
        video_name
    )

    matching_tasks = task_index.get(
        video_stem,
        [],
    )

    if not matching_tasks:
        return {
            "status": "skipped",
            "reason": "clickup_task_not_found",
            "expected_task_name": video_stem,
            "video": video,
        }

    if len(matching_tasks) > 1:
        return {
            "status": "conflict",
            "reason": "duplicate_clickup_tasks",
            "expected_task_name": video_stem,
            "video": video,
            "matching_tasks": matching_tasks,
        }

    task = matching_tasks[0]

    matched_logos: list[dict[str, Any]] = []
    unmatched_tags: list[str] = []
    duplicate_logo_tags: list[dict[str, Any]] = []

    for tag_name in task.get(
        "tags",
        [],
    ):
        logo_matches = logo_index.get(
            tag_name,
            [],
        )

        if len(logo_matches) == 1:
            matched_logos.append(
                logo_matches[0]
            )

        elif len(logo_matches) > 1:
            duplicate_logo_tags.append({
                "tag": tag_name,
                "matches": logo_matches,
            })

        else:
            unmatched_tags.append(
                tag_name
            )

    if duplicate_logo_tags:
        return {
            "status": "conflict",
            "reason": "duplicate_logo_files",
            "video": video,
            "task": task,
            "duplicate_logo_tags": (
                duplicate_logo_tags
            ),
            "unmatched_tags": (
                unmatched_tags
            ),
        }

    if not matched_logos:
        return {
            "status": "skipped",
            "reason": "no_matching_logo",
            "video": video,
            "task": task,
            "unmatched_tags": (
                unmatched_tags
            ),
        }

    planned_outputs = []

    for logo in matched_logos:
        logo_stem = get_file_stem(
            logo["name"]
        )

        planned_outputs.append(
            f"{video_stem}__{logo_stem}.mp4"
        )

    return {
        "status": "ready",
        "video": video,
        "task": task,
        "matched_logos": matched_logos,
        "unmatched_tags": unmatched_tags,
        "planned_outputs": planned_outputs,
    }


def build_dry_run_plan(
    videos: list[dict[str, Any]],
    logo_files: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    task_index = build_task_index(
        tasks
    )

    logo_index = build_logo_index(
        logo_files
    )

    items = [
        match_video_to_task_and_logos(
            video=video,
            task_index=task_index,
            logo_index=logo_index,
        )
        for video in videos
    ]

    ready_items = [
        item
        for item in items
        if item["status"] == "ready"
    ]

    skipped_items = [
        item
        for item in items
        if item["status"] == "skipped"
    ]

    conflict_items = [
        item
        for item in items
        if item["status"] == "conflict"
    ]

    planned_output_count = sum(
        len(
            item.get(
                "planned_outputs",
                [],
            )
        )
        for item in ready_items
    )

    return {
        "matching_mode": (
            "exact_case_sensitive"
        ),
        "total_videos": len(videos),
        "ready_videos": len(
            ready_items
        ),
        "skipped_videos": len(
            skipped_items
        ),
        "conflict_videos": len(
            conflict_items
        ),
        "planned_outputs": (
            planned_output_count
        ),
        "items": items,
    }