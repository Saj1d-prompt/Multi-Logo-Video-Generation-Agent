from typing import Any

import httpx

from app.settings import settings


def get_clickup_headers() -> dict[str, str]:
    return {
        "Authorization": settings.clickup_api_token,
        "Content-Type": "application/json",
    }


def clickup_get(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{settings.clickup_api_base}{endpoint}"

    response = httpx.get(
        url,
        headers=get_clickup_headers(),
        params=params,
        timeout=60,
    )

    response.raise_for_status()
    return response.json()


def get_spaces(workspace_id: str) -> list[dict[str, Any]]:
    payload = clickup_get(
        f"/team/{workspace_id}/space",
        params={"archived": "false"},
    )

    return payload.get("spaces", [])


def get_folders(space_id: str) -> list[dict[str, Any]]:
    payload = clickup_get(
        f"/space/{space_id}/folder",
        params={"archived": "false"},
    )

    return payload.get("folders", [])


def get_folder_lists(folder_id: str) -> list[dict[str, Any]]:
    payload = clickup_get(
        f"/folder/{folder_id}/list",
        params={"archived": "false"},
    )

    return payload.get("lists", [])


def get_folderless_lists(space_id: str) -> list[dict[str, Any]]:
    payload = clickup_get(
        f"/space/{space_id}/list",
        params={"archived": "false"},
    )

    return payload.get("lists", [])


def discover_workspace_lists(
    workspace_id: str,
) -> list[dict[str, Any]]:
    discovered_lists: list[dict[str, Any]] = []

    for space in get_spaces(workspace_id):
        space_id = str(space["id"])

        # Lists placed directly inside the Space
        for clickup_list in get_folderless_lists(space_id):
            discovered_lists.append({
                "id": str(clickup_list.get("id")),
                "name": clickup_list.get("name"),
                "space_id": space_id,
                "space_name": space.get("name"),
                "folder_id": None,
                "folder_name": None,
            })

        # Lists placed inside Folders
        for folder in get_folders(space_id):
            folder_id = str(folder["id"])

            for clickup_list in get_folder_lists(folder_id):
                discovered_lists.append({
                    "id": str(clickup_list.get("id")),
                    "name": clickup_list.get("name"),
                    "space_id": space_id,
                    "space_name": space.get("name"),
                    "folder_id": folder_id,
                    "folder_name": folder.get("name"),
                })

    return discovered_lists


def find_list_by_name(
    workspace_id: str,
    list_name: str,
) -> dict[str, Any]:
    """
    Finds a ClickUp List using exact,
    case-sensitive name matching.
    """

    matching_lists = [
        item
        for item in discover_workspace_lists(
            workspace_id
        )
        if item.get("name") == list_name
    ]

    if not matching_lists:
        raise ValueError(
            f"ClickUp List not found with "
            f"exact name: {list_name}"
        )

    if len(matching_lists) > 1:
        matches = [
            {
                "id": item["id"],
                "name": item["name"],
                "space_name": (
                    item["space_name"]
                ),
                "folder_name": (
                    item["folder_name"]
                ),
            }
            for item in matching_lists
        ]

        raise ValueError(
            f"Multiple ClickUp Lists found "
            f"with the exact name "
            f"'{list_name}': {matches}"
        )

    return matching_lists[0]


def get_tasks_from_list(
    list_id: str,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    page = 0

    while True:
        payload = clickup_get(
            f"/list/{list_id}/task",
            params={
                "page": page,
                "include_closed": "true",
            },
        )

        page_tasks = payload.get("tasks", [])

        if not page_tasks:
            break

        tasks.extend(page_tasks)

        if len(page_tasks) < 100:
            break

        page += 1

    return tasks


def simplify_task(
    task: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "name": task.get("name"),
        "status": task.get("status", {}).get("status"),
        "tags": [
            tag.get("name")
            for tag in task.get("tags", [])
            if tag.get("name")
        ],
        "url": task.get("url"),
    }


def get_tasks_by_list_name(
    workspace_id: str,
    list_name: str,
) -> dict[str, Any]:
    matched_list = find_list_by_name(
        workspace_id=workspace_id,
        list_name=list_name,
    )

    tasks = get_tasks_from_list(
        matched_list["id"]
    )

    return {
        "list": matched_list,
        "tasks": [
            simplify_task(task)
            for task in tasks
        ],
    }