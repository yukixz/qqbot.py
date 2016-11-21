#!/usr/bin/env python3
# coding: UTF-8

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
    if (now - ONLINE.last) < ONLINE.TOLERANCE:
        return
    text = '\n'.join([
        "WARNING",
        "No message within {tolerance}.",
        "Last message at {last}.",
        "Send /online to check.",
        ]).format(tolerance=ONLINE.TOLERANCE, last=ONLINE.last)
    for qq in ONLINE.ADMIN:
        qqbot.send(SendPrivateMessage(qq=qq, text=text))


################
# __main__
################
if __name__ == '__main__':
    try:
        qqbot.start()
        scheduler.start()
        print("Running...")
        input()
        print("Stopping...")
    except KeyboardInterrupt:
        pass
