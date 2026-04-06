# -*- coding: utf-8 -*-
"""
video_concat.py
===============
Nối video tự động theo thứ tự.

Tính năng:
  - Nhập số video cần nối (vd: 4 → lấy 4 video liên tiếp nối thành 1)
  - Kiểm tra đúng thứ tự, báo thiếu cảnh nếu không đủ
  - Hỗ trợ nối nhiều nhóm liên tiếp (batch)
  - Sử dụng concat demuxer (stream copy) → cực nhanh, không re-encode

Cách dùng:
  from video_concat import VideoConcat

  vc = VideoConcat()
  vc.concat_group(
      video_dir="D:/videos",
      group_size=4,
      output_dir="D:/output"
  )
"""

import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from ffmpeg_utils import get_ffmpeg, get_video_info, run_ffmpeg


class VideoConcat:
    """Nối video tự động theo nhóm, đúng thứ tự."""

    def __init__(self, log_callback=None):
        """
        Args:
            log_callback: hàm nhận string log (nếu None → print)
        """
        self._log = log_callback or print
        self._ffmpeg = get_ffmpeg()

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log(f"[{ts}] {msg}")

    # ────────────────────────────────────────────────────────
    # SCAN VIDEO FILES
    # ────────────────────────────────────────────────────────
    def scan_videos(self, video_dir: str | Path, extension: str = ".mp4") -> list[Path]:
        """
        Quét folder video và sắp xếp theo số thứ tự ở đầu tên file.
        Ví dụ: 1_xxx.mp4, 2_xxx.mp4, 3_xxx.mp4, ...
        """
        video_dir = Path(video_dir)
        if not video_dir.exists():
            raise FileNotFoundError(f"Folder không tồn tại: {video_dir}")

        files = sorted(video_dir.glob(f"*{extension}"))
        if not files:
            raise FileNotFoundError(f"Không tìm thấy video {extension} trong: {video_dir}")

        # Sắp xếp theo số ở đầu tên file
        def extract_number(p: Path) -> int:
            match = re.match(r"^(\d+)", p.stem)
            return int(match.group(1)) if match else 9999

        files.sort(key=extract_number)
        return files

    def _get_file_number(self, path: Path) -> int | None:
        """Trích xuất số thứ tự từ tên file."""
        match = re.match(r"^(\d+)", path.stem)
        return int(match.group(1)) if match else None

    # ────────────────────────────────────────────────────────
    # GROUP VIDEOS
    # ────────────────────────────────────────────────────────
    def group_videos(
        self,
        video_dir: str | Path,
        group_size: int,
        extension: str = ".mp4",
    ) -> list[dict]:
        """
        Chia video thành các nhóm theo group_size.
        
        Trả về: list[{
            "group_index": int,          # nhóm thứ mấy (0-based)
            "expected_numbers": [int],   # số thứ tự mong đợi
            "videos": [Path | None],     # video tìm được (None = thiếu)
            "missing": [int],            # danh sách số bị thiếu
            "complete": bool,            # True nếu đủ video
        }]
        """
        all_files = self.scan_videos(video_dir, extension)
        
        # Tạo mapping: số → path
        number_to_file = {}
        for f in all_files:
            num = self._get_file_number(f)
            if num is not None:
                number_to_file[num] = f

        # Tìm số lớn nhất
        max_num = max(number_to_file.keys()) if number_to_file else 0
        total_groups = (max_num + group_size - 1) // group_size

        groups = []
        for gi in range(total_groups):
            start = gi * group_size + 1
            expected = list(range(start, start + group_size))
            
            videos = []
            missing = []
            for num in expected:
                if num in number_to_file:
                    videos.append(number_to_file[num])
                else:
                    videos.append(None)
                    missing.append(num)

            groups.append({
                "group_index": gi,
                "expected_numbers": expected,
                "videos": videos,
                "missing": missing,
                "complete": len(missing) == 0,
            })

        return groups

    # ────────────────────────────────────────────────────────
    # CONCAT MỘT NHÓM
    # ────────────────────────────────────────────────────────
    def concat_single_group(
        self,
        video_paths: list[Path],
        output_path: str | Path,
        re_encode: bool = False,
    ) -> Path:
        """
        Nối danh sách video thành 1 file.
        
        Args:
            video_paths: danh sách video (phải đầy đủ, không None)
            output_path: đường dẫn file output
            re_encode: True = re-encode (chậm nhưng đồng bộ codec), 
                        False = stream copy (nhanh)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if len(video_paths) == 1:
            # Chỉ 1 video → copy trực tiếp
            shutil.copy2(video_paths[0], output_path)
            self.log(f"   📎 Chỉ 1 video → copy: {output_path.name}")
            return output_path

        # Tạo file danh sách concat
        list_file = output_path.parent / f"_concat_{output_path.stem}.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for p in video_paths:
                f.write(f"file '{str(p).replace(chr(92), '/')}'\n")

        if re_encode:
            # Re-encode: chậm hơn nhưng đảm bảo đồng bộ codec
            cmd = [
                self._ffmpeg, "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                str(output_path),
            ]
        else:
            # Stream copy: cực nhanh
            cmd = [
                self._ffmpeg, "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                str(output_path),
            ]

        try:
            run_ffmpeg(cmd)
        finally:
            list_file.unlink(missing_ok=True)

        return output_path

    # ────────────────────────────────────────────────────────
    # BATCH CONCAT
    # ────────────────────────────────────────────────────────
    def concat_group(
        self,
        video_dir: str | Path,
        group_size: int,
        output_dir: str | Path,
        extension: str = ".mp4",
        re_encode: bool = False,
        name_prefix: str = "merged",
        stop_flag: list | None = None,
    ) -> list[dict]:
        """
        Chia video trong folder thành nhóm theo group_size rồi nối.
        
        Args:
            video_dir: folder chứa video nguồn
            group_size: số video mỗi nhóm
            output_dir: folder lưu output
            re_encode: True = re-encode
            name_prefix: tiền tố tên file output
            stop_flag: [bool] — set True để dừng giữa chừng
            
        Returns:
            list[{group_index, status, output_path, missing}]
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        self.log(f"📂 Quét video: {video_dir}")
        groups = self.group_videos(video_dir, group_size, extension)
        self.log(f"   ✅ Tìm thấy {len(groups)} nhóm (mỗi nhóm {group_size} video)")

        results = []

        for grp in groups:
            if stop_flag and stop_flag[0]:
                self.log("⏹ Đã dừng bởi người dùng.")
                break

            gi = grp["group_index"]
            nums = grp["expected_numbers"]
            self.log(f"\n─── Nhóm {gi + 1}: video #{nums[0]}–#{nums[-1]} ───")

            if not grp["complete"]:
                self.log(f"   ⚠️  THIẾU CẢNH: {grp['missing']}")
                results.append({
                    "group_index": gi,
                    "status": f"thiếu cảnh: {grp['missing']}",
                    "output_path": None,
                    "missing": grp["missing"],
                })
                continue

            # Log danh sách video
            for v in grp["videos"]:
                self.log(f"   • {v.name}")

            output_name = f"{name_prefix}_{gi + 1:03d}.mp4"
            output_path = output_dir / output_name

            try:
                self.concat_single_group(grp["videos"], output_path, re_encode)
                self.log(f"   ✅ Xong → {output_name}")
                results.append({
                    "group_index": gi,
                    "status": "OK",
                    "output_path": str(output_path),
                    "missing": [],
                })
            except Exception as e:
                self.log(f"   ❌ Lỗi: {e}")
                results.append({
                    "group_index": gi,
                    "status": f"lỗi: {str(e)[:100]}",
                    "output_path": None,
                    "missing": [],
                })

        # Tổng kết
        ok = sum(1 for r in results if r["status"] == "OK")
        fail = len(results) - ok
        self.log(f"\n{'='*50}")
        self.log(f"✅ Thành công: {ok} | ⚠️ Lỗi/Thiếu: {fail}")
        self.log(f"📁 Output: {output_dir}")

        return results


# ════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    print("=" * 55)
    print("  VIDEO CONCAT TOOL — Nối video tự động")
    print("=" * 55)

    # Config mặc định — thay đổi tùy ý
    VIDEO_DIR = input("📂 Folder video: ").strip() or "."
    GROUP_SIZE = int(input("📊 Số video mỗi nhóm (vd: 4): ").strip() or "4")
    OUTPUT_DIR = input("📁 Folder output (Enter = ./output/concat): ").strip()
    if not OUTPUT_DIR:
        OUTPUT_DIR = str(Path(VIDEO_DIR) / "output" / "concat")

    vc = VideoConcat()
    results = vc.concat_group(
        video_dir=VIDEO_DIR,
        group_size=GROUP_SIZE,
        output_dir=OUTPUT_DIR,
    )
