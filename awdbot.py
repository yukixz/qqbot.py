#!/usr/bin/env python3

import os
import threading
import time
import traceback
from collections import namedtuple
from configparser import ConfigParser
from urllib.request import urlretrieve

from apscheduler.schedulers.background import BackgroundScheduler
from cqbot import CQBot, CQAt, CQImage, RcvdPrivateMessage, RcvdGroupMessage
from utils import reply

TTL = 604800  # 7 Day (Seconds)
CQ_IMAGE_ROOT = r'C:/Users/Administrator/Desktop/CoolQ/data/image'
POI_GROUP = '378320628'
ADMIN_QQ = ('412632991', )

qqbot = CQBot(11235)
scheduler = BackgroundScheduler(
    timezone='Asia/Tokyo',
    job_defaults={'misfire_grace_time': 60},
    )

Message = namedtuple('Manifest', ('qq', 'time', 'text'))
messages = []


@qqbot.listener((RcvdGroupMessage, ))
def blacklist(message):
    # Restrict to Poi group
    if isinstance(message, RcvdGroupMessage) and message.group != POI_GROUP:
        return True


@qqbot.listener((RcvdGroupMessage, RcvdPrivateMessage))
def command(message):
    # Restrict to admin
    if message.qq not in ADMIN_QQ:
        return
    # Parse message
    try:
        texts = message.text.split()
        cmd = texts[0]
        qq = texts[1]
        idx = texts[2:]
    except:
        return
    if cmd != '/awd':
        return

    match = CQAt.PATTERN.fullmatch(qq)
    if match and match.group(1):
        qq = match.group(1)
    try:
        idx = list(map(lambda x: int(x), idx))
    except:
        idx = []
    if len(idx) == 0:
        idx = [0]

    items = list(filter(lambda x: x.qq == qq, messages))
    items.reverse()
    for i in idx:
        try:
            item = items[i]
        except:
            continue
        reply(qqbot, message, "[awd] {qq} # {i}\n{text}".format(
                i=i, qq=CQAt(item.qq), text=item.text))


@qqbot.listener((RcvdGroupMessage, ))
def new(message):
    messages.append(Message(message.qq, int(time.time()), message.text))

    for match in CQImage.PATTERN.finditer(message.text):
        try:
            filename = match.group(1)
            ImageDownloader(filename).start()
        except:
            print(message)
            traceback.print_exc()


class ImageDownloader(threading.Thread):
    def __init__(self, filename, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filename = filename

    def run(self):
        try:
            path = os.path.join(CQ_IMAGE_ROOT, self.filename)
            if os.path.exists(path):
                return

            cqimg = os.path.join(CQ_IMAGE_ROOT, self.filename + '.cqimg')
            parser = ConfigParser()
            parser.read(cqimg)

            url = parser['image']['url']
            urlretrieve(url, path)
        except:
            print('===>', self.filename)
            traceback.print_exc()


@scheduler.scheduled_job('cron', minute='*/10')
def clean():
    global messages
    ttl_time = int(time.time()) - TTL

    new_messages = []
    old_messages = []
    for item in messages:
        if item.time >= ttl_time:
            new_messages.append(item)
        else:
            old_messages.append(item)
    messages = new_messages

    images = []
    for item in old_messages:
        for match in CQImage.PATTERN.finditer(item.text):
            images.append(match.group(1))
    for item in new_messages:
        for match in CQImage.PATTERN.finditer(item.text):
            try:
                images.remove(match.group(1))
            except ValueError:
                pass
    for filename in images:
        try:
            path = os.path.join(CQ_IMAGE_ROOT, filename)
            os.remove(path)
        except FileNotFoundError:
            pass


if __name__ == '__main__':
    try:
        qqbot.start()
        # scheduler.start()

        print("Running...")
        input()
    except KeyboardInterrupt:
        pass
