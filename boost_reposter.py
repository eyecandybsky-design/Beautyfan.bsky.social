import os
import random
import time
from datetime import datetime, timezone, timedelta
from atproto import Client

TARGET_ACCOUNT = "big-dominio.bsky.social"
OWN_ACCOUNT = "beautyfan.bsky.social"

RANDOM_POSTS = 1
NEWEST_POSTS = 10
OWN_POSTS = 3

LOOKBACK_DAYS = 60
SLEEP_SECONDS = 2

TARGET_MAX_PAGES = 10
OWN_MAX_PAGES = 20

USERNAME = os.getenv("BSKY_USERNAME")
PASSWORD = os.getenv("BSKY_PASSWORD")

client = Client()


def get_created_at(item):
    return datetime.fromisoformat(
        item.post.record.created_at.replace("Z", "+00:00")
    )


def has_media(item):
    return getattr(item.post.record, "embed", None) is not None


def is_quote(item):
    embed = getattr(item.post.record, "embed", None)
    return embed and "record" in str(type(embed)).lower()


def is_reply(item):
    return getattr(item.post.record, "reply", None) is not None


def is_repost_from_feed(item):
    return getattr(item, "reason", None) is not None


def get_media_posts(account, wanted=20, days_back=None, max_pages=10):
    posts = []
    cursor = None
    cutoff = None

    if days_back:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    for page in range(max_pages):
        params = {
            "actor": account,
            "limit": 100
        }

        if cursor:
            params["cursor"] = cursor

        feed = client.app.bsky.feed.get_author_feed(params)

        for item in feed.feed:
            # Geen reposts van anderen
            if is_repost_from_feed(item):
                continue

            # Geen replies
            if is_reply(item):
                continue

            # Alleen media
            if not has_media(item):
                continue

            # Geen quote posts
            if is_quote(item):
                continue

            created = get_created_at(item)

            if cutoff and created < cutoff:
                continue

            posts.append(item)

            if len(posts) >= wanted:
                break

        if len(posts) >= wanted:
            break

        cursor = getattr(feed, "cursor", None)

        if not cursor:
            break

    posts.sort(key=get_created_at, reverse=True)
    return posts


def refresh_repost(item):
    viewer = item.post.viewer

    like_uri = getattr(viewer, "like", None)

    if not like_uri:
        try:
            print("Like:", item.post.uri)
            client.like(item.post.uri, item.post.cid)
            time.sleep(1)
        except Exception as e:
            print("Like failed:", e)

    repost_uri = getattr(viewer, "repost", None)

    if repost_uri:
        print("Unrepost:", item.post.uri)
        client.delete_repost(repost_uri)
        time.sleep(SLEEP_SECONDS)

    print("Repost:", item.post.uri)
    client.repost(item.post.uri, item.post.cid)
    time.sleep(SLEEP_SECONDS)


def main():
    if not USERNAME or not PASSWORD:
        raise Exception("Missing BSKY_USERNAME or BSKY_PASSWORD")

    client.login(USERNAME, PASSWORD)

    target_posts = get_media_posts(
        TARGET_ACCOUNT,
        wanted=60,
        days_back=LOOKBACK_DAYS,
        max_pages=TARGET_MAX_PAGES
    )

    newest_posts = target_posts[:NEWEST_POSTS]

    random_pool = target_posts[NEWEST_POSTS:]
    random_posts = random.sample(
        random_pool,
        min(RANDOM_POSTS, len(random_pool))
    )

    own_posts = get_media_posts(
        OWN_ACCOUNT,
        wanted=OWN_POSTS,
        days_back=None,
        max_pages=OWN_MAX_PAGES
    )[:OWN_POSTS]

    print(f"Target found media posts: {len(target_posts)}")
    print(f"Random old target posts: {len(random_posts)}")
    print(f"Newest target posts: {len(newest_posts)}")
    print(f"Own Eyescandy posts: {len(own_posts)}")

    final_posts = (
        random_posts
        + list(reversed(newest_posts))
        + list(reversed(own_posts))
    )

    print(f"Total repost actions: {len(final_posts)}")

    for item in final_posts:
        refresh_repost(item)


if __name__ == "__main__":
    main()