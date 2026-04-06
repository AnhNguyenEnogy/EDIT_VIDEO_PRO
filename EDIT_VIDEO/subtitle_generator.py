# -*- coding: utf-8 -*-
"""
subtitle_generator.py
=====================
Tự động tạo phụ đề cho video bằng faster-whisper.

Tính năng:
  - Nhận dạng giọng nói → tạo phụ đề SRT
  - Hỗ trợ nhiều ngôn ngữ (Việt, Anh, Nhật, Hàn, ...)
  - Chọn model: tiny, base, small, medium, large-v3
  - Xuất file SRT chuẩn
  - Burn phụ đề lên video bằng FFmpeg

Cách dùng:
  from subtitle_generator import SubtitleGenerator

  sg = SubtitleGenerator(model_size="medium")
  sg.generate_srt("video.mp4", "output.srt", language="vi")
  sg.burn_subtitle("video.mp4", "output.srt", "output_sub.mp4")
"""

import os
import subprocess
from pathlib import Path
from datetime import datetime

from ffmpeg_utils import get_ffmpeg, get_video_duration, format_time_srt, run_ffmpeg

_FONTS_DIR = Path(__file__).parent / "fonts"


class SubtitleGenerator:
    """Tạo phụ đề tự động bằng faster-whisper."""

    # Các model và mô tả
    MODELS = {
        "tiny":      "Nhẹ nhất, nhanh nhất (~1GB RAM), độ chính xác thấp",
        "base":      "Khá nhanh (~1GB RAM), chính xác tốt cho audio rõ",
        "small":     "Cân bằng tốc độ/chất lượng (~2GB RAM)",
        "medium":    "Chính xác cao (~5GB RAM)",
        "large-v3":  "Chính xác nhất (~10GB RAM), chậm nhất",
    }

    # Các ngôn ngữ phổ biến
    LANGUAGES = {
        "auto": "Tự động nhận diện",
        "vi": "Tiếng Việt",
        "en": "Tiếng Anh",
        "ja": "Tiếng Nhật",
        "ko": "Tiếng Hàn",
        "zh": "Tiếng Trung",
        "fr": "Tiếng Pháp",
        "de": "Tiếng Đức",
        "es": "Tiếng Tây Ban Nha",
    }

    def __init__(self, model_size: str = "medium", device: str = "auto", log_callback=None):
        """
        Args:
            model_size: tiny, base, small, medium, large-v3
            device: "auto", "cpu", "cuda"
            log_callback: hàm nhận string log
        """
        self._log = log_callback or print
        self._model_size = model_size
        self._device = device
        self._model = None
        self._ffmpeg = get_ffmpeg()

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log(f"[{ts}] {msg}")

    # ────────────────────────────────────────────────────────
    # LOAD MODEL
    # ────────────────────────────────────────────────────────
    def load_model(self):
        """Tải model Whisper."""
        if self._model is not None:
            return

        from faster_whisper import WhisperModel

        device = self._device
        compute_type = "float16"

        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                    self.log("   🚀 Dùng GPU (CUDA)")
                else:
                    device = "cpu"
                    compute_type = "int8"
                    self.log("   💻 Dùng CPU")
            except ImportError:
                device = "cpu"
                compute_type = "int8"
                self.log("   💻 Dùng CPU (không có torch)")

        if device == "cpu":
            compute_type = "int8"

        self._model = WhisperModel(
            self._model_size,
            device=device,
            compute_type=compute_type,
        )
        self.log(f"   ✅ Model '{self._model_size}' đã sẵn sàng ({device}/{compute_type})")

    # ────────────────────────────────────────────────────────
    # TRANSCRIBE
    # ────────────────────────────────────────────────────────
    def transcribe(
        self,
        video_path: str | Path,
        language: str = "auto",
        word_timestamps: bool = True,
    ) -> list[dict]:
        """
        Nhận dạng giọng nói từ video/audio.
        
        Returns:
            list[{start, end, text, words: [{word, start, end}]}]
        """
        self.load_model()
        video_path = str(video_path)

        self.log(f"🎙️ Đang nhận dạng: {Path(video_path).name}")
        lang = language if language != "auto" else None

        segments_raw, info = self._model.transcribe(
            video_path,
            language=lang,
            word_timestamps=word_timestamps,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
        )

        detected_lang = info.language
        self.log(f"   🌐 Ngôn ngữ: {detected_lang} (xác suất: {info.language_probability:.1%})")

        segments = []
        for seg in segments_raw:
            words = []
            if word_timestamps and seg.words:
                for w in seg.words:
                    words.append({
                        "word": w.word.strip(),
                        "start": w.start,
                        "end": w.end,
                    })
            segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
                "words": words,
            })

        self.log(f"   ✅ Nhận dạng được {len(segments)} đoạn")
        return segments

    # ────────────────────────────────────────────────────────
    # XUẤT SRT
    # ────────────────────────────────────────────────────────
    def generate_srt(
        self,
        video_path: str | Path,
        output_srt: str | Path,
        language: str = "auto",
        max_chars_per_line: int = 42,
    ) -> Path:
        """
        Tạo file SRT từ video.
        
        Args:
            video_path: đường dẫn video
            output_srt: đường dẫn file SRT output
            language: ngôn ngữ
            max_chars_per_line: số ký tự tối đa mỗi dòng phụ đề
            
        Returns:
            Path đến file SRT
        """
        segments = self.transcribe(video_path, language)
        output_srt = Path(output_srt)
        output_srt.parent.mkdir(parents=True, exist_ok=True)

        self.log(f"📝 Xuất SRT: {output_srt.name}")

        with open(output_srt, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                start_ts = format_time_srt(seg["start"])
                end_ts = format_time_srt(seg["end"])
                text = seg["text"]

                # Chia dòng nếu quá dài
                if len(text) > max_chars_per_line:
                    words = text.split()
                    lines = []
                    current = ""
                    for w in words:
                        if len(current) + len(w) + 1 > max_chars_per_line and current:
                            lines.append(current.strip())
                            current = w
                        else:
                            current += " " + w if current else w
                    if current:
                        lines.append(current.strip())
                    text = "\n".join(lines)

                f.write(f"{i}\n")
                f.write(f"{start_ts} --> {end_ts}\n")
                f.write(f"{text}\n\n")

        self.log(f"   ✅ Đã lưu {len(segments)} phụ đề → {output_srt.name}")
        return output_srt

    # ────────────────────────────────────────────────────────
    # ĐỌC SRT
    # ────────────────────────────────────────────────────────
    @staticmethod
    def read_srt(srt_path: str | Path) -> list[dict]:
        """Đọc file SRT → list[{index, start, end, text}]."""
        import re
        srt_path = Path(srt_path)
        content = srt_path.read_text(encoding="utf-8")
        
        pattern = re.compile(
            r"(\d+)\s*\n"
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n"
            r"((?:(?!\d+\s*\n\d{2}:\d{2}).+\n?)*)",
            re.MULTILINE,
        )

        def parse_ts(ts: str) -> float:
            h, m, rest = ts.split(":")
            s, ms = rest.split(",")
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

        entries = []
        for match in pattern.finditer(content):
            entries.append({
                "index": int(match.group(1)),
                "start": parse_ts(match.group(2)),
                "end": parse_ts(match.group(3)),
                "text": match.group(4).strip(),
            })

        return entries
    def _read_srt(self, srt_path):
        import re
        content = Path(srt_path).read_text(encoding="utf-8")
        blocks = re.split(r'\n\s*\n', content.strip())
        entries = []
        for b in blocks:
            lines = b.splitlines()
            if len(lines) >= 3:
                time_line = lines[1]
                m = re.match(r'(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)', time_line)
                if m:
                    def to_s(t):
                        h, m, s_ms = t.split(':')
                        s, ms = s_ms.split(',')
                        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
                    entries.append({
                        "start": to_s(m.group(1)),
                        "end": to_s(m.group(2)),
                        "text": "\n".join(lines[2:]),
                        "words": []
                    })
        return entries


    # ────────────────────────────────────────────────────────
    # BURN SUBTITLE LÊN VIDEO
    # ────────────────────────────────────────────────────────
    def burn_subtitle(
        self,
        video_path: str | Path,
        srt_path: str | Path,
        output_path: str | Path,
        font_name: str = "Arial",
        font_size: int = 24,
        font_color: str = "&HFFFFFF",
        border_color: str = "&H000000",
        border_width: int = 3,
        position: str = "bottom",
        margin_v: int = 30,
        x_offset: int = 0,
        y_vi: int = None,
        auto_y: bool = True,
        aspect_idx: int = 0,
    ) -> Path:
        """
        Đốt phụ đề lên video bằng FFmpeg subtitles filter.
        
        Args:
            video_path: video gốc
            srt_path: file SRT
            output_path: video output
            font_name: tên font
            font_size: cỡ chữ
            font_color: màu chữ (ASS format: &HBBGGRR)
            border_color: màu viền
            border_width: độ dày viền
            position: "bottom", "top", "center"
            margin_v: margin dọc (px)
        """
        video_path = Path(video_path)
        srt_path = Path(srt_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.log(f"🎬 Burn phụ đề: {video_path.name}")
        self.log(f"   🎨 Font: {font_name} | Size: {font_size} | Color: {font_color}")

        # Escape path cho FFmpeg filter
        srt_str = str(srt_path).replace("\\", "/").replace(":", "\\:")
        fonts_str = str(_FONTS_DIR).replace("\\", "/").replace(":", "\\:") if _FONTS_DIR.exists() else ""

        # Alignment (ASS format): 2=bottom-center, 8=top-center, 5=center
        alignment = {"bottom": 2, "top": 8, "center": 5}.get(position, 2)

        if not auto_y:
            try:
                self.log(f"   📍 Burn Custom Pos: y={y_vi}, x_off={x_offset}")
                segments = self._read_srt(srt_path)
                ass_p = srt_path.with_suffix(".ass")
                self._write_ass(ass_p, segments, font_name=font_name, font_size=font_size,
                    font_color=font_color, bg_color=bg_color, style_idx=style_idx, alignment=alignment, is_bold=is_bold, is_italic=is_italic, is_underline=is_underline, border_w=border_w, position=position, fx="none",
                    margin_v=margin_v, x_offset=x_offset, y_vi=y_vi, auto_y=False,
                    aspect_idx=aspect_idx)
                ass_s = str(ass_p).replace("\\", "/").replace(":", "\\:")
                if fonts_str:
                    vf = f"ass='{ass_s}':fontsdir='{fonts_str}'"
                else:
                    vf = f"ass='{ass_s}'"
            except Exception as e:
                self.log(f"⚠️ Load SRT to ASS error: {e}. Fallback to auto.")
                auto_y = True

        if auto_y:
            style = (f"FontName={font_name},FontSize={font_size},PrimaryColour={font_color},"
                     f"OutlineColour={border_color},Outline={border_width},Alignment={alignment},MarginV={margin_v}")
            if fonts_str:
                vf = f"subtitles='{srt_str}':force_style='{style}':fontsdir='{fonts_str}'"
            else:
                vf = f"subtitles='{srt_str}':force_style='{style}'"

        cmd = [
            self._ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(output_path),
        ]

        run_ffmpeg(cmd)
        self.log(f"   ✅ Đã burn phụ đề → {output_path.name}")
        return output_path

    # ────────────────────────────────────────────────────────
    # BURN SUBTITLE VỚI HIỆU ỨNG (ASS format)
    # ────────────────────────────────────────────────────────
    def burn_subtitle_fx(
        self,
        video_path: str | Path,
        srt_path: str | Path,
        output_path: str | Path,
        font_name: str = "Arial",
        font_size: int = 24,
        font_color: str = "&HFFFFFF",
        bg_color: str = "#000000",
        style_idx: int = 0,
        is_bold: bool = True,
        is_italic: bool = False,
        is_underline: bool = False,
        border_w: int = None,
        position: str = "bottom",
        alignment: int = 2,
        fx: str = "karaoke",
        language: str = "auto",
        margin_v: int = 30,
        x_offset: int = 0,
        y_vi: int = None,
        auto_y: bool = True,
        aspect_idx: int = 0,
        kara_run_color: str = "#FFFF00",
        kara_bg_color: str = "#FFFFFF",
    ) -> Path:
        """
        Burn phụ đề lên video với hiệu ứng nâng cao.
        
        Effects:
            - karaoke: highlight từng từ khi đọc (kiểu CapCut)
            - fade: fade in từng dòng
            - popup: text nhỏ → to
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.log(f"🎬 Burn phụ đề (FX: {fx}): {video_path.name}")
        self.log(f"   🎨 Font: {font_name} | Size: {font_size} | Color: {font_color}")

        # Transcribe lại với word timestamps
        segments = self.transcribe(video_path, language=language, word_timestamps=True)

        # Tạo file ASS
        ass_path = srt_path if str(srt_path).endswith('.ass') else Path(str(srt_path).rsplit('.', 1)[0] + '.ass')
        self._write_ass(
            ass_path, segments,
            font_name=font_name, font_size=font_size,
            font_color=font_color, alignment=alignment,
            position=position, fx=fx, margin_v=margin_v,
            x_offset=x_offset, y_vi=y_vi, auto_y=auto_y,
            aspect_idx=aspect_idx,
            kara_run_color=kara_run_color,
            kara_bg_color=kara_bg_color,
        )

        # Burn bằng FFmpeg
        ass_str = str(ass_path).replace("\\", "/").replace(":", "\\:")
        fonts_str = str(_FONTS_DIR).replace("\\", "/").replace(":", "\\:") if _FONTS_DIR.exists() else ""
        if fonts_str:
            vf = f"ass='{ass_str}':fontsdir='{fonts_str}'"
        else:
            vf = f"ass='{ass_str}'"

        cmd = [
            self._ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(output_path),
        ]

        run_ffmpeg(cmd)
        self.log(f"   ✅ Đã burn phụ đề (FX: {fx}) → {output_path.name}")
        return output_path

    def _write_ass(
        self, ass_path, segments,
        font_name="Arial", font_size=24,
        font_color="&HFFFFFF", bg_color="#000000", style_idx=0, alignment=2,
        position="bottom", fx="karaoke",
        margin_v=30,
        x_offset=0, y_vi=None, auto_y=True,
        aspect_idx=0,
        is_bold=True, is_italic=False, is_underline=False, border_w=None,
        kara_run_color="#FFFF00", kara_bg_color="#FFFFFF",
    ):
        """Tạo file ASS với hiệu ứng."""
        # Chuyển đổi HEX #RRGGBB → ASS &H00BBGGRR
        def to_ass_color(hc, default="&H00FFFFFF", alpha="00"):
            if not hc or hc.startswith("&H"): return hc if str(hc).startswith("&H") else default
            hc = hc.lstrip('#')
            if len(hc) == 6: return f"&H{alpha}{hc[4:6]}{hc[2:4]}{hc[0:2]}"
            return default

        primary = to_ass_color(font_color, "&H00FFFFFF")
        bg_col = to_ass_color(bg_color, "&H00000000")
        
        # Mapping 12 Styles
        # style = "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"

        bord = 3
        shad = 1
        outline = "&H00000000" # Black default
        back = "&H80000000"    # Black shadow default
        border_style = 1       # 1=Outline+DropShadow, 3=Opaque Box
        bold = -1 if is_bold else 0
        italic = -1 if is_italic else 0
        underline = -1 if is_underline else 0
        
        if style_idx == 1:   # 1. Classic Yellow
            primary = to_ass_color("#FFD700")
            outline = to_ass_color("#000000")
            bord = 3; shad = 2
        elif style_idx == 2: # 2. White + Shadow
            primary = to_ass_color("#FFFFFF")
            back = to_ass_color("#000000", alpha="60")
            bord = 0; shad = 4
        elif style_idx == 3: # 3. Fire Red-Orange
            primary = to_ass_color("#FF4500")
            outline = to_ass_color("#FFD700")
            bord = 3; shad = 2
        elif style_idx == 4: # 4. Cyan Neon Glow
            primary = to_ass_color("#00FFFF")
            outline = to_ass_color("#00C8FF")
            bord = 4; shad = 0
            # require lur4 tag for neon later
        elif style_idx == 5: # 5. Lime Green
            primary = to_ass_color("#39FF14")
            outline = to_ass_color("#005000")
            bord = 3; shad = 2
        elif style_idx == 6: # 6. Pink-Gold Gradient (ASS limit to Pink)
            primary = to_ass_color("#FF1493")
            outline = to_ass_color("#500028")
            bord = 3; shad = 0
        elif style_idx == 7: # 7. Block Background
            primary = to_ass_color(font_color, "&H00FFFFFF")
            back = bg_col # Use user BG color
            border_style = 3  # bg block
            bord = 2; shad = 0
        elif style_idx == 8: # 8. Double Outline (ASS limit -> thick outline)
            primary = to_ass_color("#FFD700")
            outline = to_ass_color("#FFFFFF")
            back = to_ass_color("#000000")
            bord = 4; shad = 0
        elif style_idx == 9: # 9. Purple Violet
            primary = to_ass_color("#DA70D6")
            outline = to_ass_color("#4B0082")
            bord = 4; shad = 3
        elif style_idx == 10: # 10. Gold Emboss
            primary = to_ass_color("#FFD700")
            outline = to_ass_color("#8B0600")
            bord = 2; shad = 1
        elif style_idx == 11: # 11. Ice Blue
            primary = to_ass_color("#ADD8E6")
            outline = to_ass_color("#004F8C")
            bord = 4; shad = 3
        elif style_idx == 12: # 12. Rainbow (Limit to Pink/Purple)
            primary = to_ass_color("#FF00FF")
            outline = to_ass_color("#000000")
            bord = 4; shad = 0
        elif style_idx == 13: # 13. Sunset Orange
            primary = to_ass_color("#FF6B35")
            outline = to_ass_color("#C62828")
            back = to_ass_color("#FF8F00", alpha="40")
            bord = 3; shad = 2
        elif style_idx == 14: # 14. Matrix Green
            primary = to_ass_color("#00FF41")
            outline = to_ass_color("#003B00")
            bord = 2; shad = 3
        elif style_idx == 15: # 15. Blood Red
            primary = to_ass_color("#DC143C")
            outline = to_ass_color("#8B0000")
            back = to_ass_color("#2D0000", alpha="80")
            bord = 3; shad = 2
        elif style_idx == 16: # 16. Ocean Deep
            primary = to_ass_color("#0077B6")
            outline = to_ass_color("#023E8A")
            back = to_ass_color("#00B4D8", alpha="40")
            bord = 3; shad = 2
        elif style_idx == 17: # 17. Cotton Candy
            primary = to_ass_color("#FFB6C1")
            outline = to_ass_color("#FF69B4")
            bord = 3; shad = 1
        elif style_idx == 18: # 18. Chrome Silver
            primary = to_ass_color("#C0C0C0")
            outline = to_ass_color("#696969")
            back = to_ass_color("#808080", alpha="60")
            bord = 2; shad = 3
        elif style_idx == 19: # 19. Lava Glow
            primary = to_ass_color("#FF4500")
            outline = to_ass_color("#FF0000")
            bord = 5; shad = 0
            # require blur for neon effect too
        elif style_idx == 20: # 20. Electric Purple
            primary = to_ass_color("#BF00FF")
            outline = to_ass_color("#7400B8")
            bord = 4; shad = 1
        elif style_idx == 0: # User custom
            outline = bg_col
            bord = 3; shad = 1

        # User border override
        if border_w is not None:
            bord = border_w
        
        # Màu highlight cho karaoke
        kara_run = to_ass_color(kara_run_color, "&H0000FFFF")
        kara_bg = to_ass_color(kara_bg_color, "&H00FFFFFF")

        # Xác định kích thước canvas theo aspect ratio
        if aspect_idx == 0:  # 9:16
            play_res_x, play_res_y = 720, 1280
        else:  # 16:9
            play_res_x, play_res_y = 1280, 720

        pos_tag = ""
        if not auto_y and y_vi is not None:
            target_x = play_res_x // 2 + x_offset
            # \an8 = top-center anchor → y_vi = đỉnh chữ (khớp với preview)
            pos_tag = f"{{\\an8\\pos({target_x},{y_vi})}}"


        def _ts(seconds):
            """Chuyển giây → ASS timestamp H:MM:SS.cc"""
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            cs = int((seconds % 1) * 100)
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

        with open(ass_path, "w", encoding="utf-8-sig") as f:
            # Header
            f.write("[Script Info]\n")
            f.write("Title: Auto Subtitle\n")
            f.write("ScriptType: v4.00+\n")
            f.write(f"PlayResX: {play_res_x}\n")
            f.write(f"PlayResY: {play_res_y}\n")
            f.write("WrapStyle: 0\n\n")

            # Styles
            f.write("[V4+ Styles]\n")
            f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
                    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
                    "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                    "Alignment, MarginL, MarginR, MarginV, Encoding\n")

            # Default style
            f.write(f"Style: Default,{font_name},{font_size}," f"{primary},&H000000FF,{outline},{back}," f"{bold},{italic},{underline},0,100,100,0,0,{border_style},{bord},{shad}," f"{alignment},20,20,{margin_v},1\n")

            # Karaoke highlight style 
            f.write(f"Style: Highlight,{font_name},{font_size}," f"{kara_run},{kara_bg},{outline},{back}," f"{bold},{italic},{underline},0,100,100,0,0,{border_style},{bord},{shad}," f"{alignment},20,20,{margin_v},1\n\n")

            # Events
            f.write("[Events]\n")
            f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            blur_tag = '{\\blur3}' if style_idx in (4, 19) else ''
            for seg in segments:
                start = _ts(seg["start"])
                end = _ts(seg["end"])
                text = seg["text"]
                words = seg.get("words", [])

                if fx == "word_pop" and words:
                    # WORD POP: TẤT CẢ text hiện SẴN, chỉ từ đang đọc nổi bật
                    for wi, w in enumerate(words):
                        w_start = _ts(w["start"])
                        if wi < len(words) - 1:
                            w_end_active = _ts(words[wi + 1]["start"])
                        else:
                            w_end_active = end

                        # Render TẤT CẢ từ, từ đang đọc có override
                        parts = []
                        for wj, ww in enumerate(words):
                            if wj == wi:
                                tag = ("{\\\\fscx140\\\\fscy140"
                                       "\\\\t(0,100,\\\\fscx125\\\\fscy125)"
                                       "\\\\t(100,200,\\\\fscx140\\\\fscy140)"
                                       f"\\\\1c{kara_run}"
                                       "\\\\bord4\\\\blur2"
                                       f"\\\\3c{kara_run}"
                                       "}")
                                parts.append(f"{tag}{ww['word']}{{\\\\r}} ")
                            else:
                                parts.append(f"{ww['word']} ")

                        line = "".join(parts).strip()
                        f.write(f"Dialogue: 0,{w_start},{w_end_active},Highlight,,0,0,0,,{pos_tag}{blur_tag}{line}\\n")
                        for wj, ww in enumerate(words[:wi+1]):
                            if wj == wi:
                                # Từ đang đọc: POP scale + highlight color
                                pop = "{\\fscx130\\fscy130\\t(0,120,\\fscx105\\fscy105)\\t(120,200,\\fscx100\\fscy100)" + f"\\1c{kara_run}" + "}"
                                parts.append(f"{pop}{ww['word']} ")
                            else:
                                # Từ đã đọc: bình thường
                                parts.append(f"{ww['word']} ")

                        line = "".join(parts).strip()
                        f.write(f"Dialogue: 0,{w_start},{w_end_active},Highlight,,0,0,0,,{pos_tag}{blur_tag}{line}\n")

                elif fx == "word_pop":
                    # Fallback khi không có word timestamps
                    popup_tag = "{\\fscx50\\fscy50\\t(0,200,\\fscx110\\fscy110)\\t(200,350,\\fscx100\\fscy100)\\fad(50,150)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{blur_tag}{popup_tag}{text}\n")

                elif fx == "firework" and words:
                    # ═══════════════════════════════════════════════════
                    # FIREWORK (PHÁO HOA BIẾN MẤT):
                    # - Text hiện bình thường khi đang đọc
                    # - Sau khi đọc xong từ, từ đó BUNG NỔ:
                    #   phóng to 200% + blur mạnh + fade alpha → biến mất
                    # - Hiệu ứng giống pháo hoa nổ tung
                    # ═══════════════════════════════════════════════════
                    # Layer 0: text bình thường (hiện → ẩn dần)
                    fade_tag = "{\\fad(150,0)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{blur_tag}{fade_tag}{text}\n")

                    # Layer 1: mỗi từ bung nổ sau khi đọc xong
                    for wi, w in enumerate(words):
                        # Thời điểm bắt đầu bung nổ = kết thúc từ
                        if wi < len(words) - 1:
                            explode_start = words[wi + 1]["start"]
                        else:
                            explode_start = seg["end"] - 0.3  # 300ms trước kết thúc

                        explode_start = max(explode_start, w["start"] + 0.1)
                        explode_end = explode_start + 0.5  # 500ms animation

                        e_start = _ts(explode_start)
                        e_end = _ts(min(explode_end, seg["end"] + 0.3))

                        # Bung nổ: scale 100→250%, blur 0→15, alpha 00→FF
                        explode_tag = (
                            "{\\fscx100\\fscy100\\blur0\\alpha&H00&"
                            "\\t(0,400,\\fscx250\\fscy250\\blur15\\alpha&HFF&)"
                            "}"
                        )
                        f.write(f"Dialogue: 1,{e_start},{e_end},Default,,0,0,0,,{pos_tag}{explode_tag}{w['word']}\n")

                elif fx == "firework":
                    # Fallback: bung nổ toàn bộ text ở cuối
                    dur = seg["end"] - seg["start"]
                    mid = seg["start"] + dur * 0.7
                    mid_ts = _ts(mid)
                    end_ts = _ts(seg["end"] + 0.3)
                    # Phase 1: hiện bình thường
                    f.write(f"Dialogue: 0,{start},{mid_ts},Default,,0,0,0,,{pos_tag}{blur_tag}{text}\n")
                    # Phase 2: bung nổ
                    explode_tag = (
                        "{\\fscx100\\fscy100\\blur0\\alpha&H00&"
                        "\\t(0,300,\\fscx200\\fscy200\\blur12\\alpha&HFF&)"
                        "}"
                    )
                    f.write(f"Dialogue: 1,{mid_ts},{end_ts},Default,,0,0,0,,{pos_tag}{explode_tag}{text}\n")

                elif fx == "karaoke" and words:
                    # Highlight từng từ — dùng {\kf} tag
                    parts = []
                    for wi, w in enumerate(words):
                        if wi < len(words) - 1:
                            dur_cs = int((words[wi + 1]["start"] - w["start"]) * 100)
                        else:
                            dur_cs = int((seg["end"] - w["start"]) * 100)
                        dur_cs = max(dur_cs, 5)
                        parts.append(f"{{\\kf{dur_cs}}}{w['word']} ")
                    line = "".join(parts).strip()
                    f.write(f"Dialogue: 0,{start},{end},Highlight,,0,0,0,,{pos_tag}{blur_tag}{line}\n")

                elif fx == "fade":
                    fade_tag = "{\\fad(300,200)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{blur_tag}{fade_tag}{text}\n")

                elif fx == "popup":
                    popup_tag = "{\\fscx50\\fscy50\\t(0,150,\\fscx100\\fscy100)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{blur_tag}{popup_tag}{text}\n")

                elif fx == "typewriter" and words:
                    for wi, w in enumerate(words):
                        w_start = _ts(w["start"])
                        w_end = _ts(seg["end"])
                        fade_tag = "{\\fad(80,0)}"
                        partial = " ".join(ww["word"] for ww in words[:wi+1])
                        f.write(f"Dialogue: 0,{w_start},{w_end},Default,,0,0,0,,{pos_tag}{fade_tag}{partial}\n")

                elif fx == "typewriter":
                    fade_tag = "{\\fad(200,100)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{blur_tag}{fade_tag}{text}\n")

                elif fx == "bounce":
                    bounce_tag = "{\\fscx130\\fscy130\\t(0,200,\\fscx95\\fscy95)\\t(200,350,\\fscx100\\fscy100)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{blur_tag}{bounce_tag}{text}\n")

                elif fx == "slide_left":
                    move_tag = "{\\move(-" + str(play_res_x) + "," + str(play_res_y // 2) + "," + str(play_res_x // 2) + "," + str(play_res_y // 2) + ",0,250)\\fad(0,200)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{move_tag}{text}\n")

                elif fx == "slide_right":
                    move_tag = "{\\move(" + str(play_res_x * 2) + "," + str(play_res_y // 2) + "," + str(play_res_x // 2) + "," + str(play_res_y // 2) + ",0,250)\\fad(0,200)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{move_tag}{text}\n")

                elif fx == "glow":
                    glow_tag = "{\\bord6\\blur8\\3c&H00FFFF&\\fad(250,150)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{glow_tag}{text}\n")

                elif fx == "spin_in":
                    # Xoay vào: text xoay từ 45 độ → 0 độ + scale
                    spin_tag = "{\\frz45\\fscx80\\fscy80\\t(0,300,\\frz0\\fscx100\\fscy100)\\fad(50,150)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{blur_tag}{spin_tag}{text}\n")

                elif fx == "zoom_word" and words:
                    # Zoom từng từ: mỗi từ scale 150% rồi thu nhỏ 100%
                    for wi, w in enumerate(words):
                        w_start = _ts(w["start"])
                        w_end = _ts(seg["end"])
                        zoom_tag = "{\\fscx150\\fscy150\\t(0,200,\\fscx100\\fscy100)\\fad(50,0)}"
                        partial = " ".join(ww["word"] for ww in words[:wi+1])
                        f.write(f"Dialogue: 0,{w_start},{w_end},Default,,0,0,0,,{pos_tag}{blur_tag}{zoom_tag}{partial}\n")

                elif fx == "wave":
                    # Sóng chữ: text dao động nhẹ lên xuống
                    wave_tag = "{\\frz-3\\t(0,400,\\frz3)\\t(400,800,\\frz-3)\\fad(200,150)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{blur_tag}{wave_tag}{text}\n")

                elif fx == "shake":
                    # Shake rung: chữ rung lắc nhanh bằng move nhỏ
                    cx = play_res_x // 2
                    cy = play_res_y - margin_v - font_size
                    if position == "top":
                        cy = margin_v + font_size
                    elif position == "center":
                        cy = play_res_y // 2
                    shake_tag = "{\\move(" + str(cx-4) + "," + str(cy-3) + "," + str(cx+4) + "," + str(cy+3) + ",0,100)\\fad(50,100)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{shake_tag}{text}\n")

                elif fx == "drop_in":
                    # Drop từ trên: text rơi từ trên xuống vị trí
                    cx = play_res_x // 2
                    cy_end = play_res_y - margin_v - font_size
                    if position == "top":
                        cy_end = margin_v + font_size
                    elif position == "center":
                        cy_end = play_res_y // 2
                    cy_start = 0
                    drop_tag = "{\\move(" + str(cx) + "," + str(cy_start) + "," + str(cx) + "," + str(cy_end) + ",0,350)\\fad(0,200)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{drop_tag}{text}\n")

                elif fx == "flicker":
                    # Flicker nhấp nháy: text alpha nhấp nháy
                    flicker_tag = "{\\alpha&HFF&\\t(0,100,\\alpha&H00&)\\t(200,300,\\alpha&H40&)\\t(400,500,\\alpha&H00&)\\fad(0,200)}"
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{blur_tag}{flicker_tag}{text}\n")

                else:
                    # Không hiệu ứng
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{blur_tag}{text}\n")

        self.log(f"   📝 Đã tạo ASS ({fx}): {ass_path.name}")

    # ────────────────────────────────────────────────────────
    # BATCH: TẠO PHỤ ĐỀ NHIỀU VIDEO
    # ────────────────────────────────────────────────────────
    def batch_generate_srt(
        self,
        video_dir: str | Path,
        output_dir: str | Path = None,
        language: str = "auto",
        extension: str = ".mp4",
        stop_flag: list | None = None,
    ) -> list[dict]:
        """
        Tạo SRT cho tất cả video trong folder.
        
        Returns:
            list[{video, srt_path, status}]
        """
        video_dir = Path(video_dir)
        output_dir = Path(output_dir) if output_dir else video_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        videos = sorted(video_dir.glob(f"*{extension}"))
        if not videos:
            self.log(f"⚠️ Không tìm thấy video {extension} trong: {video_dir}")
            return []

        self.log(f"📂 Tìm thấy {len(videos)} video")

        results = []
        for vi, vpath in enumerate(videos):
            if stop_flag and stop_flag[0]:
                self.log("⏹ Đã dừng.")
                break

            srt_name = vpath.stem + ".srt"
            srt_path = output_dir / srt_name

            self.log(f"\n[{vi+1}/{len(videos)}] {vpath.name}")

            try:
                self.generate_srt(vpath, srt_path, language)
                results.append({
                    "video": str(vpath),
                    "srt_path": str(srt_path),
                    "status": "OK",
                })
            except Exception as e:
                self.log(f"   ❌ Lỗi: {e}")
                results.append({
                    "video": str(vpath),
                    "srt_path": None,
                    "status": f"lỗi: {str(e)[:100]}",
                })

        ok = sum(1 for r in results if r["status"] == "OK")
        self.log(f"\n{'='*50}")
        self.log(f"✅ Thành công: {ok}/{len(results)}")
        return results


# ════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    print("=" * 55)
    print("  SUBTITLE GENERATOR — Phụ đề tự động (faster-whisper)")
    print("=" * 55)

    video = input("🎬 File video: ").strip()
    if not video:
        print("❌ Chưa nhập video!")
        sys.exit(1)

    lang = input("🌐 Ngôn ngữ (vi/en/auto): ").strip() or "auto"
    model = input("🧠 Model (tiny/base/small/medium/large-v3): ").strip() or "medium"
    
    output_srt = Path(video).with_suffix(".srt")
    
    sg = SubtitleGenerator(model_size=model)
    sg.generate_srt(video, output_srt, language=lang)
    
    burn = input("\n🔥 Burn phụ đề lên video? (y/n): ").strip().lower()
    if burn == "y":
        output_video = Path(video).stem + "_subtitled.mp4"
        sg.burn_subtitle(video, output_srt, output_video)
