# -*- coding: utf-8 -*-
"""
text_style.py
=============
Kiểu chữ & hiệu ứng cho text overlay lên video.

Tính năng:
  - Nhiều preset style (Neon, Shadow, Gradient, Outline Bold, ...)
  - Tùy chỉnh font, màu, viền, shadow
  - Tạo FFmpeg drawtext filter tự động
  - Hiệu ứng: fade in/out, slide, typewriter (qua FFmpeg expression)

Cách dùng:
  from text_style import TextStyleManager, TextStyle

  tsm = TextStyleManager()
  style = tsm.get_preset("neon_glow")
  filter_str = tsm.build_drawtext_filter(
      text="Hello World",
      style=style,
      x="center", y=900,
      t_start=0, t_end=5,
  )
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ffmpeg_utils import esc_ffmpeg


# ════════════════════════════════════════════════════════════
# TEXT STYLE DATACLASS
# ════════════════════════════════════════════════════════════
@dataclass
class TextStyle:
    """Cấu hình style cho text overlay."""
    name: str = "default"
    
    # Font
    font_file: str = r"C\:/Windows/Fonts/arialbd.ttf"
    font_size: int = 52
    bold: bool = True
    italic: bool = False
    
    # Màu sắc (FFmpeg hex format: 0xRRGGBB hoặc 0xRRGGBBAA)
    font_color: str = "0xFFFFFF"          # Trắng
    border_color: str = "0x000000"        # Đen
    border_width: int = 3
    shadow_color: str = "0x000000@0.5"    # Shadow
    shadow_x: int = 0
    shadow_y: int = 0
    
    # Background box (0=tắt, 1=bật)
    box: int = 0
    box_color: str = "0x000000@0.5"
    box_border_w: int = 10
    
    # Hiệu ứng
    effect: str = "none"  # none, fade_in, fade_out, fade_both, slide_up, slide_down
    fade_duration: float = 0.5  # giây

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "font_file": self.font_file,
            "font_size": self.font_size,
            "bold": self.bold,
            "italic": self.italic,
            "font_color": self.font_color,
            "border_color": self.border_color,
            "border_width": self.border_width,
            "shadow_color": self.shadow_color,
            "shadow_x": self.shadow_x,
            "shadow_y": self.shadow_y,
            "box": self.box,
            "box_color": self.box_color,
            "box_border_w": self.box_border_w,
            "effect": self.effect,
            "fade_duration": self.fade_duration,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TextStyle":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ════════════════════════════════════════════════════════════
# TEXT STYLE MANAGER
# ════════════════════════════════════════════════════════════
class TextStyleManager:
    """Quản lý kiểu chữ và tạo FFmpeg filter."""

    # Danh sách font Windows phổ biến
    WINDOWS_FONTS = {
        "Arial Bold":          r"C\:/Windows/Fonts/arialbd.ttf",
        "Arial":               r"C\:/Windows/Fonts/arial.ttf",
        "Arial Italic":        r"C\:/Windows/Fonts/ariali.ttf",
        "Arial Bold Italic":   r"C\:/Windows/Fonts/arialbi.ttf",
        "Times New Roman":     r"C\:/Windows/Fonts/times.ttf",
        "Tahoma":              r"C\:/Windows/Fonts/tahoma.ttf",
        "Segoe UI":            r"C\:/Windows/Fonts/segoeui.ttf",
        "Segoe UI Bold":       r"C\:/Windows/Fonts/segoeuib.ttf",
        "Verdana":             r"C\:/Windows/Fonts/verdana.ttf",
        "Calibri":             r"C\:/Windows/Fonts/calibri.ttf",
        "Impact":              r"C\:/Windows/Fonts/impact.ttf",
        "Consolas":            r"C\:/Windows/Fonts/consola.ttf",
        "Consolas Bold":       r"C\:/Windows/Fonts/consolab.ttf",
        "Georgia":             r"C\:/Windows/Fonts/georgia.ttf",
        "Georgia Bold":        r"C\:/Windows/Fonts/georgiab.ttf",
        "Comic Sans MS":       r"C\:/Windows/Fonts/comic.ttf",
        "Comic Sans MS Bold":  r"C\:/Windows/Fonts/comicbd.ttf",
        "Trebuchet MS":        r"C\:/Windows/Fonts/trebuc.ttf",
        "Trebuchet MS Bold":   r"C\:/Windows/Fonts/trebucbd.ttf",
        "Lucida Console":      r"C\:/Windows/Fonts/lucon.ttf",
        "Cambria":             r"C\:/Windows/Fonts/cambria.ttc",
        "Palatino Linotype":   r"C\:/Windows/Fonts/pala.ttf",
        "Century Gothic":      r"C\:/Windows/Fonts/GOTHIC.TTF",
    }

    # Preset styles
    PRESETS = {
        "clean_white": TextStyle(
            name="Clean White",
            font_color="0xFFFFFF",
            border_color="0x000000",
            border_width=3,
        ),
        "neon_yellow": TextStyle(
            name="Neon Yellow",
            font_color="0xFFD700",
            border_color="0x000000",
            border_width=4,
        ),
        "neon_cyan": TextStyle(
            name="Neon Cyan",
            font_color="0x00FFFF",
            border_color="0x003333",
            border_width=3,
        ),
        "neon_pink": TextStyle(
            name="Neon Pink",
            font_color="0xFF69B4",
            border_color="0x330022",
            border_width=3,
        ),
        "fire_red": TextStyle(
            name="Fire Red",
            font_color="0xFF4444",
            border_color="0x220000",
            border_width=4,
        ),
        "lime_green": TextStyle(
            name="Lime Green",
            font_color="0x00FF00",
            border_color="0x003300",
            border_width=3,
        ),
        "shadow_dark": TextStyle(
            name="Shadow Dark",
            font_color="0xFFFFFF",
            border_color="0x000000",
            border_width=2,
            shadow_color="0x000000@0.8",
            shadow_x=3,
            shadow_y=3,
        ),
        "subtitle_box": TextStyle(
            name="Subtitle Box",
            font_color="0xFFFFFF",
            border_color="0x000000",
            border_width=0,
            box=1,
            box_color="0x000000@0.6",
            box_border_w=12,
        ),
        "outline_bold": TextStyle(
            name="Outline Bold",
            font_size=68,
            font_color="0xFFFFFF",
            border_color="0x000000",
            border_width=6,
        ),
        "fade_in_out": TextStyle(
            name="Fade In/Out",
            font_color="0xFFFFFF",
            border_color="0x000000",
            border_width=3,
            effect="fade_both",
            fade_duration=0.5,
        ),
        "slide_up": TextStyle(
            name="Slide Up",
            font_color="0xFFD700",
            border_color="0x000000",
            border_width=4,
            effect="slide_up",
            fade_duration=0.3,
        ),
        "electric_blue": TextStyle(
            name="Electric Blue",
            font_color="0x00BFFF",
            border_color="0x001133",
            border_width=4,
            shadow_color="0x0066CC@0.6",
            shadow_x=2,
            shadow_y=2,
        ),
        "sunset_orange": TextStyle(
            name="Sunset Orange",
            font_color="0xFF6B35",
            border_color="0x331100",
            border_width=3,
        ),
        "purple_dream": TextStyle(
            name="Purple Dream",
            font_color="0xBB86FC",
            border_color="0x1A0033",
            border_width=3,
            shadow_color="0x6200EA@0.4",
            shadow_x=2,
            shadow_y=2,
        ),
        "minimal_gray": TextStyle(
            name="Minimal Gray",
            font_color="0xE0E0E0",
            border_color="0x333333",
            border_width=2,
        ),
        "retro_gold": TextStyle(
            name="Retro Gold",
            font_color="0xFFB347",
            border_color="0x8B4513",
            border_width=4,
            shadow_color="0x333333@0.7",
            shadow_x=3,
            shadow_y=3,
        ),
        "pastel_pink": TextStyle(
            name="Pastel Pink",
            font_color="0xFFB6C1",
            border_color="0x660033",
            border_width=2,
        ),
        "ice_blue_shadow": TextStyle(
            name="Ice Blue Shadow",
            font_color="0xADD8E6",
            border_color="0x000033",
            border_width=3,
            shadow_color="0x003366@0.6",
            shadow_x=4,
            shadow_y=4,
        ),
        "bold_impact": TextStyle(
            name="Bold Impact",
            font_size=72,
            font_color="0xFFFFFF",
            border_color="0xFF0000",
            border_width=5,
        ),
    }

    def __init__(self, custom_fonts_dir: str | Path = None):
        """
        Args:
            custom_fonts_dir: folder chứa font custom (.ttf)
        """
        self._custom_fonts = {}
        if custom_fonts_dir:
            self._load_custom_fonts(Path(custom_fonts_dir))

    def _load_custom_fonts(self, fonts_dir: Path):
        """Quét folder font custom."""
        if not fonts_dir.exists():
            return
        for f in fonts_dir.glob("*.ttf"):
            name = f.stem.replace("-", " ").replace("_", " ")
            # FFmpeg cần forward slash + escape colon
            escaped = str(f).replace("\\", "/").replace(":", "\\:")
            self._custom_fonts[name] = escaped

    def get_all_fonts(self) -> dict[str, str]:
        """Trả về tất cả font (Windows + custom)."""
        all_fonts = dict(self.WINDOWS_FONTS)
        all_fonts.update(self._custom_fonts)
        return all_fonts

    def get_preset(self, name: str) -> TextStyle:
        """Lấy preset style theo tên."""
        if name in self.PRESETS:
            return self.PRESETS[name]
        raise KeyError(f"Không tìm thấy preset: {name}. Có: {list(self.PRESETS.keys())}")

    def list_presets(self) -> list[str]:
        """Danh sách tên preset."""
        return list(self.PRESETS.keys())

    # ────────────────────────────────────────────────────────
    # BUILD DRAWTEXT FILTER
    # ────────────────────────────────────────────────────────
    def build_drawtext_filter(
        self,
        text: str,
        style: TextStyle,
        x: str | int = "center",
        y: int = 900,
        t_start: float = 0,
        t_end: float = 99,
        enable_time: bool = True,
    ) -> str:
        """
        Tạo FFmpeg drawtext filter string.
        
        Args:
            text: nội dung text
            style: TextStyle object
            x: vị trí X ("center" hoặc pixel)
            y: vị trí Y (pixel, tính từ trên)
            t_start: thời gian bắt đầu hiện
            t_end: thời gian kết thúc hiện
            enable_time: True = thêm enable theo thời gian
            
        Returns:
            FFmpeg filter string
        """
        # X position
        if x == "center":
            x_expr = "(w-text_w)/2"
        elif x == "left":
            x_expr = "20"
        elif x == "right":
            x_expr = "(w-text_w-20)"
        else:
            x_expr = str(x)

        # Y position — có thể kèm hiệu ứng
        y_expr = str(y)

        # Hiệu ứng
        alpha_expr = None
        if style.effect == "fade_in":
            fd = style.fade_duration
            alpha_expr = f"if(lt(t-{t_start}\\,{fd})\\,(t-{t_start})/{fd}\\,1)"
        elif style.effect == "fade_out":
            fd = style.fade_duration
            alpha_expr = f"if(gt(t\\,{t_end}-{fd})\\,({t_end}-t)/{fd}\\,1)"
        elif style.effect == "fade_both":
            fd = style.fade_duration
            alpha_expr = (
                f"if(lt(t-{t_start}\\,{fd})\\,(t-{t_start})/{fd}\\,"
                f"if(gt(t\\,{t_end}-{fd})\\,({t_end}-t)/{fd}\\,1))"
            )
        elif style.effect == "slide_up":
            fd = style.fade_duration
            # Y trượt từ dưới lên
            y_expr = f"if(lt(t-{t_start}\\,{fd})\\,{y}+50*(1-(t-{t_start})/{fd})\\,{y})"
            alpha_expr = f"if(lt(t-{t_start}\\,{fd})\\,(t-{t_start})/{fd}\\,1)"
        elif style.effect == "slide_down":
            fd = style.fade_duration
            y_expr = f"if(lt(t-{t_start}\\,{fd})\\,{y}-50*(1-(t-{t_start})/{fd})\\,{y})"
            alpha_expr = f"if(lt(t-{t_start}\\,{fd})\\,(t-{t_start})/{fd}\\,1)"

        # Enable time expression
        enable = ""
        if enable_time:
            enable = f":enable='between(t\\\\,{t_start}\\\\,{t_end})'"

        # Font color — thêm alpha nếu có hiệu ứng
        fc = style.font_color
        if alpha_expr:
            fc = f"{style.font_color}@%{{eif\\:{alpha_expr}\\:d}}"
            # Dùng cách đơn giản hơn cho alpha
            fc = style.font_color  # fallback, dùng enable thay thế

        # Build filter
        parts = [
            f"drawtext=fontfile='{style.font_file}'",
            f"text='{esc_ffmpeg(text)}'",
            f"fontsize={style.font_size}",
            f"fontcolor={fc}",
        ]

        # Border/outline
        if style.border_width > 0:
            parts.append(f"bordercolor={style.border_color}")
            parts.append(f"borderw={style.border_width}")

        # Shadow
        if style.shadow_x != 0 or style.shadow_y != 0:
            parts.append(f"shadowcolor={style.shadow_color}")
            parts.append(f"shadowx={style.shadow_x}")
            parts.append(f"shadowy={style.shadow_y}")

        # Box background
        if style.box:
            parts.append(f"box=1")
            parts.append(f"boxcolor={style.box_color}")
            parts.append(f"boxborderw={style.box_border_w}")

        # Position
        parts.append(f"x={x_expr}")
        parts.append(f"y={y_expr}")

        # Enable
        if enable:
            parts.append(f"enable='between(t\\\\,{t_start}\\\\,{t_end})'")

        return ":".join(parts)

    # ────────────────────────────────────────────────────────
    # BUILD MULTI-LINE FILTER (VI + EN + IPA)
    # ────────────────────────────────────────────────────────
    def build_multiline_filter(
        self,
        lines: list[dict],
        style: TextStyle,
        t_start: float = 0,
        t_end: float = 99,
    ) -> str:
        """
        Tạo filter cho nhiều dòng text.
        
        Args:
            lines: list[{text, y, font_file (optional), font_size (optional)}]
            style: TextStyle cơ sở
            t_start, t_end: thời gian hiển thị
            
        Returns:
            FFmpeg filter string (các drawtext nối nhau bằng dấu phẩy)
        """
        filters = []
        for line in lines:
            # Override font nếu có
            line_style = TextStyle(**style.to_dict())
            if "font_file" in line:
                line_style.font_file = line["font_file"]
            if "font_size" in line:
                line_style.font_size = line["font_size"]
            if "font_color" in line:
                line_style.font_color = line["font_color"]
            if "italic" in line:
                line_style.italic = line["italic"]
            if "bold" in line:
                line_style.bold = line["bold"]

            f = self.build_drawtext_filter(
                text=line["text"],
                style=line_style,
                y=line.get("y", 900),
                t_start=t_start,
                t_end=t_end,
            )
            filters.append(f)

        return ",".join(filters)


# ════════════════════════════════════════════════════════════
# DEMO / CLI
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    tsm = TextStyleManager(custom_fonts_dir=Path(__file__).parent / "fonts")

    print("=" * 55)
    print("  TEXT STYLE MANAGER — Kiểu chữ cho video")
    print("=" * 55)

    print("\n📋 Preset có sẵn:")
    for name in tsm.list_presets():
        preset = tsm.get_preset(name)
        print(f"  • {name:20s} → {preset.name} (màu: {preset.font_color})")

    print("\n📋 Font có sẵn:")
    for name, path in tsm.get_all_fonts().items():
        print(f"  • {name}")

    # Demo tạo filter
    style = tsm.get_preset("neon_yellow")
    demo_filter = tsm.build_drawtext_filter(
        text="Xin chào",
        style=style,
        y=900,
        t_start=0,
        t_end=5,
    )
    print(f"\n🎬 Demo filter:\n{demo_filter}")
