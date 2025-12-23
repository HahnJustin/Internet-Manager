# ui/gui_text.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Tuple, List

@dataclass(frozen=True)
class _OutlineLayer:
    item_id: int
    dx: int
    dy: int

@dataclass
class OutlinedCanvasText:
    canvas: object
    main_id: int
    outline_layers: List[_OutlineLayer]
    base_tags: Tuple[str, ...]

    def set_text(self, text: str):
        self.canvas.itemconfigure(self.main_id, text=text)
        for layer in self.outline_layers:
            self.canvas.itemconfigure(layer.item_id, text=text)

    def set_state(self, state: str):
        self.canvas.itemconfigure(self.main_id, state=state)
        for layer in self.outline_layers:
            self.canvas.itemconfigure(layer.item_id, state=state)

    def coords(self, x: float, y: float):
        # main text
        self.canvas.coords(self.main_id, x, y)
        # outline text copies keep their offsets
        for layer in self.outline_layers:
            self.canvas.coords(layer.item_id, x + layer.dx, y + layer.dy)

        # ensure main is above outline
        try:
            self.canvas.tag_raise(self.main_id)
        except Exception:
            pass


def _outline_offsets(thickness: int) -> Iterable[tuple[int, int]]:
    """
    Generate pixel offsets for a thicker outline.
    Filled square ring (looks good for small fonts).
    """
    t = max(1, int(thickness))
    for dx in range(-t, t + 1):
        for dy in range(-t, t + 1):
            if dx == 0 and dy == 0:
                continue
            yield dx, dy


def create_outlined_text(
    canvas,
    x: float,
    y: float,
    *,
    text: str,
    font,
    anchor="center",
    fill="white",
    outline="black",
    thickness: int = 2,
    state="normal",
    tags=(),
) -> OutlinedCanvasText:
    # Ensure tags is a tuple
    if isinstance(tags, str):
        tags = (tags,)
    else:
        tags = tuple(tags)

    outline_layers: List[_OutlineLayer] = []

    # Create outline copies first (under the main text)
    for dx, dy in _outline_offsets(thickness):
        oid = canvas.create_text(
            x + dx, y + dy,
            text=text,
            fill=outline,
            font=font,
            anchor=anchor,
            state=state,
            tags=tags
        )
        outline_layers.append(_OutlineLayer(item_id=oid, dx=dx, dy=dy))

    # Main text on top
    main_id = canvas.create_text(
        x, y,
        text=text,
        fill=fill,
        font=font,
        anchor=anchor,
        state=state,
        tags=tags
    )

    # Make sure stacking order is correct immediately
    try:
        canvas.tag_raise(main_id)
    except Exception:
        pass

    return OutlinedCanvasText(
        canvas=canvas,
        main_id=main_id,
        outline_layers=outline_layers,
        base_tags=tags
    )
