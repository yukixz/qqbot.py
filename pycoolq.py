# coding: UTF-8
import re
import socket
import collections
from urllib.parse import quote, unquote
from circuits import handler
from circuits.net.sockets import TCPServer

ReceivedMessage = collections.namedtuple(
    'ReceivedMessage',
    ('sourceType', 'fromGroupID', 'fromID', 'content')
)

SendMessage = collections.namedtuple(
    'SendMessage',
    ('destinationType', 'destinationID', 'content')
)

re_cq_special = re.compile(r'\[CQ:(face|emoji|at|shake|music|anonymous|image|record)(,\w+=[^]]+)?\]')


class messagePreprocessor(TCPServer):
    @handler("read")
    def on_read(self, sock, data):
        self.qqMessageHandlerExecutor(data)
        return 0

    def setMessageHandlers(self, handlers):
        self.messageHandlers = handlers

    def qqMessageHandlerExecutor(self, data):
        dataParts = data.decode().split(" ")
        message = None

        if dataParts[0] in ("group", "discuss"):
            sendGroup = int(dataParts[1])
            sender = int(dataParts[2])
            msg = unquote(dataParts[3], encoding='gbk')
            message = ReceivedMessage(sourceType=dataParts[0],
                                      fromGroupID=sendGroup,
                                      fromID=sender,
                                      content=msg)
        elif dataParts[0] == 'private':
            sender = int(dataParts[1])
            msg = unquote(dataParts[2], encoding='gbk')
            message = ReceivedMessage(sourceType=dataParts[0],
                                      fromGroupID=0,
                                      fromID=sender,
                                      content=msg)

        if message is None:
            print("!! Parse message error:", data)
            return
        for h in self.messageHandlers:
            if h(message):
                break


class coolqBot():
    def __init__(self, py2cqPort, cq2pyPort):
        self.sendPort = py2cqPort
        self.receivePort = cq2pyPort
        self.messageHandlers = []

        self.sock = socket.socket(type=socket.SOCK_DGRAM)
        self.sock.connect(("127.0.0.1", self.sendPort))
        self.listener = messagePreprocessor(("0.0.0.0", self.receivePort))
        self.listener.setMessageHandlers(self.messageHandlers)

    def send(self, message):
        data = "{0} {1} {2}".format(
            message.destinationType,
            message.destinationID,
            quote(message.content, encoding="utf-8")
            )
        self.sock.send(data.encode())
        return 0

    def start(self):
        self.listener.start()

    def messageHandler(self):
        def decorator(handler):
            self.messageHandlers.append(handler)
            return handler

        return decorator
