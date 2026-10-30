"""Compatibility import: the shared renderer lives in eu5-modding-base."""
import importlib
import os
import sys
from pathlib import Path

_workspace = Path(__file__).resolve().parents[2]
_base_root = _workspace / ".eu5-base"
if not _base_root.is_dir():
    _base_root = _workspace.parent / "eu5-modding-base"
_base_renderer = _base_root / "ai_gui_assessment" / "renderer"
os.environ.setdefault("EU5_RENDER_WORKSPACE", str(_workspace))
os.environ.setdefault("EU5_RENDER_MOD_ROOT", str(_workspace / "src" / "stable"))
os.environ.setdefault("EU5_RENDER_OUTPUT_ROOT", str(_workspace / "ai_gui_assessment" / "images"))
if str(_base_renderer) not in sys.path:
    sys.path.insert(0, str(_base_renderer))
sys.modules[__name__] = importlib.import_module("eu5_gui_renderer.text")
