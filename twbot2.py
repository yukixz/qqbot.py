#!/usr/bin/env python3
# coding: UTF-8

import json
import os
import re
import traceback
from datetime import datetime, timezone, timedelta
from xmlrpc.server import SimpleXMLRPCServer

import utils
from utils import CQ_IMAGE_ROOT, info, error, FileDownloader
from cqsdk import CQBot, CQImage, SendGroupMessage, SendPrivateMessage


qqbot = CQBot(11235, online=False)

with open('twitter.json', 'r') as f:
    data = json.loads(f.read())
    NOTIFY = data['notify']

REQUESTS_OPTIONS_PROXIED = {
    'timeout': 60,
    'proxies': {
        'http': 'socks5://127.0.0.1:1080',
        'https': 'socks5://127.0.0.1:1080',
    }
}


################
# Timeline
################
class Twitter:
    image_subdir = 'twitter'

utils.mkdir(os.path.join(CQ_IMAGE_ROOT, Twitter.image_subdir))


class Tweet:
    def __init__(self, id_):
        self.id_ = id_
        self.user = None
        self.date = None
        self.ja = ''
        self.zh = ''
        self.media = []

    def __str__(self):
        if self.user is None or self.date is None:
            error("Stringify `Tweet` without `user` or `date`.")
            raise ValueError()
        dt = self.date.astimezone(timezone(timedelta(hours=9)))
        ds = datetime.strftime(dt, "%Y-%m-%d %H:%M:%S JST")
        results = [self.user, ds]
        for t in [self.ja, self.zh]:
            if len(t) == 0:
                continue
            # Fix GBK encoding
            t = t.replace('・', '·')
            t = t.replace('✕', '×')
            t = t.replace('♪', '')
            t = t.replace('#艦これ', '')
            t = t.replace('#千年戦争アイギス', '')
            results.extend(['', t.strip()])
        results.extend([str(m) for m in self.media])
        return '\n'.join(results)


def process_twitter(post):
    id_ = post['id_str']
    user = post['user']['screen_name']
    text = post['text']
    tweet = Tweet(id_)
    if len(text) == 0:
        return

    tweet.user = post['user']['name']
    tweet.date = datetime.strptime(
        post['created_at'], "%a %b %d %H:%M:%S %z %Y")
    for ent in post['entities'].get('urls', []):
        text = text.replace(ent['url'], ent['expanded_url'])
    for ent in post['entities'].get('media', []):
        text = text.replace(ent['url'], ent['expanded_url'])
        url = ent['media_url']
        filename = os.path.basename(url)
        FileDownloader(
            url=url,
            path=os.path.join(
                CQ_IMAGE_ROOT, Twitter.image_subdir, filename),
            requests_kwargs=REQUESTS_OPTIONS_PROXIED,
        ).run()
        tweet.media.append(
            CQImage(os.path.join(Twitter.image_subdir, filename)))
    tweet.ja = text

    text = str(tweet)
    # info(text)
    for notify in NOTIFY:
        if user not in notify.get('type'):
            continue
        for q in notify.get('qq', []):
            qqbot.send(SendPrivateMessage(qq=q, text=text))
        for g in notify.get('group', []):
            qqbot.send(SendGroupMessage(group=g, text=text))


################
# avatar
################
class Avatar:
    image_prog = re.compile(r'_normal\.(jpg|png|gif)')
    image_repl = r'.\1'
    image_subdir = 'twitter'
    # Monitor KanColle_STAFF only
    latest = None

utils.mkdir(os.path.join(CQ_IMAGE_ROOT, Avatar.image_subdir))


def process_avatar(post):
    user = post['user']
    if user['screen_name'] != 'KanColle_STAFF':
        return

    url = Avatar.image_prog.sub(
        Avatar.image_repl, user['profile_image_url_https'])
    if Avatar.latest is None:
        Avatar.latest = url
        print("[Avatar]", url)
        return

    if Avatar.latest != url:
        print("[Avatar]", url)
        filename = os.path.basename(url)
        FileDownloader(
            url=url,
            path=os.path.join(
                CQ_IMAGE_ROOT, Avatar.image_subdir, filename),
            requests_kwargs=REQUESTS_OPTIONS_PROXIED
        ).run()
        Avatar.latest = url

        text = '\n'.join([
            user['name'],
            "【アイコン変更】",
            str(CQImage(os.path.join(Avatar.image_subdir, filename)))
        ])
        for notify in NOTIFY:
            if '_avatar_' not in notify.get('type'):
                continue
            for q in notify.get('qq', []):
                qqbot.send(SendPrivateMessage(qq=q, text=text))
            for g in notify.get('group', []):
                qqbot.send(SendGroupMessage(group=g, text=text))


################
# xmlrpc
################
def do_tweet(data):
    message = json.loads(data)
    for handle in [process_twitter, process_avatar]:
        try:
            handle(message)
        except:
            traceback.print_exc()


################
# __main__
################
if __name__ == '__main__':
    try:
        print("Running...")
        server = SimpleXMLRPCServer(
            ("localhost", 12450),
            logRequests=False, allow_none=True)
        server.register_function(do_tweet)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
