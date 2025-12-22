from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from PIL import Image, ImageTk

from assets import resolve_user_override

@dataclass
class WatermarkOverlay:
    user_filename: str = "watermark.png"
    opacity: float = 0.12  # tweak

    canvas: Optional[object] = None
    base_img: Optional[Image.Image] = None
    img_tk: Optional[ImageTk.PhotoImage] = None
    item: Optional[int] = None
    enabled: bool = True

    def init(self, canvas):
        self.canvas = canvas

        wm_path = resolve_user_override(self.user_filename, fallback_rel=None)
        if not wm_path:
            self.enabled = False
            return

        try:
            self.base_img = Image.open(wm_path).convert("RGBA")
        except Exception:
            self.enabled = False
            self.base_img = None
            return

        self.img_tk = ImageTk.PhotoImage(self.base_img)
        self.item = canvas.create_image(0, 0, image=self.img_tk, anchor="center", tags=("watermark",))

    def enable(self, value: bool):
        self.enabled = value
        if self.canvas is None or self.item is None:
            return
        self.canvas.itemconfigure(self.item, state=("normal" if value else "hidden"))

    def layout(self, w: int, h: int):
        if not self.enabled:
            return
        if self.canvas is None or self.item is None:
            return
        self.canvas.coords(self.item, w / 2, h / 2)
