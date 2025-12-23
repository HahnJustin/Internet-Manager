import selectors
import socket
import threading
from typing import Any, Callable, Optional
from client.app_context import AppContext
from client.message import Message
from libuniversal import Actions

global host, port, app

def create_request(action, value):
    global host, port
    if action in (Actions.SEARCH, Actions.USED_VOUCHER, Actions.UNUSED_VOUCHER,
              Actions.LOOT_OPEN, Actions.LOOT_CHECK,
              Actions.GET_LOOT, Actions.NEW_LOOT):
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=value),
        )

    elif action in (Actions.INTERNET_ON, Actions.INTERNET_OFF,
                    Actions.GRAB_CONFIG, Actions.ADMIN_STATUS,
                    Actions.INTERNET_STATUS, Actions.GRAB_STORAGE,
                    Actions.RELAPSE, Actions.ADD_VOUCHER,
                    Actions.CLOSE_SERVER, Actions.USED_RETROVOUCHER, 
                    Actions.UNUSED_RETROVOUCHER):
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action),
        )

    else:
        return dict(
            type="binary/custom-client-binary-type",
            encoding="binary",
            content=bytes(action + value, encoding="utf-8"),
        )

def start_connection(sel, host, port, request):
    addr = (host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = Message(sel, sock, addr, request)
    sel.register(sock, events, data=message)
    return message

def do_request(action, value):
    global host, port
    request = create_request(action, value)

    sel = selectors.DefaultSelector()
    try:
        msg = start_connection(sel, host, port, request)

        while True:
            events = sel.select(timeout=1)
            for key, mask in events:
                message = key.data
                message.process_events(mask)

            if not sel.get_map():
                return msg.result
    finally:
        sel.close()

def do_request_async(action, value="", on_done: Optional[Callable[[Any], None]] = None):
    if _ctx is None:
        raise RuntimeError("client_api not initialized. Call client_api.set_app(AppContext(app)) first.")
    if on_done is None:
        on_done = lambda _res: None

    def worker():
        try:
            result = do_request(action, value)   # your sync request
        except Exception as e:
            result = e
        _ctx.app.after(0, lambda: on_done(result))

    threading.Thread(target=worker, daemon=True).start()

def init(host_number, port_number):
    global host, port
    host = host_number
    port = port_number

def set_app(ctx: AppContext) -> None:
    global _ctx
    _ctx = ctx