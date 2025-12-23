from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from PIL import ImageTk

from assets import Paths
from ui.images import get_canvas_photo
from ui import gui_text


@dataclass
class StatusOverlay:
    canvas: Optional[object] = None

    item: Optional[int] = None
    img_tk: Optional[ImageTk.PhotoImage] = None

    # outlined text object returned by gui_text.create_outlined_text
    text_obj: Optional[object] = None

    visible: bool = False
    current_text: str = ""
    positive: bool = True

    def init(self, canvas):
        self.canvas = canvas

        # Ribbon image
        self.item = canvas.create_image(
            0, 0, anchor="n", state="hidden", tags=("status",)
        )

        # Outlined text (white with black outline)
        # Give it its own tag so we can move all layers in layout()
        self.text_obj = gui_text.create_outlined_text(
            canvas,
            0, 0,
            text="",
            fill="white",
            outline="black",
            thickness=1,
            font=("DreiFraktur", 11),
            anchor="n",
            state="hidden",
            tags=("status", "status_text")
        )

    def show(self, text: str, positive: bool):
        if self.canvas is None or self.item is None:
            return

        self.visible = True
        self.current_text = text
        self.positive = positive

        ribbon_path = Paths.ASSETS_FOLDER + ("/blue_ribbon.png" if positive else "/red_ribbon.png")
        self.img_tk = get_canvas_photo(self.canvas, ribbon_path)

        self.canvas.itemconfigure(self.item, image=self.img_tk, state="normal")

        if self.text_obj is not None:
            self.text_obj.set_text(text)

        # show all status-tagged items (ribbon + outlined text layers)
        self.canvas.itemconfigure("status", state="normal")

    def hide(self):
        self.visible = False
        if self.canvas is None:
            return
        self.canvas.itemconfigure("status", state="hidden")

    def layout(self, w: int, h: int):
        if not self.visible or self.canvas is None or self.item is None:
            return

        top_pad = -4
        self.canvas.coords(self.item, w / 2, top_pad)

        rh = 40
        try:
            if self.img_tk is not None:
                rh = self.img_tk.height() / 1.5
        except Exception:
            pass

        tx = w / 2
        ty = top_pad + rh * 0.42 + 4  # slightly lower

        if self.text_obj is not None:
            self.text_obj.coords(tx, ty)

