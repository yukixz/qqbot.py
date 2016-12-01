#!/usr/bin/env python3
# coding: UTF-8

import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from cqsdk import CQBot, \
    RcvdPrivateMessage, RcvdGroupMessage, SendPrivateMessage
from utils import reply


qqbot = CQBot(11235)
scheduler = BackgroundScheduler(
    timezone='Asia/Tokyo',
    job_defaults={'misfire_grace_time': 60},
    )


################
# Online
################
class ONLINE:
    ADMIN = ['412632991', '694692391']
    TOLERANCE = timedelta(minutes=10)
    last = datetime.now()
    notified_last = None


@qqbot.listener((RcvdPrivateMessage, RcvdGroupMessage))
def update(message):
    ONLINE.last = datetime.now()


@qqbot.listener((RcvdPrivateMessage, ))
def commmand(message):
    if message.qq not in ONLINE.ADMIN:
        return
    if message.text != "/online":
        return
    text = '\n'.join([
        "ONLINE",
        "Last message at {last}.",
    ]).format(tolerance=ONLINE.TOLERANCE, last=ONLINE.last)
    reply(qqbot, message, text)


@scheduler.scheduled_job('cron', minute='*')
def check():
    now = datetime.now()
    last = ONLINE.last
    if (now - last) < ONLINE.TOLERANCE or ONLINE.notified_last == last:
        return
    ONLINE.notified_last = last
    text = '\n'.join([
        "** WARNING **",
        "No message for {tolerance}. Restarting CoolQ.",
        "If you don't receive finish message in 2 mintues, "  # No comma
        "send /online to check or restart manually."
        ]).format(tolerance=ONLINE.TOLERANCE)
    for qq in ONLINE.ADMIN:
        qqbot.send(SendPrivateMessage(qq=qq, text=text))
    time.sleep(10)  # Wait for warn message sending
    Restarter().start()


class Restarter(threading.Thread):
    def run(self):
        logging.warn("Stopping CoolQ")
        os.system("taskkill /F /T /IM CQP.exe")
        time.sleep(10)
        logging.warn("Starting CoolQ")
        subprocess.Popen([
            "C:/Users/dazzy/Desktop/CoolQ/CQP.exe",
            "/account", "1695676191"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(10)
        logging.warn("Sending finish message")
        text = '\n'.join([
            "** INFO **",
            "Restart has finished.",
            ])
        for qq in ONLINE.ADMIN:
            qqbot.send(SendPrivateMessage(qq=qq, text=text))


################
# __main__
################
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.WARNING,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(funcName)s: %(message)s",
        )
    try:
        qqbot.start()
        scheduler.start()
        print("Running...")
        input()
        print("Stopping...")
    except KeyboardInterrupt:
        pass
