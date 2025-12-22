import os
from libuniversal import Paths, app_base_dir, resource_path
from PIL import Image, ImageTk, ImageDraw
from customtkinter import CTkImage

canvas_img_cache = {}          # cache PhotoImage objects so clicks don't stutter
_canvas_shape_cache = {}

def storage_dir() -> str:
    """
    Folder where storage.json lives.
    If Paths.JSON_FILE is relative, anchor it to the app folder (not cwd).
    """
    json_path = Paths.JSON_FILE
    if not os.path.isabs(json_path):
        json_path = os.path.join(app_base_dir(), json_path)
    return os.path.dirname(os.path.abspath(json_path))

def custom_dir() -> str:
    d = os.path.join(storage_dir(), "custom")
    os.makedirs(d, exist_ok=True)
    return d

def resolve_user_override(filename: str, fallback_rel: str | None = None) -> str | None:
    """
    Search order:
      1) <storage_dir>/custom/<filename>
      2) <storage_dir>/<filename>
      3) packaged fallback (resource_path) if provided
    """
    p1 = os.path.join(custom_dir(), filename)
    if os.path.exists(p1):
        return p1

    p2 = os.path.join(storage_dir(), filename)
    if os.path.exists(p2):
        return p2

    if fallback_rel is None:
        return None
    return resource_path(fallback_rel)