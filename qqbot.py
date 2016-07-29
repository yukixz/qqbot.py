#!/usr/bin/env python3
# coding: UTF-8

import html
import json
import random
import re
import time
import traceback
from collections import deque
from datetime import datetime, timedelta

import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from cqbot import CQBot, \
    RcvdPrivateMessage, RcvdGroupMessage, RcvdDiscussMessage, \
    SendPrivateMessage, SendGroupMessage, SendDiscussMessage, \
    GroupMemberDecrease, GroupMemberIncrease, \
    RE_CQ_SPECIAL, CQAt
from utils import match, reply


POI_GROUP = '378320628'

qqbot = CQBot(11235)
scheduler = BackgroundScheduler(
    timezone='Asia/Tokyo',
    job_defaults={'misfire_grace_time': 60},
    )


################
# debug
################
@qqbot.listener((RcvdPrivateMessage, ))
def debug(message):
    if message.qq == '412632991':
        print('DEBUG', message)


################
# blacklist
################
BLACKLIST_KEYWORDS = []
BLACKLIST_USERS = []

with open('blacklist.json', 'r', encoding="utf-8") as f:
    data = json.loads(f.read())
    BLACKLIST_KEYWORDS = data.get("keywords", [])
    BLACKLIST_USERS = data.get("users", [])


@qqbot.listener((RcvdPrivateMessage, RcvdGroupMessage, RcvdDiscussMessage,
                 GroupMemberIncrease, GroupMemberDecrease))
def blacklist(message):
    # Restrict to Poi group
    if isinstance(message, (GroupMemberIncrease, GroupMemberDecrease)):
        return message.group != POI_GROUP
    if isinstance(message, RcvdGroupMessage) and message.group != POI_GROUP:
        return True
    if match(message.text.lower(), BLACKLIST_KEYWORDS):
        return True
    if message.qq in BLACKLIST_USERS:
        return True
    # else
    return False


################
# FAQ
################
FAQ_DEFAULT_INTERVAL = 60
FAQ = []


class FAQObject:
    def __init__(self, opts):
        self.keywords = opts["keywords"]
        self.whitelist = opts.get("whitelist", [])
        self.message = opts["message"]
        self.interval = opts.get("interval", FAQ_DEFAULT_INTERVAL)
        self.triggered = 0

with open('faq.json', 'r', encoding="utf-8") as f:
    jFAQ = json.loads(f.read())
    for jfaq in jFAQ:
        FAQ.append(FAQObject(jfaq))


@qqbot.listener((RcvdPrivateMessage, RcvdGroupMessage, RcvdDiscussMessage))
def faq(message):
    text = message.text.lower()
    now = time.time()
    for faq in FAQ:
        if not match(text, faq.keywords):
            continue
        if match(text, faq.whitelist):
            return True
        if (now - faq.triggered) < faq.interval:
            return True

        if isinstance(faq.message, list):
            send_text = random.choice(faq.message)
        else:
            send_text = faq.message

        faq.triggered = now
        reply(qqbot, message, send_text)
        return True


################
# roll
################
ROLL_LOWER = 2
ROLL_UPPER = 7000
ROLL_SEPARATOR = ','
ROLL_HELP = "[roll] 有效范围为 {} ~ {}".format(ROLL_LOWER, ROLL_UPPER)


@qqbot.listener((RcvdPrivateMessage, RcvdGroupMessage, RcvdDiscussMessage))
def roll(message):
    texts = message.text.split()
    if not (len(texts) > 0 and texts[0] == '/roll'):
        return
    texts = RE_CQ_SPECIAL.sub('', message.text).split()

    ranges = []
    for text in texts[1:6]:
        # /roll 100
        try:
            n = int(text)
            if ROLL_LOWER <= n <= ROLL_UPPER:
                ranges.append(n)
            else:
                reply(qqbot, message, ROLL_HELP)
                return True
            continue
        except:
            pass
        # /roll 1,20,100
        if ROLL_SEPARATOR in text:
            n = text.split(',')
            ranges.append(n)
            continue
        # else
        break
    if len(ranges) == 0:
        ranges = [100]

    rolls = []
    for n in ranges:
        if isinstance(n, int):
            rolls.append("{}/{}".format(random.randint(1, n), n))
        if isinstance(n, (list, tuple)):
            rolls.append("{}/{}".format(random.choice(n),
                                        ROLL_SEPARATOR.join(n)))
    roll_text = ", ".join(rolls)
    send_text = "[roll] [CQ:at,qq={}]: {}".format(message.qq, roll_text)

    reply(qqbot, message, send_text)
    return True


