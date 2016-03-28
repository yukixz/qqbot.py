# coding: UTF-8

import json
import random
import time

from pycoolq import coolqBot, SendMessage

qqbot = coolqBot(py2cqPort=12451, cq2pyPort=12450)


def match(text, keywords):
    for keyword in keywords:
        if keyword in text:
            return True
    return False


################
# log
################
@qqbot.messageHandler()
def log(message):
    print("↘", message.sourceType,
          message.fromGroupID, message.fromID, message.content)


def reply(message, text):
    if message.sourceType in ("group", "discuss"):
        dest_type = message.sourceType
        dest_id = message.fromGroupID
    else:
        return  # Cannot send private message
        dest_type = "personal"
        dest_id = message.fromID
    qqbot.send(SendMessage(dest_type, dest_id, text))
    print("↗", dest_type, dest_id, text)


################
# blacklist
################
BLACKLIST = []

with open('blacklist.json', 'r', encoding="utf-8") as f:
    BLACKLIST = json.loads(f.read())


@qqbot.messageHandler()
def blacklist(message):
    text = message.content.lower()
    return match(text, BLACKLIST)


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


@qqbot.messageHandler()
def faq(message):
    text = message.content.lower()
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
        reply(message, send_text)
        return True


################
# roll
################
ROLL_LOWER = 2
ROLL_UPPER = 7000


@qqbot.messageHandler()
def roll(message):
    texts = message.content.split()
    if not (len(texts) > 0 and texts[0] == '/roll'):
        return

    ranges = []
    for text in texts[1:5]:
        try:
            n = int(text)
        except:
            break
        if ROLL_LOWER <= n <= ROLL_UPPER:
            ranges.append(n)
        else:
            reply(message,
                  "[roll] 有效范围为 {} ~ {}".format(ROLL_LOWER, ROLL_UPPER))
            return True
    if len(ranges) == 0:
        ranges = [100]

    rolls = []
    for n in ranges:
        rolls.append("{}/{}".format(random.randint(1, n), n))
    send_text = "[roll] [CQ:at,qq={}]: {}".format(
        message.fromID, ", ".join(rolls))

    reply(message, send_text)
    return True


################
# repeat
################
REPEAT_QUEUE_SIZE = 20
REPEAT_COUNT_MIN = 2
REPEAT_COUNT_MAX = 4
queue = []


class QueueMessage:
    def __init__(self, text):
        self.text = text
        self.count = 0
        self.repeated = False


@qqbot.messageHandler()
def repeat(message):
    text = message.content

    # Find & remove matched message from queue.
    msg = None
    for qmsg in queue:
        if qmsg.text == text:
            msg = qmsg
            queue.remove(qmsg)
            break

    # Increase message count
    if msg is None:
        msg = QueueMessage(text)
    msg.count += 1

    # Push message back to queue
    queue.append(msg)
    if len(queue) > REPEAT_QUEUE_SIZE:
        queue.pop(0)

    # Repeat message
    if msg.repeated:
        return False
    if REPEAT_COUNT_MIN <= msg.count <= REPEAT_COUNT_MAX and \
            random.randint(1, REPEAT_COUNT_MAX - msg.count + 1) == 1:
        reply(message, msg.text)
        msg.repeated = True
        return True


qqbot.start()
try:
    qqbot.send(SendMessage("group", 378320628, "AlphaBie Online"))
    input()
except KeyboardInterrupt:
    pass
finally:
    qqbot.send(SendMessage("group", 378320628, "AlphaBie Offline"))
