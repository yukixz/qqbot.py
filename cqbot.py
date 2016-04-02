#!/usr/bin/env python3

import socket
import socketserver
import sys
import threading
import traceback
from base64 import b64encode, b64decode
from collections import namedtuple


RcvdPrivateMessage = namedtuple("RcvdPrivateMessage", ("qq", "text"))
SendPrivateMessage = namedtuple("SendPrivateMessage", ("qq", "text"))

RcvdGroupMessage = namedtuple("RcvdGroupMessage", ("group", "qq", "text"))
SendGroupMessage = namedtuple("SendGroupMessage", ("group", "text"))

FrameType = namedtuple("FrameType", ("prefix", "rcvd", "send"))
FRAME_TYPES = (
    FrameType("PrivateMessage", RcvdPrivateMessage, SendPrivateMessage),
    FrameType("GroupMessage", RcvdGroupMessage, SendGroupMessage),
)


def load_frame(data):
    if isinstance(data, str):
        parts = data.split()
    elif isinstance(data, list):
        parts = data
    else:
        raise TypeError()

    frame = None
    (prefix, *payload) = parts
    for type_ in FRAME_TYPES:
        if prefix == type_.prefix:
            frame = type_.rcvd(*payload)
    # decode text
    if isinstance(frame, (RcvdPrivateMessage, RcvdGroupMessage)):
        payload[-1] = b64decode(payload[-1]).decode('gbk')
        frame = type(frame)(*payload)
    return frame


def dump_frame(frame):
    if isinstance(frame, tuple):
        payload = list(frame)
    else:
        raise TypeError()

    data = None
    # encode text
    if isinstance(frame, (SendPrivateMessage, SendGroupMessage)):
        payload[-1] = b64encode(payload[-1].encode('gbk')).decode()
    for type_ in FRAME_TYPES:
        if isinstance(frame, type_.send):
            data = " ".join((type_.prefix, *payload))
    return data


class APIRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0].decode()
        parts = data.split()

        message = load_frame(parts)
        if message is None:
            print("Unknown message", parts, file=sys.stderr)

        for handler in self.server.handlers:
            try:
                if handler(message):
                    break
            except:
                traceback.print_exc()


class APIServer(socketserver.UDPServer):
    handlers = []


class CQBot():
    def __init__(self, server_port, client_port):
        self.remote_addr = ("127.0.0.1", server_port)
        self.local_addr = ("127.0.0.1", client_port)
        self.handlers = []

        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server = APIServer(self.local_addr, APIRequestHandler)
        self.threaded_server = threading.Thread(
            target=self.server.serve_forever
            )
        self.threaded_server.daemon = True

    def __del__(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()

    def start(self):
        self.server.handlers = self.handlers
        self.threaded_server.start()

    def handler(self, handler):
        self.handlers.append(handler)
        return handler

    def send(self, message):
        data = dump_frame(message).encode()
        self.client.sendto(data, self.remote_addr)


if __name__ == '__main__':
    try:
        qqbot = CQBot(11231, 11232)

        @qqbot.handler
        def log(message):
            if isinstance(message, (RcvdPrivateMessage, RcvdGroupMessage)):
                print(message)

        qqbot.start()
        print("QQBot is running...")
        input()
    except KeyboardInterrupt:
        pass
