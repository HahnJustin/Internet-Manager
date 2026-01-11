# utilities/server_control.py
from __future__ import annotations

import json
import os
import socket
import struct
import sys
from typing import Any

import configreader
from libuniversal import Actions, ConfigKey

def _read_host_port() -> tuple[str, int]:
    """
    Read host/port from config.json via configreader (same as server does).
    Falls back safely.
    """
    try:
        configreader.init()
        cfg = configreader.get_config() or {}

        host = cfg.get(ConfigKey.HOST.value, "127.0.0.1")
        port = int(cfg.get(ConfigKey.PORT.value, 65432))
        return str(host), port
    except Exception:
        return "127.0.0.1", 65432


def _build_framed_json_request(content_obj: dict[str, Any]) -> bytes:
    content_bytes = json.dumps(content_obj, ensure_ascii=False).encode("utf-8")

    jsonheader = {
        "byteorder": sys.byteorder,
        "content-type": "text/json",
        "content-encoding": "utf-8",
        "content-length": len(content_bytes),
    }
    jsonheader_bytes = json.dumps(jsonheader, ensure_ascii=False).encode("utf-8")

    message_hdr = struct.pack(">H", len(jsonheader_bytes))
    return message_hdr + jsonheader_bytes + content_bytes


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed while reading.")
        buf += chunk
    return buf


def _read_framed_json_response(sock: socket.socket) -> dict[str, Any]:
    hdr = _recv_exact(sock, 2)
    (jsonhdr_len,) = struct.unpack(">H", hdr)

    jsonhdr_bytes = _recv_exact(sock, jsonhdr_len)
    jsonhdr = json.loads(jsonhdr_bytes.decode("utf-8"))

    content_len = int(jsonhdr["content-length"])
    content_bytes = _recv_exact(sock, content_len)

    if jsonhdr.get("content-type") == "text/json":
        encoding = jsonhdr.get("content-encoding", "utf-8")
        return json.loads(content_bytes.decode(encoding))

    return {"_raw": content_bytes}


def close_server(timeout_sec: float = 2.0, verbose: bool = True) -> bool:
    host, port = _read_host_port()
    req = {"action": Actions.CLOSE_SERVER}  # str-backed enum → JSON string

    msg = _build_framed_json_request(req)

    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as s:
            s.settimeout(timeout_sec)
            s.sendall(msg)

            # You might not get a response if server exits quickly,
            # but if you do, print it.
            try:
                resp = _read_framed_json_response(s)
                if verbose:
                    print("Server response:", resp)
            except Exception as e:
                if verbose:
                    print("No readable response (may have exited quickly):", repr(e))

        return True
    except Exception as e:
        if verbose:
            print(f"Failed to connect/send to {host}:{port}:", repr(e))
        return False
