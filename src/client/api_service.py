# client/api_service.py
from typing import Callable, Optional, Any
from client import client_api
from client.app_context import AppContext

class ApiService:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def request(self, action, key) -> Any:
        return client_api.do_request(action, key)

    def request_async(self, action, key, on_done: Optional[Callable[[Any], None]] = None):
        root = self.ctx.app

        def _cb(result):
            if on_done is None:
                return
            # marshal to tkinter thread
            root.after(0, lambda: on_done(result))

        client_api.do_request_async(action, key, _cb)