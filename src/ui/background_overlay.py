from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from PIL import Image, ImageTk

# These should exist in your assets.py (you already had them in your big file)
from assets import resolve_user_override

@dataclass
class BackgroundOverlay:
    user_filename: str = "background.png"

    canvas: Optional[object] = None
    tile_base: Optional[Image.Image] = None
    item: Optional[int] = None
    img_tk: Optional[ImageTk.PhotoImage] = None
    last_size: tuple[int, int] = (0, 0)

    def init(self, canvas):
        self.canvas = canvas

        bg_path = resolve_user_override(self.user_filename, fallback_rel=None)
        if not bg_path:
            return

        try:
            self.tile_base = Image.open(bg_path).convert("RGBA")
        except Exception:
            self.tile_base = None
            return

        self.item = canvas.create_image(0, 0, anchor="nw", tags=("bg",))
        self.last_size = (0, 0)

    def layout(self, w: int, h: int):
        if self.canvas is None or self.tile_base is None or self.item is None:
            return
        if w < 2 or h < 2:
            return
        if (w, h) == self.last_size:
            return

        tw, th = self.tile_base.size
        if tw <= 0 or th <= 0:
            return

        tiled = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for y in range(0, h, th):
            for x in range(0, w, tw):
                tiled.paste(self.tile_base, (x, y))

        self.img_tk = ImageTk.PhotoImage(tiled)
        self.canvas.itemconfigure(self.item, image=self.img_tk)
        self.canvas.coords(self.item, 0, 0)

        self.last_size = (w, h)
