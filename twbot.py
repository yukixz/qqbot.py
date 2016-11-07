#!/usr/bin/env python3
# coding: UTF-8

import json
import os
import re
import traceback
from datetime import datetime, timezone, timedelta

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from requests_oauthlib import OAuth1Session

import utils
from utils import CQ_IMAGE_ROOT, info, error, FileDownloader
from cqsdk import CQBot, CQImage, SendGroupMessage, SendPrivateMessage


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
    NOTIFY = data['notify']

REQUESTS_OPTIONS = {
    'timeout': 10,
}
REQUESTS_OPTIONS_PROXIED = {
    **REQUESTS_OPTIONS,
    'proxies': {
        'http': 'socks5://127.0.0.1:1080',
        'https': 'socks5://127.0.0.1:1080',
    }
}


################
# Timeline
# Assume no posting 20+ tweet in a minute.
################
TEMPLATE_TWITTER = {
    **REQUESTS_OPTIONS_PROXIED,
    'url': "https://api.twitter.com/1.1/statuses/user_timeline.json",
    'params': {
        "screen_name": "KanColle_STAFF",
        "count": 20,
    },
}
TEMPLATE_KCWIKI = {
    'url': "http://api.kcwiki.moe/tweet/20",
}


class Twitter:
    tweets = {}
    inited = {}
    html_tag = re.compile(r'<\w+.*?>|</\w+>')
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
            t = t.replace('#艦これ', '')
            t = t.replace('#千年戦争アイギス', '')
            results.extend(['', t.strip()])
        results.extend([str(m) for m in self.media])
        return '\n'.join(results)


@scheduler.scheduled_job('cron', minute='*', second='10')
def poll_twitter_all():
    for user in ["KanColle_STAFF", "Aigis1000"]:
        try:
            poll_twitter(user)
        except:
            traceback.print_exc()


def poll_twitter(user):
    Template = dict(TEMPLATE_TWITTER)
    Template['params']['screen_name'] = user

    resp = session.get(**Template)
    if resp.status_code != 200:
        print(user, "Response not success", resp)
    posts = resp.json()
    posts.reverse()

    for post in posts:
        id_ = post['id_str']
        text = post['text']
        tweet = Twitter.tweets.get(id_, Tweet(id_))
        if len(text) == 0:
            continue
        if len(tweet.ja) > 0:
            continue

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
        Twitter.tweets[id_] = tweet

        if Twitter.inited.get(user):
            text = str(tweet)
            info(text)
            for notify in NOTIFY:
                if user not in notify.get('type'):
                    continue
                for q in notify.get('qq', []):
                    qqbot.send(SendPrivateMessage(qq=q, text=text))
                for g in notify.get('group', []):
                    qqbot.send(SendGroupMessage(group=g, text=text))

    if not Twitter.inited.get(user):
        Twitter.inited[user] = True
        print(user, "init", len(posts))


@scheduler.scheduled_job('cron', minute='*', second='30')
def poll_kcwiki():
    user = 'kcwiki'
    resp = requests.get(**TEMPLATE_KCWIKI)
    if resp.status_code != 200:
        print(user, "Response not success", resp)
        return
    posts = resp.json()
    posts.reverse()

    for post in posts:
        id_ = post['id']
        text = post['zh']
        tweet = Twitter.tweets.get(id_, Tweet(id_))
        if len(text) == 0:
            continue
        if len(tweet.zh) > 0:
            continue

        text = Twitter.html_tag.sub('', text)
        tweet.zh = text
        Twitter.tweets[id_] = tweet

        # Dont post old translation.
        date = datetime.strptime(post['date'], "%Y-%m-%d %H:%M:%S") \
                       .replace(tzinfo=timezone(timedelta(hours=8)))
        now = datetime.utcnow() \
                      .replace(tzinfo=timezone(timedelta(hours=0)))
        if now - date > timedelta(hours=2):
            continue

        if Twitter.inited.get(user):
            text = str(tweet)
            info(text)
            for notify in NOTIFY:
                if 'KanColle_STAFF' not in notify.get('type'):
                    continue
                for q in notify.get('qq', []):
                    qqbot.send(SendPrivateMessage(qq=q, text=text))
                for g in notify.get('group', []):
                    qqbot.send(SendGroupMessage(group=g, text=text))

    if not Twitter.inited.get(user):
        Twitter.inited[user] = True
        print(user, "init", len(posts))


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
        **REQUESTS_OPTIONS_PROXIED)

    if resp.status_code == 200:
        user = resp.json()
        url = Avatar.image_prog.sub(
            Avatar.image_repl, user['profile_image_url_https'])
    else:
        error("[Avatar]", "Response failed:", resp.status_code, resp.text)
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
            requests_kwargs=REQUESTS_OPTIONS_PROXIED
        ).run()
        Avatar.latest = url

        text = '\n'.join([
            user['name'],
            "【アイコン変更】",
            str(CQImage(os.path.join(Avatar.image_subdir, filename)))
        ])
        for notify in NOTIFY:
            if '*Avatar' not in notify.get('type'):
                continue
            for g in notify['group']:
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
