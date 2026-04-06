# -*- coding: utf-8 -*-
r"""
AUTO VIDEO EDITOR - MAIN ENTRY POINT

Lenh chay: .\.venv\Scripts\python.exe main.py
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# Global exception handler — bắt mọi crash
def _exception_hook(exc_type, exc_value, exc_tb):
    import traceback
    traceback.print_exception(exc_type, exc_value, exc_tb)
    # Không thoát app khi exception trong thread
    if exc_type != KeyboardInterrupt:
        print(f"[CRASH] {exc_type.__name__}: {exc_value}", flush=True)


sys.excepthook = _exception_hook


def main():
    print("=" * 55)
    print("  AUTO VIDEO EDITOR")
    print("=" * 55)
    from app_ui import run_app
    run_app()


if __name__ == "__main__":
    main()
