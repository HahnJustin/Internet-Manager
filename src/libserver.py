import sys
import selectors
import json
import io
import struct
import threading
import internet_management
import configreader
from libuniversal import Actions, MessageKey

loot_box_gained = 0
loot_box_timer = None
_loot_lock = threading.Lock()

SHOULD_EXIT = False

class Message:
    def __init__(self, selector, sock, addr):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self._recv_buffer = b""
        self._send_buffer = b""
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None
        self.response_created = False

    def _set_selector_events_mask(self, mode):
        """Set selector to listen for events: mode is 'r', 'w', or 'rw'."""
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {mode!r}.")
        self.selector.modify(self.sock, events, data=self)

    def _read(self):
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")

    def _write(self):
        if self._send_buffer:
            print(f"Sending {self._send_buffer!r} to {self.addr}")
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]
                # Close when the buffer is drained. The response has been sent.
                if sent and not self._send_buffer:
                    self.close()

    def _json_encode(self, obj, encoding):
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(
        self, *, content_bytes, content_type, content_encoding
    ):
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        return message

    def _create_response_json_content(self):
        action = self.request.get("action")
        if action == Actions.SEARCH:
            query = self.request.get("value")
            answer = internet_management.request_search.get(query) or f"No match for '{query}'."
            content = {MessageKey.RESULT: answer}
        elif action == Actions.USED_VOUCHER:
            time = self.request.get("value")
            answer = configreader.use_voucher(time)
            content = {MessageKey.RESULT: answer}
        elif action == Actions.UNUSED_VOUCHER:
            time = self.request.get("value")
            answer = configreader.unuse_voucher(time)
            content = {MessageKey.RESULT: answer}
        elif action == Actions.INTERNET_OFF:
            internet_management.turn_off_wifi()
            internet_management.turn_off_ethernet()
            content = {MessageKey.RESULT: "attempted to turn off internet"}
        elif action == Actions.INTERNET_ON:
            internet_management.turn_on_wifi()
            internet_management.turn_on_ethernet()
            content = {MessageKey.RESULT: "attempted to turn on internet"}
        elif action == Actions.GRAB_CONFIG:
            cfg = configreader.get_config()
            content = {MessageKey.RESULT: cfg}
        elif action == Actions.ADMIN_STATUS:
            admin = internet_management.is_admin()
            content = {MessageKey.RESULT: admin}
        elif action == Actions.INTERNET_STATUS:
            on = internet_management.is_internet_on()
            content = {MessageKey.RESULT: on}
        elif action == Actions.GRAB_STORAGE:
            storage = configreader.get_storage()
            content = {MessageKey.RESULT: storage}
        elif action == Actions.RELAPSE:
            internet_management.turn_on_wifi()
            internet_management.turn_on_ethernet()
            configreader.reset_relapse_time()
            configreader.set_manual_override(True)
            content = {MessageKey.RESULT: "attempted to turn on internet, relapse acknowledged"}
        elif action == Actions.CLOSE_SERVER:
            global SHOULD_EXIT
            SHOULD_EXIT = True
            content = {MessageKey.RESULT: "closing server"}
        elif action == Actions.LOOT_CHECK:
            lootbox_type = self.request.get("value")
            lootbox_amount = 0
            if lootbox_type == MessageKey.SHUTDOWN_LOOT_BOX:
                lootbox_amount = configreader.get_shutdown_loot_boxes()
            elif lootbox_type == MessageKey.NORMAL_LOOT_BOX:
                lootbox_amount = configreader.get_normal_loot_boxes()
            elif lootbox_type == MessageKey.ALL_LOOT_BOXES:
                lootbox_amount = configreader.get_all_loot_boxes()
            content = {MessageKey.RESULT: lootbox_amount}
        elif action == Actions.LOOT_OPEN:
            lootbox_type = self.request.get("value")
            voucher_amount = 0
            if lootbox_type == MessageKey.SHUTDOWN_LOOT_BOX:
                voucher_amount = configreader.open_shutdown_loot_box()
            elif lootbox_type == MessageKey.NORMAL_LOOT_BOX:
                voucher_amount = configreader.open_loot_box()
            stop_loot_box_timer()
            content = {MessageKey.RESULT: voucher_amount}
        elif action == Actions.NEW_LOOT:
            global loot_box_gained
            with _loot_lock:
                amt = loot_box_gained
                loot_box_gained = 0
            content = {MessageKey.RESULT: amt}
        elif action == Actions.GET_LOOT:
            key = configreader.get_a_loot_box()
            content = {MessageKey.RESULT: key}
        else:
            content = {MessageKey.RESULT: f"Error: invalid action '{action}'."}
        content_encoding = "utf-8"
        response = {
            "content_bytes": self._json_encode(content, content_encoding),
            "content_type": "text/json",
            "content_encoding": content_encoding,
        }
        return response

    def _create_response_binary_content(self):
        response = {
            "content_bytes": b"First 10 bytes of request: "
            + self.request[:10],
            "content_type": "binary/custom-server-binary-type",
            "content_encoding": "binary",
        }
        return response

    def process_events(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()

    def read(self):
        self._read()

        if self._jsonheader_len is None:
            self.process_protoheader()

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()

        if self.jsonheader:
            if self.request is None:
                self.process_request()

    def write(self):
        if self.request:
            if not self.response_created:
                self.create_response()

        self._write()

    def close(self):
        print(f"Closing connection to {self.addr}")
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            print(
                f"Error: selector.unregister() exception for "
                f"{self.addr}: {e!r}"
            )

        try:
            self.sock.close()
        except OSError as e:
            print(f"Error: socket.close() exception for {self.addr}: {e!r}")
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None

    def process_protoheader(self):
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(
                ">H", self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_jsonheader(self):
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self.jsonheader = self._json_decode(
                self._recv_buffer[:hdrlen], "utf-8"
            )
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                "byteorder",
                "content-length",
                "content-type",
                "content-encoding",
            ):
                if reqhdr not in self.jsonheader:
                    raise ValueError(f"Missing required header '{reqhdr}'.")

    def process_request(self):
        content_len = self.jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        if self.jsonheader["content-type"] == "text/json":
            encoding = self.jsonheader["content-encoding"]
            self.request = self._json_decode(data, encoding)
            print(f"Received request {self.request!r} from {self.addr}")
        else:
            # Binary or unknown content-type
            self.request = data
            print(
                f"Received {self.jsonheader['content-type']} "
                f"request from {self.addr}"
            )
        # Set selector to listen for write events, we're done reading.
        self._set_selector_events_mask("w")

    def create_response(self):
        if self.jsonheader["content-type"] == "text/json":
            response = self._create_response_json_content()
        else:
            # Binary or unknown content-type
            response = self._create_response_binary_content()
        message = self._create_message(**response)
        self.response_created = True
        self._send_buffer += message

def start_loot_box_timer(amount : int):
    global loot_box_timer
    global loot_box_gained
    with _loot_lock:
        if loot_box_timer != None: loot_box_timer.cancel()

        loot_box_gained = amount

        def reset_loot_box_flag():
            global loot_box_gained, loot_box_timer
            with _loot_lock:
                loot_box_gained = 0
                loot_box_timer = None

        loot_box_timer = threading.Timer(120, reset_loot_box_flag)
        loot_box_timer.daemon = True
        loot_box_timer.start()

def stop_loot_box_timer():
    global loot_box_gained
    global loot_box_timer

    with _loot_lock:
        if loot_box_timer != None: loot_box_timer.cancel()

        loot_box_gained = 0
        loot_box_timer = None