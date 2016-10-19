#!/usr/bin/env python3
# coding: UTF-8

import json
import os
import re
from datetime import datetime, timezone, timedelta

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from requests_oauthlib import OAuth1Session

import config
from cqsdk import CQBot, CQImage, SendGroupMessage
from utils import error


qqbot = CQBot(11235)
scheduler = BackgroundScheduler(
    timezone='Asia/Tokyo',
    job_defaults={'misfire_grace_time': 60},
)

with open('twitter.json', 'r') as f:
    data = json.loads(f.read())
    session = OAuth1Session(
        client_key=data['consumer_key'],
        client_secret=data['consumer_secret'],
        resource_owner_key=data['access_token'],
        resource_owner_secret=data['access_secret'],
    )
    NOTIFY_GROUPS = data['notify_groups']

REQUESTS_PROXIED = {
    'proxies': {
        'http': 'socks5://127.0.0.1:1080',
        'https': 'socks5://127.0.0.1:1080',
    }
}


################
# Timeline
# Assume no posting 20+ tweet in a minute.
################
class TL:
    tweets = {}
    twitter_inited = False
    twitter = {
        'url': "https://api.twitter.com/1.1/statuses/user_timeline.json",
        'params': {
            "screen_name": "KanColle_STAFF",
            "trim_user": 1,
            "count": 20,
        },
    }
    kcwiki_inited = False
    kcwiki = {
        'url': "http://api.kcwiki.moe/tweet/20",
    }
    html_pattern = re.compile(r'<\w+.*?>|</\w+>')


class Tweet:
    def __init__(self, id_):
        self.id_ = id_
        self.date = None
        self.ja = None
        self.zh = None

    def __str__(self):
        if self.date is None:
            error("Stringify `Tweet` before assgin `Tweet.date`.")
            return ''
        dt = self.date.astimezone(timezone(timedelta(hours=9)))
        ds = datetime.strftime(dt, "%Y-%m-%d %H:%M:%S")
        li = [ds]
        for t in [self.ja, self.zh]:
            if t is not None:
                li.append(t)
        return '\n\n'.join(li)


@scheduler.scheduled_job('cron', minute='*', second='10')
def poll_twitter():
    resp = session.get(**TL.twitter, **REQUESTS_PROXIED)
    posts = resp.json()
    posts.reverse()

    for post in posts:
        id_ = post['id_str']
        tweet = TL.tweets.get(id_, Tweet(id_))
        if tweet.ja is not None:
            continue

        date = datetime.strptime(
            post['created_at'], "%a %b %d %H:%M:%S %z %Y")
        if tweet.date is None or date < tweet.date:
            tweet.date = date
        text = post['text']
        text = text.replace('・', '·')  # Fix gbk encoding
        text = text.replace('#艦これ', '')
        tweet.ja = text.strip()
        TL.tweets[id_] = tweet

        if TL.twitter_inited:
            text = '\n'.join(["「艦これ」開発/運営", str(tweet)])
            for g in NOTIFY_GROUPS:
                qqbot.send(SendGroupMessage(group=g, text=text))

    if not TL.twitter_inited:
        TL.twitter_inited = True
        print("TL.Twitter init:", len(posts))


@scheduler.scheduled_job('cron', minute='*', second='30')
def poll_kcwiki():
    resp = requests.get(**TL.kcwiki)
    posts = resp.json()
    posts.reverse()

    for post in posts:
        id_ = post['id']
        tweet = TL.tweets.get(id_, Tweet(id_))
        if tweet.zh is not None:
            continue

        date = datetime.strptime(post['date'], "%Y-%m-%d %H:%M:%S") \
                       .replace(tzinfo=timezone(timedelta(hours=8)))
        if tweet.date is None or date < tweet.date:
            tweet.date = date
        text = post['zh']
        text = TL.html_pattern.sub('', text)
        text = text.replace('・', '·')  # Fix gbk encoding
        text = text.replace('#艦これ', '')
        tweet.zh = text.strip()
        TL.tweets[id_] = tweet

        if TL.kcwiki_inited:
            text = '\n'.join(["「艦これ」開発/運営", str(tweet)])
            for g in NOTIFY_GROUPS:
                qqbot.send(SendGroupMessage(group=g, text=text))

    if not TL.kcwiki_inited:
        TL.kcwiki_inited = True
        print("TL.kcwiki init:", len(posts))


################
# avatar
################
class Avatar:
    twitter_url = "https://api.twitter.com/1.1/users/show.json"
    twitter_params = {"screen_name": "KanColle_STAFF"}
    image_prog = re.compile(r'_normal\.(jpg|png|gif)')
    image_repl = r'.\1'
    image_root = config.CQ_IMAGE_ROOT
    image_subdir = 'avatar'
    latest_url = None

    def __init__(self):
        os.makedirs(os.path.join(Avatar.image_root, Avatar.image_subdir))


@scheduler.scheduled_job('cron', minute='*', second='50')
def poll_avatar():
    resp = session.get(
        url=Avatar.twitter_url,
        params=Avatar.twitter_params,
        **REQUESTS_PROXIED)

    if resp.status_code == 200:
        user = resp.json()
        image_url = Avatar.image_prog.sub(
            Avatar.image_repl, user['profile_image_url_https'])
    else:
        error("Response failed:", resp.status_code, resp.text)
        return

    if Avatar.latest_url is None:
        Avatar.latest_url = image_url
        print("Avatar:", image_url)
        return

    if Avatar.latest_url != image_url:
        print("Avatar:", image_url)
        filename = os.path.basename(image_url)
        path = os.path.join(Avatar.image_root, Avatar.image_subdir, filename)
        with open(path, 'wb') as f:
            r = requests.get(image_url, **REQUESTS_PROXIED)
            f.write(r.content)
        Avatar.latest_url = image_url

        text = '\n'.join([
            user['name'],
            "【アイコン変更】",
            str(CQImage(os.path.join(Avatar.image_subdir, filename)))
        ])
        for g in NOTIFY_GROUPS:
            qqbot.send(SendGroupMessage(group=g, text=text))


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
