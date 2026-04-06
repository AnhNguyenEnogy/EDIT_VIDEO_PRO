# -*- coding: utf-8 -*-
"""
subtitle_worker.py
==================
Script chạy riêng trong subprocess để tạo phụ đề.
Tránh crash app chính nếu faster-whisper/CTranslate2 gặp lỗi native.

Nhận tham số qua JSON stdin, trả kết quả qua stdout.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Fix encoding Windows — subprocess mặc định dùng cp1252
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = json.dumps({"type": "log", "msg": f"[{ts}] {msg}"}, ensure_ascii=False)
    print(line, flush=True)


def main():
    # Đọc config từ argv
    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "msg": "Thiếu config JSON"}), flush=True)
        sys.exit(1)

    config = json.loads(sys.argv[1])
    video = config["video"]
    model_size = config.get("model", "medium")
    language = config.get("language", "auto")
    burn = config.get("burn", False)
    mode = config.get("mode", "single")

    # Style params
    font = config.get("font", "Arial")
    font_size = config.get("font_size", 24)
    font_color = config.get("font_color", "&HFFFFFF")
    bg_color = config.get("bg_color", "#000000")
    style_idx = config.get("style_idx", 0)
    position = config.get("position", "bottom")
    align = config.get("align", "center")
    fx = config.get("fx", "none")
    margin_v = config.get("margin_v", 30)
    x_offset = config.get("x_offset", 0)
    y_vi = config.get("y_vi")
    auto_y = config.get("auto_y", True)
    aspect_idx = config.get("aspect_idx", 0)  # 0=9:16, 1=16:9
    is_bold = config.get("is_bold", True)
    is_italic = config.get("is_italic", False)
    is_underline = config.get("is_underline", False)
    border_w = config.get("border_w", None)
    kara_run_color = config.get("kara_run_color", "#FFFF00")
    kara_bg_color = config.get("kara_bg_color", "#FFFFFF")

    try:
        from subtitle_generator import SubtitleGenerator
        sg = SubtitleGenerator(model_size=model_size, log_callback=log)

        video_path = Path(video)

        if mode == "single" and video_path.is_file():
            srt_path = video_path.with_suffix(".srt")
            sg.generate_srt(video_path, srt_path, language=language)

            if burn:
                out = video_path.parent / f"{video_path.stem}_sub{video_path.suffix}"

                # Xác định alignment ASS
                # ASS alignment: bottom(1,2,3), middle(4,5,6), top(7,8,9)
                # left=1/4/7, center=2/5/8, right=3/6/9
                pos_base = {"bottom": 0, "center": 3, "top": 6}.get(position, 0)
                align_offset = {"left": 1, "center": 2, "right": 3}.get(align, 2)
                ass_alignment = pos_base + align_offset

                if fx in ("karaoke", "word_pop", "firework", "popup", "fade", "typewriter", "bounce",
                          "slide_left", "slide_right", "glow"):
                    # Hiệu ứng nâng cao — dùng ASS file
                    sg.burn_subtitle_fx(
                        video_path, srt_path, out,
                        font_name=font, font_size=font_size,
                        font_color=font_color, bg_color=bg_color, style_idx=style_idx,
                        is_bold=is_bold, is_italic=is_italic, is_underline=is_underline, border_w=border_w,
                        position=position,
                        alignment=ass_alignment, fx=fx,
                        language=language, margin_v=margin_v,
                        x_offset=x_offset, y_vi=y_vi, auto_y=auto_y,
                        aspect_idx=aspect_idx,
                        kara_run_color=kara_run_color,
                        kara_bg_color=kara_bg_color,
                    )
                else:
                    # Burn bình thường
                    sg.burn_subtitle(
                        video_path, srt_path, out,
                        font_name=font, font_size=font_size,
                        font_color=font_color, bg_color=bg_color, style_idx=style_idx,
                        is_bold=is_bold, is_italic=is_italic, is_underline=is_underline, border_w=border_w,
                        position=position,
                        margin_v=margin_v,
                        x_offset=x_offset, y_vi=y_vi, auto_y=auto_y,
                        aspect_idx=aspect_idx,
                    )
                log(f"OK Burn xong -> {out.name}")

            result = {"type": "done", "srt": str(srt_path)}
        else:
            sg.batch_generate_srt(
                video_dir=video_path,
                language=language,
            )
            result = {"type": "done", "dir": str(video_path)}

        print(json.dumps(result, ensure_ascii=False), flush=True)

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"type": "error", "msg": str(e)}, ensure_ascii=False), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
