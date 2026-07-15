import subprocess
from pathlib import Path


class RenderError(RuntimeError):
    pass


def run_command(
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    print("\nRunning FFmpeg command:", flush=True)
    print(
        " ".join(str(part) for part in command),
        flush=True,
    )

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        print(
            "\nFFmpeg error:",
            result.stderr,
            flush=True,
        )

        raise RenderError(
            result.stderr.strip()
            or "FFmpeg command failed"
        )

    return result


def check_ffmpeg() -> None:
    for command_name in ("ffmpeg", "ffprobe"):
        result = subprocess.run(
            [command_name, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RenderError(
                f"{command_name} was not found inside the container"
            )


def get_video_size(
    video_path: Path,
) -> tuple[int, int]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=s=x:p=0",
        str(video_path),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RenderError(
            f"Could not read video size: {result.stderr.strip()}"
        )

    width_text, height_text = result.stdout.strip().split("x")

    return int(width_text), int(height_text)


def add_full_frame_logo(
    source_video: Path,
    logo_file: Path,
    output_video: Path,
) -> Path:
    if not source_video.exists():
        raise FileNotFoundError(
            f"Source video not found: {source_video}"
        )

    if not logo_file.exists():
        raise FileNotFoundError(
            f"Logo file not found: {logo_file}"
        )

    output_video.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    video_width, video_height = get_video_size(
        source_video
    )

    print(
        f"\nOverlay input video size: "
        f"{video_width}x{video_height}",
        flush=True,
    )

    print(
        f"Overlay image file: {logo_file}",
        flush=True,
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
            f"[1:v]"
            f"scale={video_width}:{video_height},"
            f"format=rgba"
            f"[ovr];"
            f"[0:v]"
            f"format=rgba"
            f"[base];"
            f"[base][ovr]"
            f"overlay=0:0:"
            f"format=auto"
            f"[v]"
        ),
        "-map",
        "[v]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output_video),
    ]

    run_command(command)

    if not output_video.exists():
        raise RenderError(
            "FFmpeg did not create the output file"
        )

    if output_video.stat().st_size == 0:
        raise RenderError(
            "FFmpeg created an empty output file"
        )

    return output_video