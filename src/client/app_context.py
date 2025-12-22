# client/app_context.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Callable, Optional

class TkApp(Protocol):
    def after(self, ms: int, func: Callable[[], None]) -> str: ...
    def after_cancel(self, handle: str) -> None: ...

@dataclass
class AppContext:
    app: TkApp
