from dataclasses import dataclass
import tkinter

@dataclass
class OutlinedCanvasText:
    canvas: tkinter.Canvas
    main: int
    outline: list[int]
    offsets: list[tuple[int, int]]

    def set_text(self, text: str):
        self.canvas.itemconfigure(self.main, text=text)
        for oid in self.outline:
            self.canvas.itemconfigure(oid, text=text)

    def set_state(self, state: str):
        self.canvas.itemconfigure(self.main, state=state)
        for oid in self.outline:
            self.canvas.itemconfigure(oid, state=state)

    def set_fill(self, fill: str):
        self.canvas.itemconfigure(self.main, fill=fill)

    def set_outline_fill(self, fill: str):
        for oid in self.outline:
            self.canvas.itemconfigure(oid, fill=fill)

    def move(self, x: float, y: float):
        self.canvas.coords(self.main, x, y)
        for oid, (dx, dy) in zip(self.outline, self.offsets):
            self.canvas.coords(oid, x + dx, y + dy)

    def raise_to_top(self):
        for oid in self.outline:
            self.canvas.tag_raise(oid)
        self.canvas.tag_raise(self.main)

def create_outlined_text(
    canvas: tkinter.Canvas,
    x: float, y: float,
    *,
    text: str = "",
    font=None,
    anchor: str = "center",
    fill: str = "white",
    outline: str = "black",
    thickness: int = 2,
    state: str = "normal",
    tags=()
) -> OutlinedCanvasText:
    # 8-direction stroke
    offsets = [
        (-thickness, -thickness), (0, -thickness), (thickness, -thickness),
        (-thickness, 0),                          (thickness, 0),
        (-thickness, thickness),  (0, thickness), (thickness, thickness),
    ]

    outline_ids = [
        canvas.create_text(
            x + dx, y + dy,
            text=text, fill=outline, font=font,
            anchor=anchor, state=state, tags=tags
        )
        for (dx, dy) in offsets
    ]

    main_id = canvas.create_text(
        x, y,
        text=text, fill=fill, font=font,
        anchor=anchor, state=state, tags=tags
    )

    # Ensure the white text is above the outline
    for oid in outline_ids:
        canvas.tag_lower(oid, main_id)

    return OutlinedCanvasText(canvas, main_id, outline_ids, offsets)
