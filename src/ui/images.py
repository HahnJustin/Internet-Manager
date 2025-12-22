# images.py
from __future__ import annotations
import os
from typing import Dict, Tuple, Any
from PIL import Image, ImageTk, ImageDraw
from customtkinter import CTkImage
from domain.models import TimeActionKind
from libuniversal import Paths, app_base_dir, resource_path

# Cache keyed by (master_id, full_path)
_canvas_img_cache: Dict[Tuple[int, str], ImageTk.PhotoImage] = {}
_canvas_shape_cache: Dict[Tuple[int, int, int, int, tuple], ImageTk.PhotoImage] = {}

# Optional: cache PIL images by full path so disk IO is avoided (safe)
_pil_cache: Dict[str, Image.Image] = {}

# NEW: cache CTkImages by full path (and size) so we don't recreate constantly
_ctk_image_cache: Dict[Tuple[str, int, int], CTkImage] = {}


def _load_pil_rgba(full_path: str) -> Image.Image:
    img = _pil_cache.get(full_path)
    if img is None:
        img = Image.open(full_path).convert("RGBA")
        _pil_cache[full_path] = img
    return img


def get_canvas_photo(master: Any, asset_rel_path: str) -> ImageTk.PhotoImage:
    full = resource_path(asset_rel_path)
    key = (id(master), full)

    img = _canvas_img_cache.get(key)
    if img is None:
        pil = _load_pil_rgba(full)
        img = ImageTk.PhotoImage(pil, master=master)
        _canvas_img_cache[key] = img
    return img


def get_round_rect_photo(master: Any, w: int, h: int, r: int, rgba: tuple) -> ImageTk.PhotoImage:
    key = (id(master), w, h, r, rgba)
    img = _canvas_shape_cache.get(key)
    if img is not None:
        return img

    pil = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(pil)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=rgba)

    tk_img = ImageTk.PhotoImage(pil, master=master)
    _canvas_shape_cache[key] = tk_img
    return tk_img


def get_image(path: str) -> CTkImage:
    """
    CTkImage is fine for CustomTkinter widgets; DO NOT use on tkinter.Canvas
    """
    full = resource_path(path)
    pil = _load_pil_rgba(full)

    key = (full, pil.width, pil.height)
    cached = _ctk_image_cache.get(key)
    if cached is not None:
        return cached

    img = CTkImage(pil, size=(pil.width, pil.height))
    _ctk_image_cache[key] = img
    return img

def get_time_action_icon(kind: TimeActionKind) -> CTkImage:
    if kind == TimeActionKind.SHUTDOWN:
        path = Paths.ASSETS_FOLDER + "/no_globe.png"
    elif kind == TimeActionKind.INTERNET_UP:
        path = Paths.ASSETS_FOLDER + "/globe.png"
    elif kind == TimeActionKind.VOUCHER:
        path = Paths.ASSETS_FOLDER + "/mini_voucher.png"
    elif kind == TimeActionKind.RETROVOUCHER:
        path = Paths.ASSETS_FOLDER + "/mini_voucher.png"
    else:
        path = Paths.ASSETS_FOLDER + "/skull_globe.png"
    return get_image(path)

def get_streak_icon(streak: int) -> CTkImage:
    path = ""
    if streak < 15:
        path = Paths.ASSETS_FOLDER + "/streak.png"
    elif streak < 30:
        path = Paths.ASSETS_FOLDER + "/streak1half.png"
    elif streak < 45:
        path = Paths.ASSETS_FOLDER + "/streak2.png"
    elif streak < 60:
        path = Paths.ASSETS_FOLDER + "/streak3.png"
    elif streak < 120:
        path = Paths.ASSETS_FOLDER + "/streak_mid.png"
    elif streak < 180:
        path = Paths.ASSETS_FOLDER + "/streak_mid1half.png"
    elif streak < 240:
        path = Paths.ASSETS_FOLDER + "/streak_mid2.png"
    elif streak < 300:
        path = Paths.ASSETS_FOLDER + "/streak_mid3.png"
    elif streak < 365:
        path = Paths.ASSETS_FOLDER + "/streak_mid4.png"
    elif streak < 548:
        path = Paths.ASSETS_FOLDER + "/streak_big.png"
    elif streak < 730:
        path = Paths.ASSETS_FOLDER + "/streak_big1half.png"
    elif streak < 913:
        path = Paths.ASSETS_FOLDER + "/streak_big2.png"
    elif streak < 1095:
        path = Paths.ASSETS_FOLDER + "/streak_big3.png"
    else:
        path = Paths.ASSETS_FOLDER + "/streak_big4.png"
    return get_image(path)
