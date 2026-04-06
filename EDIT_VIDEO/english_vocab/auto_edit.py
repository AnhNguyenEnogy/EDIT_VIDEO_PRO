# -*- coding: utf-8 -*-
"""
auto_edit.py
============
Dùng FFmpeg trực tiếp (nhanh hơn MoviePy x10-20):
  - drawtext filter: chèn text có viền chữ, KHÔNG nền màu
  - 0–4s hiện từ 1, 4–8s hiện từ 2
  - Ghép tất cả video bằng concat demuxer

Cách dùng:
  .venv/Scripts/python.exe auto_edit.py
"""

import sys, subprocess, tempfile, os, shutil
from pathlib import Path

# ════════════════════════════════════════════════════════════
# CẤU HÌNH
# ════════════════════════════════════════════════════════════
VIDEO_DIR = Path(__file__).parent

VIDEO_FILES = [
    "1_1_20032026_091309.mp4",
    "2_1_20032026_091326.mp4",
    "3_1_20032026_124851.mp4",
    "4_1_20032026_091416.mp4",
]

VOCAB_PER_SCENE = [
    [
        {"vi": "Kem đánh răng", "en": "Toothpaste", "ipa": "/'tuːθ.peɪst/"},
        {"vi": "Khăn tắm",      "en": "Towel",      "ipa": "/'taʊ.əl/"},
    ],
    [
        {"vi": "Lược",     "en": "Comb",       "ipa": "/koʊm/"},
        {"vi": "Bàn chải", "en": "Toothbrush", "ipa": "/'tuːθ.brʌʃ/"},
    ],
    [
        {"vi": "Xà phòng", "en": "Soap",     "ipa": "/soʊp/"},
        {"vi": "Kéo",      "en": "Scissors", "ipa": "/'sɪz.ərz/"},
    ],
    [],  # Scene 4 CTA
]

SWITCH_TIME   = 4.0   # giây chuyển từ 1 sang từ 2

# ── Style text ──────────────────────────────────────────────
FONT_BOLD   = r"C\:/Windows/Fonts/arialbd.ttf"   # FFmpeg cần dấu \: cho Windows path
FONT_ITALIC = r"C\:/Windows/Fonts/ariali.ttf"

SIZE_VI     = 62   # font size tiếng Việt
SIZE_EN     = 62   # font size tiếng Anh
SIZE_IPA    = 50   # font size IPA

# Màu hex (tránh chroma bleeding khi dùng tên màu)
# yellow = FFD700, white = FFFFFF, orange = FFA500, cyan = 00FFFF
COLOR_TEXT   = "0xFFD700"   # Vàng sắc nét
COLOR_BORDER = "0x000000"   # Viền đen
BORDER_W     = 4            # Độ dày viền (px)

# Vị trí Y — tính từ dưới lên (px), video cao 1280px
# Thứ tự từ dưới: IPA → EN → VI
Y_IPA = 1130   # IPA dòng thấp nhất
Y_EN  = 1058   # EN
Y_VI  = 988    # Tiếng Việt — dòng cao nhất


# ════════════════════════════════════════════════════════════
# TÌM FFMPEG
# ════════════════════════════════════════════════════════════
def get_ffmpeg() -> str:
    """Lấy đường dẫn ffmpeg — ưu tiên local folder, fallback system."""
    # Ưu tiên ffmpeg trong thư mục project gốc
    local_ff = Path(__file__).parent.parent / "ffmpeg" / "ffmpeg.exe"
    if local_ff.exists():
        return str(local_ff)
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    raise RuntimeError(
        "Không tìm thấy ffmpeg! Hãy đặt ffmpeg.exe vào folder ffmpeg/"
    )


# ════════════════════════════════════════════════════════════
# TẠO DRAWTEXT FILTER
# ════════════════════════════════════════════════════════════
def esc(s: str) -> str:
    """Escape text cho FFmpeg drawtext: \ : ' = đặc biệt."""
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\u2019")   # thay apostrophe thẳng bằng curly
    s = s.replace(":", "\\:")
    return s


def build_drawtext(vi_text, en_text, ipa_text, t_start, t_end) -> str:
    """Tạo chuỗi 3 drawtext filter (VI + EN + IPA) có enable theo thời gian."""
    enable = f"between(t\\,{t_start}\\,{t_end})"

    def dt(text, font, size, y):
        return (
            f"drawtext=fontfile='{font}'"
            f":text='{esc(text)}'"
            f":fontsize={size}"
            f":fontcolor={COLOR_TEXT}"
            f":bordercolor={COLOR_BORDER}"
            f":borderw={BORDER_W}"
            f":x=(w-text_w)/2"
            f":y={y}"
            f":enable='{enable}'"
        )

    filters = [
        dt(vi_text,  FONT_BOLD,   SIZE_VI,  Y_VI),
        dt(en_text,  FONT_BOLD,   SIZE_EN,  Y_EN),
        dt(ipa_text, FONT_ITALIC, SIZE_IPA, Y_IPA),
    ]
    return ",".join(filters)