################
# repeat
################
REPEAT_QUEUE_SIZE = 20
REPEAT_COUNT_MIN = 2
REPEAT_COUNT_MAX = 4
queue = deque()


class QueueMessage:
    def __init__(self, text):
        self.text = text
        self.count = 0
        self.senders = set()
        self.repeated = False


@qqbot.listener((RcvdPrivateMessage, RcvdGroupMessage, RcvdDiscussMessage))
def repeat(message):
    text = message.text
    sender = message.qq

    # Find & remove matched message from queue.
    msg = None
    for m in queue:
        if m.text == text:
            msg = m
            queue.remove(m)
            break

    # Increase message count
    if msg is None:
        msg = QueueMessage(text)
    msg.senders.add(sender)
    msg.count = len(msg.senders)

    # Push message back to queue
    queue.appendleft(msg)
    if len(queue) > REPEAT_QUEUE_SIZE:
        queue.pop()

    # Repeat message
    if msg.repeated or msg.count < REPEAT_COUNT_MIN:
        return
    if random.randint(1, REPEAT_COUNT_MAX - msg.count + 1) == 1:
        reply(qqbot, message, msg.text)
        msg.repeated = True
        return True


################
# Join & Leave
################
@qqbot.listener((GroupMemberIncrease, ))
def join(message):
    qqbot.send(SendGroupMessage(
        group=message.group,
        text="{} 欢迎来到 poi 用户讨论群。新人请发女装照一张。".format(
            CQAt(message.operatedQQ))
    ))


# @qqbot.listener((GroupMemberDecrease, ))
# def leave(message):
#     qqbot.send(SendGroupMessage(
#         group=message.group,
#         text="{} 畏罪潜逃了".format(
#             CQAt(message.operatedQQ))
#     ))


################
# notify
################
NOTIFY_HOURLY = {}

with open('notify.json', 'r', encoding="utf-8") as f:
    NOTIFY_HOURLY = json.loads(f.read())


@scheduler.scheduled_job('cron', hour='*')
def notify_hourly():
    hour = str(datetime.now(pytz.timezone("Asia/Tokyo")).hour)
    text = NOTIFY_HOURLY.get(hour, None)
    if text:
        qqbot.send(SendGroupMessage(group=POI_GROUP, text=text))


@scheduler.scheduled_job('cron', hour='2,14', minute='0,30,40,50')
def notify_pratice():
    qqbot.send(SendGroupMessage(
        group=POI_GROUP, text="演习快刷新啦、赶紧打演习啦！"))


################
# twitter
################
TWEETS = {}
TWEET_URL = 'http://t.kcwiki.moe/?json=1&count=10'
TWEET_RE_HTML = re.compile(r'<\w+.*?>|</\w+>')
TWEET_MAX_BEFORE = timedelta(hours=12)


@scheduler.scheduled_job('cron', minute='*', second='42')
def twitter_kcwiki():
    response = requests.get(TWEET_URL, timeout=20)
    posts = response.json().get('posts', [])
    posts.reverse()
    now = datetime.now()

    if TWEETS:  # is not empty
        for post in posts:
            try:
                id_ = post['id']
                key = len(post['content'])

                if TWEETS.get(id_) == key:
                    continue
                TWEETS[id_] = key

                date = post['date']
                date_t = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                if (now - date_t) > TWEET_MAX_BEFORE:
                    continue

                content = TWEET_RE_HTML.sub('', post['content'])
                content = html.unescape(content)
                content = content.replace('・', '·')  # HACK: Fix gbk encoding
                content = content.replace('#艦これ', '')
                content = content.strip()

                text = '\n'.join(["「艦これ」開発/運営", date, '', content])
                qqbot.send(SendGroupMessage(group=POI_GROUP, text=text))
                qqbot.send(SendGroupMessage(group='489722633', text=text))
            except:
                traceback.print_exc()

    else:
        for post in posts:
            id_ = post['id']
            key = len(post['content'])
            TWEETS[id_] = key


################
# __main__
################
if __name__ == '__main__':
    try:
        qqbot.start()
        scheduler.start()

        print("Running...")
        input()
    except KeyboardInterrupt:
        pass
