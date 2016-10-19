#!/usr/bin/env python3
# coding: UTF-8

import html
import json
import os
import re
from datetime import datetime, timedelta
from urllib.request import urlretrieve

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from requests_oauthlib import OAuth1Session

import config
from cqsdk import CQBot, SendGroupMessage, CQImage
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

REQUESTS_KWARGS = {
    'proxies': {
        'http': 'socks5://127.0.0.1:1080',
        'https': 'socks5://127.0.0.1:1080',
    }
}


################
# tweets
################
class Tweet:
    tweets = {}
    url = 'http://t.kcwiki.moe/?json=1&count=10'
    re_html = re.compile(r'<\w+.*?>|</\w+>')
    max_before = timedelta(hours=12)


@scheduler.scheduled_job('cron', minute='*', second='42')
def tweet():
    response = requests.get(Tweet.url, timeout=20)
    posts = response.json().get('posts', [])
    posts.reverse()
    now = datetime.now()

    if len(Tweet.tweets) == 0:
        for post in posts:
            id_ = post['id']
            key = len(post['content'])
            Tweet.tweets[id_] = key
        print("Tweets init:", len(posts))
        return

    for post in posts:
        id_ = post['id']
        key = len(post['content'])

        if Tweet.tweets.get(id_) == key:
            continue
        Tweet.tweets[id_] = key

        date = post['date']
        date_t = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
        if (now - date_t) > Tweet.max_before:
            continue

        content = Tweet.re_html.sub('', post['content'])
        content = html.unescape(content)
        content = content.replace('・', '·')  # HACK: Fix gbk encoding
        content = content.replace('#艦これ', '')
        content = content.strip()

        text = '\n'.join(["「艦これ」開発/運営", date, '', content])
        for g in NOTIFY_GROUPS:
            qqbot.send(SendGroupMessage(group=g, text=text))


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


@scheduler.scheduled_job('cron', minute='*', second='12')
def avatar():
    resp = session.get(
        url=Avatar.twitter_url,
        params=Avatar.twitter_params,
        **REQUESTS_KWARGS)

    if resp.status_code == 200:
        user = resp.json()
        image_url = Avatar.image_prog.sub(
            Avatar.image_repl, user['profile_image_url_https'])
    else:
        error("ERROR", "Response failed:", resp.status_code, resp.text)
        return

    if Avatar.latest_url is None:
        Avatar.latest_url = image_url
        print("Avatar init:", image_url)
        return

    if Avatar.latest_url != image_url:
        filename = os.path.basename(image_url)
        path = os.path.join(Avatar.image_root, Avatar.image_subdir, filename)
        urlretrieve(image_url, path)

        text = '\n'.join([
            "「艦これ」開発/運営",
            '【アイコン変更】',
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
