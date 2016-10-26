#!/usr/bin/env python3
# coding: UTF-8

import json
import os
import re
from datetime import datetime, timezone, timedelta

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from requests_oauthlib import OAuth1Session

import utils
from utils import CQ_IMAGE_ROOT, error, FileDownloader
from cqsdk import CQBot, CQImage, SendGroupMessage


qqbot = CQBot(11235, online=False)
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
    html_tag = re.compile(r'<\w+.*?>|</\w+>')
    image_subdir = 'twitter'

utils.mkdir(os.path.join(CQ_IMAGE_ROOT, TL.image_subdir))


class Tweet:
    def __init__(self, id_):
        self.id_ = id_
        self.date = None
        self.ja = ''
        self.zh = ''
        self.media = []

    def __str__(self):
        if self.date is None:
            error("Stringify `Tweet` before assgin `Tweet.date`.")
            raise ValueError(self)
        dt = self.date.astimezone(timezone(timedelta(hours=9)))
        ds = datetime.strftime(dt, "%Y-%m-%d %H:%M:%S JST")
        results = ["「艦これ」開発/運営", ds]
        for t in [self.ja, self.zh]:
            if len(t) == 0:
                continue
            # Fix gbk encoding
            t = t.replace('・', '·')
            t = t.replace('✕', '×')
            t = t.replace('#艦これ', '')
            results.extend(['', t.strip()])
        results.extend([str(m) for m in self.media])
        return '\n'.join(results)


@scheduler.scheduled_job('cron', minute='*', second='10')
def poll_twitter():
    resp = session.get(**TL.twitter, **REQUESTS_PROXIED)
    if resp.status_code != 200:
        print("[twitter]", "Response not success", resp)
    posts = resp.json()
    posts.reverse()

    for post in posts:
        id_ = post['id_str']
        text = post['text']
        tweet = TL.tweets.get(id_, Tweet(id_))
        if len(text) == 0:
            continue
        if len(tweet.ja) > 0:
            continue

        date = datetime.strptime(
            post['created_at'], "%a %b %d %H:%M:%S %z %Y")
        if tweet.date is None or date < tweet.date:
            tweet.date = date
        for ent in post['entities'].get('urls', []):
            text = text.replace(ent['url'], ent['expanded_url'])
        for ent in post['entities'].get('media', []):
            text = text.replace(ent['url'], ent['expanded_url'])
            url = ent['media_url']
            filename = os.path.basename(url)
            FileDownloader(
                url=url,
                path=os.path.join(
                    CQ_IMAGE_ROOT, TL.image_subdir, filename),
                requests_kwargs=REQUESTS_PROXIED,
            ).run()
            tweet.media.append(
                CQImage(os.path.join(TL.image_subdir, filename)))
        tweet.ja = text
        TL.tweets[id_] = tweet

        if TL.twitter_inited:
            text = str(tweet)
            for g in NOTIFY_GROUPS:
                qqbot.send(SendGroupMessage(group=g, text=text))

    if not TL.twitter_inited:
        TL.twitter_inited = True
        print("[twitter]", "init", len(posts))


@scheduler.scheduled_job('cron', minute='*', second='30')
def poll_kcwiki():
    resp = requests.get(**TL.kcwiki)
    if resp.status_code != 200:
        print("[kcwiki]", "Response not success", resp)
        return
    posts = resp.json()
    posts.reverse()

    for post in posts:
        id_ = post['id']
        text = post['zh']
        tweet = TL.tweets.get(id_, Tweet(id_))
        if len(text) == 0:
            continue
        if len(tweet.zh) > 0:
            continue

        date = datetime.strptime(post['date'], "%Y-%m-%d %H:%M:%S") \
                       .replace(tzinfo=timezone(timedelta(hours=8)))
        if tweet.date is None or date < tweet.date:
            tweet.date = date
        text = TL.html_tag.sub('', text)
        tweet.zh = text
        TL.tweets[id_] = tweet

        if TL.kcwiki_inited:
            text = str(tweet)
            for g in NOTIFY_GROUPS:
                qqbot.send(SendGroupMessage(group=g, text=text))

    if not TL.kcwiki_inited:
        TL.kcwiki_inited = True
        print("[kcwiki]", "init", len(posts))


################
# avatar
################
class Avatar:
    twitter_url = "https://api.twitter.com/1.1/users/show.json"
    twitter_params = {"screen_name": "KanColle_STAFF"}
    image_prog = re.compile(r'_normal\.(jpg|png|gif)')
    image_repl = r'.\1'
    image_subdir = 'twitter'
    latest = None

utils.mkdir(os.path.join(CQ_IMAGE_ROOT, Avatar.image_subdir))


@scheduler.scheduled_job('cron', minute='*', second='50')
def poll_avatar():
    resp = session.get(
        url=Avatar.twitter_url,
        params=Avatar.twitter_params,
        **REQUESTS_PROXIED)

    if resp.status_code == 200:
        user = resp.json()
        url = Avatar.image_prog.sub(
            Avatar.image_repl, user['profile_image_url_https'])
    else:
        error("[avatar]", "Response failed:", resp.status_code, resp.text)
        return

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
            requests_kwargs=REQUESTS_PROXIED
        ).run()
        Avatar.latest = url

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
        print("Stopping...")
    except KeyboardInterrupt:
        pass