# ════════════════════════════════════════════════════════════
# XỬ LÝ 1 VIDEO: thêm drawtext → temp file
# ════════════════════════════════════════════════════════════
def process_video(ffmpeg: str, src: Path, vocab: list, out: Path) -> Path:
    """
    Nếu vocab rỗng → copy thẳng (không re-encode).
    Nếu có vocab → dùng drawtext filter.
    """
    if not vocab:
        # Không có text → giữ nguyên, không re-encode
        print(f"   ℹ️  Không có từ vựng — copy giữ nguyên")
        shutil.copy2(src, out)
        return out

    # Xây filter chuỗi cho 2 từ theo thời gian
    filters_parts = []

    if len(vocab) >= 1:
        v = vocab[0]
        filters_parts.append(
            build_drawtext(v["vi"], v["en"], v["ipa"], 0, SWITCH_TIME)
        )
        print(f"   📝 0–{SWITCH_TIME}s → {v['vi']} / {v['en']}")

    if len(vocab) >= 2:
        v = vocab[1]
        filters_parts.append(
            build_drawtext(v["vi"], v["en"], v["ipa"], SWITCH_TIME, 99)
        )
        print(f"   📝 {SWITCH_TIME}s–end → {v['vi']} / {v['en']}")

    vf = ",".join(filters_parts)

    cmd = [
        ffmpeg, "-y",
        "-i", str(src),
        "-vf", vf + ",format=yuv420p",  # fix chroma bleeding
        "-c:v", "libx264",
        "-preset", "medium",             # chất lượng tốt hơn fast
        "-crf", "15",                    # chất lượng cao (thấp = tốt hơn)
        "-pix_fmt", "yuv420p",           # chuẩn màu H.264
        "-color_range", "tv",            # color range chuẩn
        "-colorspace", "bt709",          # color space chuẩn
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-c:a", "copy",
        str(out),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(f"   ❌ FFmpeg lỗi:\n{result.stderr[-800:]}")
        raise RuntimeError(f"FFmpeg failed on {src.name}")

    return out


# ════════════════════════════════════════════════════════════
# GHÉP VIDEO BẰNG CONCAT DEMUXER
# ════════════════════════════════════════════════════════════
def concat_videos(ffmpeg: str, parts: list[Path], output: Path):
    """Ghép danh sách video bằng concat demuxer — nhanh, không re-encode."""
    list_file = output.parent / "concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in parts:
            # FFmpeg concat list cần forward slash
            f.write(f"file '{str(p).replace(chr(92), '/')}'\n")

    cmd = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",   # stream copy — cực nhanh
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    list_file.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"   ❌ Concat lỗi:\n{result.stderr[-800:]}")
        raise RuntimeError("FFmpeg concat failed")


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("  AUTO VIDEO EDITOR (FFmpeg) — Chèn text + Ghép video")
    print("=" * 60)

    ffmpeg = get_ffmpeg()
    print(f"\n🔧 FFmpeg: {ffmpeg}")

    # Kiểm tra video files
    video_paths = []
    for f in VIDEO_FILES:
        p = VIDEO_DIR / f
        if p.exists():
            video_paths.append(p)
        else:
            print(f"  ⚠️  Không tìm thấy: {f}")

    if not video_paths:
        print("❌ Không có video nào!")
        sys.exit(1)

    print(f"\n📂 {len(video_paths)} video:")
    for p in video_paths:
        print(f"   • {p.name}")

    output_dir = VIDEO_DIR / "output"
    output_dir.mkdir(exist_ok=True)
    tmp_dir    = output_dir / "_tmp"
    tmp_dir.mkdir(exist_ok=True)

    processed = []

    for vi, vpath in enumerate(video_paths):
        vocab   = VOCAB_PER_SCENE[vi] if vi < len(VOCAB_PER_SCENE) else []
        tmp_out = tmp_dir / f"part_{vi+1}.mp4"

        print(f"\n⏳ [{vi+1}/{len(video_paths)}] {vpath.name}")
        process_video(ffmpeg, vpath, vocab, tmp_out)
        processed.append(tmp_out)
        print(f"   ✅ Xong → {tmp_out.name}")

    # Ghép
    final_path = output_dir / "final_output.mp4"
    print(f"\n🔗 Ghép {len(processed)} clips → {final_path.name} ...")
    concat_videos(ffmpeg, processed, final_path)

    # Dọn temp
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n✅ HOÀN THÀNH!\n   {final_path}\n")


if __name__ == "__main__":
    main()
