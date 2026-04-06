# -*- coding: utf-8 -*-
"""
preview_text_styles.py
======================
Tạo ảnh preview tất cả các mẫu text style.
Mỗi style render chữ "Toothpaste" / "Kem đánh răng" / "/ˈtuːθ.peɪst/"
Output: text_styles_preview.png
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, os, sys

# ── Cấu hình ───────────────────────────────────────────────────────────────
W, H = 720, 240          # kích thước 1 ô preview
COLS = 3
FONT_PATH_BOLD   = r"C:\Windows\Fonts\arialbd.ttf"
FONT_PATH_ITALIC = r"C:\Windows\Fonts\ariali.ttf"
FONT_PATH_REG    = r"C:\Windows\Fonts\arial.ttf"
SIZE_BIG   = 64
SIZE_MED   = 48
SIZE_SMALL = 36

TEXT_VI  = "Kem đánh răng"
TEXT_EN  = "Toothpaste"
TEXT_IPA = "/ˈtuːθ.peɪst/"

BG = (20, 20, 28)  # nền tối

# ── Helpers ────────────────────────────────────────────────────────────────
def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

def center_x(draw, text, font, W):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    return (W - w) // 2

def draw_3lines(draw, W, y_top, gap, texts, fonts, colors, strokes, stroke_colors):
    """Vẽ 3 dòng chữ VI / EN / IPA."""
    for i, (text, font, color, sw, sc) in enumerate(zip(texts, fonts, colors, strokes, stroke_colors)):
        x = center_x(draw, text, font, W)
        y = y_top + i * gap
        if sw > 0:
            draw.text((x, y), text, font=font, fill=color,
                      stroke_width=sw, stroke_fill=sc)
        else:
            draw.text((x, y), text, font=font, fill=color)

def make_gradient_h(w, h, c1, c2):
    """Tạo ảnh gradient ngang từ c1→c2."""
    img = Image.new("RGBA", (w, h))
    for x in range(w):
        r = int(c1[0] + (c2[0]-c1[0]) * x/w)
        g = int(c1[1] + (c2[1]-c1[1]) * x/w)
        b = int(c1[2] + (c2[2]-c1[2]) * x/w)
        for y in range(h):
            img.putpixel((x, y), (r, g, b, 255))
    return img

def apply_gradient_to_text(base_img, text, font, x, y, c1, c2):
    """Render text với màu gradient ngang."""
    tw = base_img.width
    th = base_img.height
    # Tạo mask từ text
    mask = Image.new("L", (tw, th), 0)
    md = ImageDraw.Draw(mask)
    md.text((x, y), text, font=font, fill=255)
    # Gradient overlay
    grad = make_gradient_h(tw, th, c1, c2)
    base_img.paste(grad, mask=mask)

# ── 12 text styles ──────────────────────────────────────────────────────────
STYLES = []

# ── STYLE 1: Classic Yellow (đang dùng) ────────────────────────────────────
def style_01(W, H):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    draw_3lines(d, W, y0, gap,
        [TEXT_VI, TEXT_EN, TEXT_IPA],
        [fB, fB, fI],
        [(0xFF,0xD7,0x00), (0xFF,0xD7,0x00), (0xFF,0xD7,0x00)],
        [3, 3, 2], [(0,0,0)]*3)
    return img, "1. Classic Yellow"

# ── STYLE 2: White Shadow ───────────────────────────────────────────────────
def style_02(W, H):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    # Shadow layer
    for dx, dy in [(3,3),(4,4)]:
        draw_3lines(d, W, y0+dy, gap,
            [TEXT_VI, TEXT_EN, TEXT_IPA],
            [fB, fB, fI],
            [(0,0,0,180)]*3, [0]*3, [(0,0,0)]*3)
    draw_3lines(d, W, y0, gap,
        [TEXT_VI, TEXT_EN, TEXT_IPA],
        [fB, fB, fI],
        [(255,255,255), (255,255,255), (220,220,220)],
        [0]*3, [(0,0,0)]*3)
    return img, "2. White + Shadow"

# ── STYLE 3: Fire Red-Orange ────────────────────────────────────────────────
def style_03(W, H):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    draw_3lines(d, W, y0, gap,
        [TEXT_VI, TEXT_EN, TEXT_IPA],
        [fB, fB, fI],
        [(0xFF,0x45,0x00), (0xFF,0x6A,0x00), (0xFF,0x8C,0x00)],
        [3, 3, 2], [(0xFF,0xD7,0x00)]*3)
    return img, "3. Fire Red-Orange"

# ── STYLE 4: Cyan Neon ──────────────────────────────────────────────────────
def style_04(W, H):
    img = Image.new("RGB", (W, H), (5, 5, 15))
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    # Glow effect (vẽ nhiều lớp mờ)
    for sw in [8, 5, 3]:
        draw_3lines(d, W, y0, gap,
            [TEXT_VI, TEXT_EN, TEXT_IPA],
            [fB, fB, fI],
            [(0,255,255,60)]*3, [sw]*3, [(0,200,255)]*3)
    draw_3lines(d, W, y0, gap,
        [TEXT_VI, TEXT_EN, TEXT_IPA],
        [fB, fB, fI],
        [(0,255,255), (0,255,255), (0,220,255)],
        [2]*3, [(0,100,200)]*3)
    return img, "4. Cyan Neon Glow"

# ── STYLE 5: Green Lime ─────────────────────────────────────────────────────
def style_05(W, H):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    draw_3lines(d, W, y0, gap,
        [TEXT_VI, TEXT_EN, TEXT_IPA],
        [fB, fB, fI],
        [(0x39,0xFF,0x14), (0x7F,0xFF,0x00), (0xAD,0xFF,0x2F)],
        [3, 3, 2], [(0,80,0)]*3)
    return img, "5. Lime Green"

# ── STYLE 6: Pink Gradient ──────────────────────────────────────────────────
def style_06(W, H):
    img = Image.new("RGBA", (W, H), (*BG, 255))
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    texts = [TEXT_VI, TEXT_EN, TEXT_IPA]
    fonts = [fB, fB, fI]
    c1s = [(0xFF,0x14,0x93), (0xFF,0x69,0xB4), (0xFF,0xA0,0xC8)]
    c2s = [(0xFF,0xA5,0x00), (0xFF,0xD7,0x00), (0xFF,0xE0,0x80)]
    for i, (text, font, c1, c2) in enumerate(zip(texts, fonts, c1s, c2s)):
        x = center_x(d, text, font, W)
        y = y0 + i * gap
        # stroke
        d.text((x, y), text, font=font, fill=(100,0,60), stroke_width=3, stroke_fill=(80,0,40))
        apply_gradient_to_text(img, text, font, x, y, c1, c2)
    return img.convert("RGB"), "6. Pink-Gold Gradient"

# ── STYLE 7: Block Background ───────────────────────────────────────────────
def style_07(W, H):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    texts  = [TEXT_VI, TEXT_EN, TEXT_IPA]
    fonts  = [fB, fB, fI]
    bgs    = [(0xFF,0x00,0x00), (0x00,0x00,0xFF), (0xFF,0x8C,0x00)]
    fgs    = [(0xFF,0xFF,0xFF), (0xFF,0xFF,0xFF), (0xFF,0xFF,0xFF)]
    for i, (text, font, bg, fg) in enumerate(zip(texts, fonts, bgs, fgs)):
        bbox = d.textbbox((0,0), text, font=font)
        tw = bbox[2]-bbox[0]+16
        th = bbox[3]-bbox[1]+8
        x  = (W - tw) // 2
        y  = y0 + i*gap - 4
        d.rectangle([x, y, x+tw, y+th], fill=bg)
        d.text((x+8, y+4), text, font=font, fill=fg)
    return img, "7. Block Background"

# ── STYLE 8: Double Outline ─────────────────────────────────────────────────
def style_08(W, H):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    # Outer stroke (trắng)
    draw_3lines(d, W, y0, gap, [TEXT_VI, TEXT_EN, TEXT_IPA], [fB, fB, fI],
        [(255,255,255)]*3, [7,7,5], [(255,255,255)]*3)
    # Inner stroke (đen)
    draw_3lines(d, W, y0, gap, [TEXT_VI, TEXT_EN, TEXT_IPA], [fB, fB, fI],
        [(0xFF,0xD7,0x00)]*3, [3,3,2], [(0,0,0)]*3)
    return img, "8. Double Outline"

# ── STYLE 9: Purple Violet ──────────────────────────────────────────────────
def style_09(W, H):
    img = Image.new("RGB", (W, H), (10,5,20))
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    draw_3lines(d, W, y0, gap,
        [TEXT_VI, TEXT_EN, TEXT_IPA],
        [fB, fB, fI],
        [(0xDA,0x70,0xD6), (0xEE,0x82,0xEE), (0xFF,0xA0,0xFF)],
        [4,4,3], [(0x4B,0x00,0x82)]*3)
    return img, "9. Purple Violet"

# ── STYLE 10: Gold Emboss ───────────────────────────────────────────────────
def style_10(W, H):
    img = Image.new("RGB", (W, H), (15,10,5))
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    # Highlight (sáng trên-trái)
    draw_3lines(d, W, y0-2, gap, [TEXT_VI, TEXT_EN, TEXT_IPA], [fB, fB, fI],
        [(0xFF,0xFF,0xCC)]*3, [0]*3, [(0,0,0)]*3)
    # Shadow (tối dưới-phải)
    draw_3lines(d, W, y0+2, gap, [TEXT_VI, TEXT_EN, TEXT_IPA], [fB, fB, fI],
        [(0x80,0x60,0x00)]*3, [0]*3, [(0,0,0)]*3)
    # Main gold
    draw_3lines(d, W, y0, gap,
        [TEXT_VI, TEXT_EN, TEXT_IPA],
        [fB, fB, fI],
        [(0xFF,0xD7,0x00), (0xFF,0xC1,0x07), (0xFE,0xA,0x00)],
        [2,2,1], [(0x8B,0x6,0x00)]*3)
    return img, "10. Gold Emboss"

# ── STYLE 11: Ice Blue ──────────────────────────────────────────────────────
def style_11(W, H):
    img = Image.new("RGB", (W, H), (5,10,25))
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    draw_3lines(d, W, y0, gap,
        [TEXT_VI, TEXT_EN, TEXT_IPA],
        [fB, fB, fI],
        [(0xAD,0xD8,0xE6), (0x87,0xCE,0xEB), (0xB0,0xE0,0xE6)],
        [4,4,3], [(0x00,0x4F,0x8C)]*3)
    return img, "11. Ice Blue"

# ── STYLE 12: Rainbow Gradient ──────────────────────────────────────────────
def style_12(W, H):
    img = Image.new("RGBA", (W, H), (*BG, 255))
    d = ImageDraw.Draw(img)
    fB = load_font(FONT_PATH_BOLD, SIZE_MED)
    fI = load_font(FONT_PATH_ITALIC, SIZE_SMALL)
    gap = SIZE_MED + 8
    y0 = (H - gap*2 - SIZE_SMALL) // 2
    texts = [TEXT_VI, TEXT_EN, TEXT_IPA]
    fonts = [fB, fB, fI]
    c1s = [(0xFF,0x00,0x00), (0xFF,0x7F,0x00), (0xFF,0xFF,0x00)]
    c2s = [(0x00,0x00,0xFF), (0x00,0xFF,0x00), (0xFF,0x00,0xFF)]
    for i, (text, font, c1, c2) in enumerate(zip(texts, fonts, c1s, c2s)):
        x = center_x(d, text, font, W)
        y = y0 + i * gap
        d.text((x, y), text, font=font, fill=(0,0,0), stroke_width=4, stroke_fill=(0,0,0))
        apply_gradient_to_text(img, text, font, x, y, c1, c2)
    return img.convert("RGB"), "12. Rainbow"

STYLES = [
    style_01, style_02, style_03, style_04,
    style_05, style_06, style_07, style_08,
    style_09, style_10, style_11, style_12,
]

# ── Tạo preview grid ────────────────────────────────────────────────────────
ROWS = math.ceil(len(STYLES) / COLS)
PAD  = 10
LABEL_H = 30
FONT_LABEL = load_font(FONT_PATH_BOLD, 20) if True else None

grid_w = COLS * (W + PAD) + PAD
grid_h = ROWS * (H + LABEL_H + PAD) + PAD
grid = Image.new("RGB", (grid_w, grid_h), (10,10,10))
gd   = ImageDraw.Draw(grid)

for idx, style_fn in enumerate(STYLES):
    col = idx % COLS
    row = idx // COLS
    x0  = PAD + col * (W + PAD)
    y0  = PAD + row * (H + LABEL_H + PAD)
    try:
        cell, label = style_fn(W, H)
        grid.paste(cell, (x0, y0 + LABEL_H))
        gd.text((x0, y0 + 5), label, font=FONT_LABEL, fill=(200,200,200))
    except Exception as e:
        print(f"Style {idx+1} lỗi: {e}")

out = r"d:\AI\TOOL_VEO3_NEW\Edit_video\text_styles_preview.png"
grid.save(out)
print(f"✅ Đã lưu: {out}")
print(f"   Grid: {grid_w}x{grid_h}px, {ROWS} hàng x {COLS} cột")
