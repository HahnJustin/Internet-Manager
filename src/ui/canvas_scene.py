from __future__ import annotations
from dataclasses import dataclass

@dataclass
class CanvasScene:
    canvas: object
    background: object
    watermark: object
    loot: object
    status: object
    bottom: object

    def init(self):
        # Give everyone the canvas and create their items
        self.background.init(self.canvas)
        self.watermark.init(self.canvas)
        self.loot.init(self.canvas)
        self.status.init(self.canvas)
        self.bottom.init(self.canvas)

        # One resize binding, one layout pipeline
        self.canvas.bind("<Configure>", self._on_resize)

        # Initial layout
        self.layout()

    def _on_resize(self, _e=None):
        self.layout()

    def layout(self, _event=None):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            return

        # Let each overlay update itself
        self.background.layout(w, h)

        # Tag-based z-order (no cross-module globals)
        self.enforce_zorder()

        self.watermark.layout(w, h)
        self.loot.layout(w, h)
        self.status.layout(w, h)
        self.bottom.layout(w, h)

    def enforce_zorder(self):
        c = self.canvas
        # bottom-most
        c.tag_lower("bg")

        # watermark just above bg
        c.tag_raise("watermark", "bg")

        # overlays above watermark
        for tag in ("status", "loot", "bottomui", "relapsebtn"):
            c.tag_raise(tag, "watermark")
