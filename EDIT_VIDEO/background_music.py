# -*- coding: utf-8 -*-
"""
background_music.py
===================
Chèn nhạc nền vào video tự động.

Tính năng:
  - Tự động cắt nhạc vừa với thời lượng video
  - Chọn đoạn nhạc muốn dùng (start → end)
  - Loop nhạc nếu video dài hơn nhạc
  - Điều chỉnh âm lượng nhạc nền (không lấn át giọng nói)
  - Hỗ trợ fade in/out nhạc
  - Nghe thử đoạn nhạc đã chọn trước khi áp dụng

Cách dùng:
  from background_music import BackgroundMusic

  bgm = BackgroundMusic()
  bgm.add_music(
      video_path="video.mp4",
      music_path="music.mp3",
      output_path="output.mp4",
      music_volume=0.3,
  )
"""

import subprocess
import os
from pathlib import Path
from datetime import datetime

from ffmpeg_utils import (
    get_ffmpeg, get_ffplay, get_video_duration, get_video_info, 
    run_ffmpeg, format_time,
)


class BackgroundMusic:
    """Chèn nhạc nền vào video."""

    def __init__(self, log_callback=None):
        self._log = log_callback or print
        self._ffmpeg = get_ffmpeg()
        self._preview_process = None  # process ffplay đang chạy

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log(f"[{ts}] {msg}")

    # ────────────────────────────────────────────────────────
    # LẤY THÔNG TIN NHẠC
    # ────────────────────────────────────────────────────────
    def get_music_info(self, music_path: str | Path) -> dict:
        """Lấy thông tin file nhạc: duration, codec, sample_rate."""
        return get_video_info(music_path)

    # ────────────────────────────────────────────────────────
    # NGHE THỬ ĐOẠN NHẠC
    # ────────────────────────────────────────────────────────
    def preview_music(
        self,
        music_path: str | Path,
        start_time: float = 0,
        duration: float = 10,
        volume: float = 1.0,
    ):
        """
        Nghe thử đoạn nhạc bằng ffplay.
        
        Args:
            music_path: file nhạc
            start_time: thời điểm bắt đầu (giây)
            duration: thời lượng nghe (giây)
            volume: âm lượng (0.0 → 1.0)
        """
        self.stop_preview()  # Dừng preview cũ nếu có

        try:
            ffplay = get_ffplay()
        except RuntimeError:
            self.log("⚠️ Không tìm thấy ffplay! Không thể nghe thử.")
            return

        self.log(f"🔊 Nghe thử: {Path(music_path).name} [{format_time(start_time)} → {format_time(start_time + duration)}]")

        af_parts = []
        if volume != 1.0:
            af_parts.append(f"volume={volume}")
        af = ",".join(af_parts) if af_parts else None

        cmd = [
            ffplay, "-nodisp", "-autoexit",
            "-ss", str(start_time),
            "-t", str(duration),
        ]
        if af:
            cmd.extend(["-af", af])
        cmd.append(str(music_path))

        self._preview_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    def stop_preview(self):
        """Dừng preview đang phát."""
        if self._preview_process and self._preview_process.poll() is None:
            self._preview_process.terminate()
            try:
                self._preview_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._preview_process.kill()
            self._preview_process = None

    def is_previewing(self) -> bool:
        """Kiểm tra có đang preview không."""
        return self._preview_process is not None and self._preview_process.poll() is None

    # ────────────────────────────────────────────────────────
    # CHÈN NHẠC NỀN
    # ────────────────────────────────────────────────────────
    def add_music(
        self,
        video_path: str | Path,
        music_path: str | Path,
        output_path: str | Path,
        music_volume: float = 0.3,
        original_volume: float = 1.0,
        music_start: float = 0,
        music_end: float | None = None,
        fade_in: float = 1.0,
        fade_out: float = 2.0,
        loop_music: bool = True,
    ) -> Path:
        """
        Chèn nhạc nền vào video.
        
        Args:
            video_path: video gốc
            music_path: file nhạc
            output_path: video output
            music_volume: âm lượng nhạc nền (0.0 → 1.0, khuyến nghị 0.2–0.4)
            original_volume: âm lượng audio gốc (1.0 = giữ nguyên)
            music_start: thời điểm bắt đầu lấy nhạc (giây)
            music_end: thời điểm kết thúc lấy nhạc (None = tự cắt theo video)
            fade_in: thời gian fade in nhạc (giây, 0=tắt)
            fade_out: thời gian fade out nhạc (giây, 0=tắt)
            loop_music: True = loop nhạc nếu video dài hơn
            
        Returns:
            Path đến video output
        """
        video_path = Path(video_path)
        music_path = Path(music_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Lấy thông tin
        video_duration = get_video_duration(video_path)
        music_duration = get_video_duration(music_path)

        self.log(f"🎬 Video: {video_path.name} ({video_duration:.1f}s)")
        self.log(f"🎵 Nhạc: {music_path.name} ({music_duration:.1f}s)")

        # Tính thời lượng nhạc cần dùng
        if music_end is not None:
            usable_duration = music_end - music_start
        else:
            usable_duration = music_duration - music_start

        # ── Build filter complex ──
        input_args = ["-i", str(video_path)]
        
        # Input nhạc: cắt từ music_start
        if music_start > 0:
            input_args.extend(["-ss", str(music_start)])
        
        if loop_music and usable_duration < video_duration:
            # Loop nhạc
            input_args.extend(["-stream_loop", "-1"])
        
        if music_end is not None:
            input_args.extend(["-t", str(usable_duration)])
        
        input_args.extend(["-i", str(music_path)])

        # Audio filter graph
        af_parts_music = []
        
        # Cắt nhạc vừa video
        af_parts_music.append(f"atrim=0:{video_duration}")
        af_parts_music.append(f"asetpts=PTS-STARTPTS")
        
        # Âm lượng nhạc
        af_parts_music.append(f"volume={music_volume}")
        
        # Fade in/out
        if fade_in > 0:
            af_parts_music.append(f"afade=t=in:st=0:d={fade_in}")
        if fade_out > 0:
            fade_out_start = max(0, video_duration - fade_out)
            af_parts_music.append(f"afade=t=out:st={fade_out_start}:d={fade_out}")

        music_filter = ",".join(af_parts_music)

        # Kiểm tra video có audio gốc không
        video_info = get_video_info(video_path)
        has_audio = "audio_codec" in video_info

        if has_audio:
            # Mix audio gốc + nhạc nền
            filter_complex = (
                f"[0:a]volume={original_volume}[orig];"
                f"[1:a]{music_filter}[bgm];"
                f"[orig][bgm]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
            )
            map_args = ["-map", "0:v", "-map", "[aout]"]
        else:
            # Video không có audio → chỉ dùng nhạc nền
            filter_complex = f"[1:a]{music_filter}[aout]"
            map_args = ["-map", "0:v", "-map", "[aout]"]

        cmd = [
            self._ffmpeg, "-y",
            *input_args,
            "-filter_complex", filter_complex,
            *map_args,
            "-c:v", "copy",           # Giữ nguyên video, không re-encode
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]

        self.log(f"⏳ Đang chèn nhạc nền...")

        try:
            run_ffmpeg(cmd)
            self.log(f"✅ Xong → {output_path.name}")
        except RuntimeError as e:
            self.log(f"❌ Lỗi: {e}")
            raise

        return output_path

    # ────────────────────────────────────────────────────────
    # CHÈN NHẠC NỀN BATCH
    # ────────────────────────────────────────────────────────
    def batch_add_music(
        self,
        video_dir: str | Path,
        music_path: str | Path,
        output_dir: str | Path,
        music_volume: float = 0.3,
        music_start: float = 0,
        music_end: float | None = None,
        fade_in: float = 1.0,
        fade_out: float = 2.0,
        extension: str = ".mp4",
        stop_flag: list | None = None,
    ) -> list[dict]:
        """
        Chèn nhạc nền cho tất cả video trong folder.
        
        Returns:
            list[{video, output, status}]
        """
        video_dir = Path(video_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        videos = sorted(video_dir.glob(f"*{extension}"))
        if not videos:
            self.log(f"⚠️ Không tìm thấy video trong: {video_dir}")
            return []

        self.log(f"📂 Tìm thấy {len(videos)} video")
        self.log(f"🎵 Nhạc: {Path(music_path).name}")

        results = []
        for vi, vpath in enumerate(videos):
            if stop_flag and stop_flag[0]:
                self.log("⏹ Đã dừng.")
                break

            out_name = f"{vpath.stem}_bgm{vpath.suffix}"
            out_path = output_dir / out_name

            self.log(f"\n[{vi+1}/{len(videos)}] {vpath.name}")

            try:
                self.add_music(
                    video_path=vpath,
                    music_path=music_path,
                    output_path=out_path,
                    music_volume=music_volume,
                    music_start=music_start,
                    music_end=music_end,
                    fade_in=fade_in,
                    fade_out=fade_out,
                )
                results.append({
                    "video": str(vpath),
                    "output": str(out_path),
                    "status": "OK",
                })
            except Exception as e:
                self.log(f"   ❌ Lỗi: {e}")
                results.append({
                    "video": str(vpath),
                    "output": None,
                    "status": f"lỗi: {str(e)[:100]}",
                })

        ok = sum(1 for r in results if r["status"] == "OK")
        self.log(f"\n{'='*50}")
        self.log(f"✅ Thành công: {ok}/{len(results)}")
        return results

    # ────────────────────────────────────────────────────────
    # TÁCH AUDIO TỪ VIDEO
    # ────────────────────────────────────────────────────────
    def extract_audio(
        self,
        video_path: str | Path,
        output_path: str | Path = None,
        audio_format: str = "mp3",
    ) -> Path:
        """Tách audio từ video."""
        video_path = Path(video_path)
        if output_path is None:
            output_path = video_path.with_suffix(f".{audio_format}")
        output_path = Path(output_path)

        cmd = [
            self._ffmpeg, "-y",
            "-i", str(video_path),
            "-vn",  # bỏ video
            "-c:a", "libmp3lame" if audio_format == "mp3" else "aac",
            "-b:a", "192k",
            str(output_path),
        ]

        run_ffmpeg(cmd)
        self.log(f"✅ Tách audio → {output_path.name}")
        return output_path

    # ────────────────────────────────────────────────────────
    # XÓA AUDIO GỐC
    # ────────────────────────────────────────────────────────
    def remove_audio(
        self,
        video_path: str | Path,
        output_path: str | Path = None,
    ) -> Path:
        """Xóa toàn bộ audio khỏi video."""
        video_path = Path(video_path)
        if output_path is None:
            output_path = video_path.parent / f"{video_path.stem}_noaudio{video_path.suffix}"
        output_path = Path(output_path)

        cmd = [
            self._ffmpeg, "-y",
            "-i", str(video_path),
            "-an",  # bỏ audio
            "-c:v", "copy",
            str(output_path),
        ]

        run_ffmpeg(cmd)
        self.log(f"✅ Xóa audio → {output_path.name}")
        return output_path


# ════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    print("=" * 55)
    print("  BACKGROUND MUSIC — Chèn nhạc nền vào video")
    print("=" * 55)

    video = input("🎬 File video: ").strip()
    music = input("🎵 File nhạc: ").strip()
    if not video or not music:
        print("❌ Chưa nhập video hoặc nhạc!")
        sys.exit(1)

    vol = input("🔊 Âm lượng nhạc (0.0-1.0, mặc định 0.3): ").strip()
    volume = float(vol) if vol else 0.3

    output = str(Path(video).stem) + "_bgm.mp4"

    bgm = BackgroundMusic()
    
    # Cho nghe thử 10 giây trước
    preview = input("🔊 Nghe thử 10s nhạc? (y/n): ").strip().lower()
    if preview == "y":
        bgm.preview_music(music, start_time=0, duration=10, volume=volume)
        input("   Nhấn Enter để tiếp tục...")
        bgm.stop_preview()

    bgm.add_music(
        video_path=video,
        music_path=music,
        output_path=output,
        music_volume=volume,
    )
