# -*- coding: utf-8 -*-
"""
ffmpeg_utils.py
===============
Tiện ích dùng chung cho FFmpeg: tìm đường dẫn, lấy thông tin video, escape text.
"""

import shutil
import subprocess
import json
from pathlib import Path


def get_ffmpeg() -> str:
    """Lấy đường dẫn ffmpeg — ưu tiên local folder, fallback system."""
    # Ưu tiên ffmpeg trong thư mục project
    local_ff = Path(__file__).parent / "ffmpeg" / "ffmpeg.exe"
    if local_ff.exists():
        return str(local_ff)

    ff = shutil.which("ffmpeg")
    if ff:
        return ff

    raise RuntimeError("Không tìm thấy ffmpeg! Hãy đặt ffmpeg.exe vào folder ffmpeg/")


def get_ffprobe() -> str:
    """Lấy đường dẫn ffprobe."""
    local_fp = Path(__file__).parent / "ffmpeg" / "ffprobe.exe"
    if local_fp.exists():
        return str(local_fp)

    fp = shutil.which("ffprobe")
    if fp:
        return fp

    raise RuntimeError("Không tìm thấy ffprobe!")


def get_ffplay() -> str:
    """Lấy đường dẫn ffplay."""
    local_fp = Path(__file__).parent / "ffmpeg" / "ffplay.exe"
    if local_fp.exists():
        return str(local_fp)

    fp = shutil.which("ffplay")
    if fp:
        return fp

    raise RuntimeError("Không tìm thấy ffplay!")


def get_video_duration(video_path: str | Path) -> float:
    """Lấy thời lượng video (giây)."""
    ffprobe = get_ffprobe()
    cmd = [
        ffprobe, "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe lỗi: {result.stderr[:300]}")

    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def get_video_info(video_path: str | Path) -> dict:
    """Lấy thông tin video đầy đủ: duration, width, height, fps, codec."""
    ffprobe = get_ffprobe()
    cmd = [
        ffprobe, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe lỗi: {result.stderr[:300]}")

    data = json.loads(result.stdout)
    info = {
        "duration": float(data["format"].get("duration", 0)),
        "size_bytes": int(data["format"].get("size", 0)),
    }

    for stream in data.get("streams", []):
        if stream["codec_type"] == "video":
            info["width"] = stream.get("width", 0)
            info["height"] = stream.get("height", 0)
            info["video_codec"] = stream.get("codec_name", "")
            # Parse fps
            fps_str = stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                info["fps"] = round(int(num) / max(int(den), 1), 2)
            else:
                info["fps"] = float(fps_str)
        elif stream["codec_type"] == "audio":
            info["audio_codec"] = stream.get("codec_name", "")
            info["sample_rate"] = stream.get("sample_rate", "")
            info["channels"] = stream.get("channels", 0)

    return info


def esc_ffmpeg(s: str) -> str:
    """Escape text cho FFmpeg drawtext filter."""
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\u2019")  # curly apostrophe
    s = s.replace(":", "\\:")
    return s


def run_ffmpeg(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Chạy lệnh FFmpeg và trả về kết quả."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg lỗi:\n{result.stderr[-800:]}")
    return result


def format_time(seconds: float) -> str:
    """Chuyển giây thành HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def format_time_srt(seconds: float) -> str:
    """Chuyển giây thành định dạng SRT: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    ms = int((s - int(s)) * 1000)
    return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"
