import subprocess
from pathlib import Path


class RenderError(RuntimeError):
    pass


def run_command(
    command: list[str],
) -> None:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RenderError(
            result.stderr.strip()
            or "FFmpeg command failed"
        )


def check_ffmpeg() -> None:
    run_command([
        "ffmpeg",
        "-version",
    ])


def add_full_frame_logo(
    source_video: Path,
    logo_file: Path,
    output_video: Path,
) -> Path:
    """
    Overlay a transparent full-frame 9:16 image
    onto a 9:16 source video.

    The image already contains the logo in its final
    fixed position, so the overlay coordinates are 0:0.
    """

    if not source_video.exists():
        raise FileNotFoundError(
            f"Source video not found: "
            f"{source_video}"
        )

    if not logo_file.exists():
        raise FileNotFoundError(
            f"Logo file not found: "
            f"{logo_file}"
        )

    output_video.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_video),
        "-i",
        str(logo_file),
        "-filter_complex",
        (
            "[1:v]format=rgba[logo];"
            "[0:v][logo]"
            "overlay=0:0:"
            "format=auto[outv]"
        ),
        "-map",
        "[outv]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(output_video),
    ]

    run_command(command)

    if not output_video.exists():
        raise RenderError(
            "FFmpeg completed without "
            "creating the output file"
        )

    if output_video.stat().st_size == 0:
        raise RenderError(
            "FFmpeg created an empty output file"
        )

    return output_video