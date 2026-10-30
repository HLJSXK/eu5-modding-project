"""SOL-compatible entry point; implementation lives in eu5-modding-base."""
import os
import runpy
from pathlib import Path

_workspace = Path(__file__).resolve().parents[2]
_base_root = _workspace / ".eu5-base"
if not _base_root.is_dir():
    _base_root = _workspace.parent / "eu5-modding-base"
_base = _base_root / "ai_gui_assessment" / "renderer"
os.environ.setdefault("EU5_RENDER_WORKSPACE", str(_workspace))
os.environ.setdefault("EU5_RENDER_MOD_ROOT", str(_workspace / "src" / "stable"))
os.environ.setdefault("EU5_RENDER_OUTPUT_ROOT", str(_workspace / "ai_gui_assessment" / "images"))
if __name__ == "__main__":
    runpy.run_path(str(_base / "guidef.py"), run_name="__main__")
