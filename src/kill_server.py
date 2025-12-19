import yaml
import socket
import selectors
import traceback
from client.message import Message

from libuniversal import Actions, ConfigKey, Paths

#TODO: Most of the functions in the class are in gui.py
#Could easily make another lib or util class to house these

def start_connection(host, port, request):
    addr = (host, port)
    print(f"Starting connection to {addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = message.Message(sel, sock, addr, request)
    sel.register(sock, events, data=message)

def do_request(action, value) -> str:
    global sel

    request = create_request(action, value)
    start_connection(host, port, request)

    try:
        while True:
            message = None
            events = sel.select(timeout=1)
            print(f"Events {events}")
            for key, mask in events:
                message = key.data
                try:
                    print("processing message")
                    message.process_events(mask)
                except Exception:
                    print(
                        f"Main: Error: Exception for {message.addr}:\n"
                        f"{traceback.format_exc()}"
                    )
                    message.close()
            # Check for a socket being monitored to continue.
            if not sel.get_map():
                return message.result
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")

def create_request(action, value):
    if action == Actions.SEARCH or Actions.USED_VOUCHER or Actions.UNUSED_VOUCHER:
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=value),
        )
    elif( action == Actions.INTERNET_ON or action == Actions.INTERNET_OFF or 
          action == Actions.GRAB_CONFIG or action == Actions.ADMIN_STATUS or
          action == Actions.INTERNET_STATUS or action == Actions.GRAB_STORAGE or
          action == Actions.RELAPSE or action == Actions.ADD_VOUCHER or 
          action == Actions.KILL_SERVER):
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

sel = selectors.DefaultSelector()

# Reading config
try:
    f = open(Paths.CLIENT_CONFIG_FILE)
except OSError:
    cfg = {ConfigKey.HOST.value: str("127.0.0.1"), ConfigKey.PORT.value : 65432}
    with open(Paths.CLIENT_CONFIG_FILE, 'w') as yaml_file:
        yaml.dump(cfg, yaml_file)
    f = open(Paths.CLIENT_CONFIG_FILE)
with f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)
    host = cfg[ConfigKey.HOST]
    port = cfg[ConfigKey.PORT]

cfg = do_request(Actions.KILL_SERVER, "")