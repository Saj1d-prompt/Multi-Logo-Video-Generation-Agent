from typing import Literal

from pydantic import BaseModel, Field


class RenderSettings(BaseModel):
    bgm_volume: float = Field(
        default=0.08,
        ge=0,
        le=1
    )

    existing_policy: Literal[
        "skip",
        "overwrite",
        "version"
    ] = "skip"


class BatchRequest(BaseModel):
    video_folder_id: str
    logo_folder_id: str
    music_folder_id: str | None = None
    output_folder_id: str
    clickup_list_id: str

    render_settings: RenderSettings = RenderSettings()