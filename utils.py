#!/use/bin/env python3

import sys
import threading
import traceback
from urllib.request import urlretrieve
from cqsdk import RE_CQ_SPECIAL, \
    RcvdPrivateMessage, RcvdGroupMessage, RcvdDiscussMessage, \
    SendPrivateMessage, SendGroupMessage, SendDiscussMessage, \
    GroupMemberDecrease, GroupMemberIncrease


def error(*args, **kwargs):
    print("================ ERROR ================", file=sys.stderr)
    print(*args, **kwargs, file=sys.stderr)


def match(text, keywords):
    for keyword in keywords:
        if keyword in text:
            return True
    return False


def reply(qqbot, message, text):
    reply_msg = None
    if isinstance(message, RcvdPrivateMessage):
        reply_msg = SendPrivateMessage(
            qq=message.qq,
            text=text,
            )
    if isinstance(message, RcvdGroupMessage):
        reply_msg = SendGroupMessage(
            group=message.group,
            text=text,
            )
    if isinstance(message, RcvdDiscussMessage):
        reply_msg = SendDiscussMessage(
            discuss=message.discuss,
            text=text,
            )
    if reply_msg:
        qqbot.send(reply_msg)
        print("↘", message)
        print("↗", reply_msg)


class FileDownloader(threading.Thread):
    def __init__(self, url, path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = url
        self.path = path

    def run(self):
        try:
            urlretrieve(self.url, self.path)
        except:
            error("ERROR downloading:", self.url, 'to', self.path)
            traceback.print_exc()
