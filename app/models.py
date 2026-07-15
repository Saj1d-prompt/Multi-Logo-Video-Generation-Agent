from typing import Literal

from pydantic import BaseModel


class RenderSettings(BaseModel):
    existing_policy: Literal[
        "skip",
        "overwrite",
        "version",
    ] = "skip"


class BatchRequest(BaseModel):
    video_folder_id: str
    assets_folder_id: str
    output_folder_id: str

    clickup_workspace_id: str
    clickup_list_name: str

    render_settings: RenderSettings = RenderSettings()