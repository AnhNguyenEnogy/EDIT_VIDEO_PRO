# -*- coding: utf-8 -*-
"""
download_fonts.py
=================
Tải các Google Fonts hỗ trợ tiếng Việt về folder fonts/

Cách dùng:
  .venv/Scripts/python.exe download_fonts.py
"""

import urllib.request, sys
from pathlib import Path

FONTS_DIR = Path(__file__).parent / "fonts"
FONTS_DIR.mkdir(exist_ok=True)

# ── Danh sách font muốn tải ──────────────────────────────────
# Nguồn: Google Fonts GitHub (raw)
BASE = "https://github.com/google/fonts/raw/main"

FONTS = [
    # ── Be Vietnam Pro — Font thiết kế riêng cho tiếng Việt ──
    (f"{BASE}/ofl/bevietnamepro/BeVietnamPro-Bold.ttf",         "BeVietnamPro-Bold.ttf"),
    (f"{BASE}/ofl/bevietnamepro/BeVietnamPro-Regular.ttf",      "BeVietnamPro-Regular.ttf"),
    (f"{BASE}/ofl/bevietnamepro/BeVietnamPro-SemiBold.ttf",     "BeVietnamPro-SemiBold.ttf"),
    (f"{BASE}/ofl/bevietnamepro/BeVietnamPro-Italic.ttf",       "BeVietnamPro-Italic.ttf"),
    (f"{BASE}/ofl/bevietnamepro/BeVietnamPro-BoldItalic.ttf",   "BeVietnamPro-BoldItalic.ttf"),

    # ── Nunito — Bo tròn, dễ thương ──
    (f"{BASE}/ofl/nunito/Nunito%5Bwght%5D.ttf",                 "Nunito-Variable.ttf"),
    (f"{BASE}/ofl/nunito/NunitoItalic%5Bwght%5D.ttf",           "Nunito-Italic-Variable.ttf"),

    # ── Poppins — Hiện đại, sắc nét ──
    (f"{BASE}/ofl/poppins/Poppins-Bold.ttf",                    "Poppins-Bold.ttf"),
    (f"{BASE}/ofl/poppins/Poppins-Regular.ttf",                 "Poppins-Regular.ttf"),
    (f"{BASE}/ofl/poppins/Poppins-SemiBold.ttf",                "Poppins-SemiBold.ttf"),
    (f"{BASE}/ofl/poppins/Poppins-Italic.ttf",                  "Poppins-Italic.ttf"),
    (f"{BASE}/ofl/poppins/Poppins-BoldItalic.ttf",              "Poppins-BoldItalic.ttf"),

    # ── Roboto — Thanh lịch, thông dụng ──
    (f"{BASE}/apache/roboto/Roboto-Bold.ttf",                   "Roboto-Bold.ttf"),
    (f"{BASE}/apache/roboto/Roboto-Regular.ttf",                "Roboto-Regular.ttf"),
    (f"{BASE}/apache/roboto/Roboto-Italic.ttf",                 "Roboto-Italic.ttf"),

    # ── Baloo 2 — Vui nhộn, phù hợp trẻ em ──
    (f"{BASE}/ofl/baloo2/Baloo2%5Bwght%5D.ttf",                 "Baloo2-Variable.ttf"),

    # ── Quicksand — Mềm mại ──
    (f"{BASE}/ofl/quicksand/Quicksand%5Bwght%5D.ttf",           "Quicksand-Variable.ttf"),

    # ── Cabin — Gọn gàng, dễ đọc ──
    (f"{BASE}/ofl/cabin/Cabin%5Bwdth%2Cwght%5D.ttf",            "Cabin-Variable.ttf"),
    (f"{BASE}/ofl/cabin/CabinItalic%5Bwdth%2Cwght%5D.ttf",     "Cabin-Italic-Variable.ttf"),

    # ── Comfortaa — Tròn trịa, thân thiện ──
    (f"{BASE}/ofl/comfortaa/Comfortaa%5Bwght%5D.ttf",           "Comfortaa-Variable.ttf"),
]

def download(url: str, dest: Path, name: str):
    if dest.exists():
        print(f"  ✅ Đã có: {name}")
        return True
    try:
        print(f"  ⬇️  Đang tải: {name} ...", end="", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        dest.write_bytes(data)
        print(f"  ({len(data)//1024} KB)")
        return True
    except Exception as e:
        print(f"  ❌ Lỗi: {e}")
        return False

def main():
    print("=" * 55)
    print("  DOWNLOAD GOOGLE FONTS → fonts/")
    print("=" * 55)

    ok, fail = 0, 0
    for url, name in FONTS:
        dest = FONTS_DIR / name
        if download(url, dest, name):
            ok += 1
        else:
            fail += 1

    print(f"\n{'='*55}")
    print(f"  ✅ Thành công: {ok}   ❌ Thất bại: {fail}")
    print(f"  📁 Folder: {FONTS_DIR}")
    print(f"\n  Font names để dùng trong auto_edit.py:")
    for f in sorted(FONTS_DIR.glob("*.ttf")):
        print(f"    \"{f.name}\"")


if __name__ == "__main__":
    main()
