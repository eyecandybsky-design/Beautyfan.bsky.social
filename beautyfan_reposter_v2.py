import os
import json
import time
import random
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from atproto import Client, models

# ============================================================
# BEAUTYFAN TOTAL REPOSTER V2
# Account: beautyfan.bsky.social
#
# RUN_1 (:16):
#   RedFox + Repost Always + Hashtags
#   + Multibooster + Promo Random + Own
#
# RUN_2 (:46):
#   RedFox + Repost Always + Hashtags
#   + Promo Last + Own
#
# Likes:
#   ONLY after a successful NORMAL new repost.
#   Never unlike.
#   Reboosts/boosters and Own Posts are not liked.
#
# Triggered externally by cron-job.org via workflow_dispatch.
# ============================================================

USERNAME = "beautyfan.bsky.social"
PASSWORD = os.getenv("BEAUTYFAN_BSKY_PASSWORD")
RUN_MODE = os.getenv("RUN_MODE", "RUN_1").upper()
STATE_FILE = os.getenv("STATE_FILE", "beautyfan_v2_state.json")

MAX_ACTIONS = 100
MAX_PER_USER = 5
NORMAL_LOOKBACK_HOURS = 3
REPOST_ALWAYS_REBOOST_HOURS = 8
PROMO_MAX_AGE_HOURS = 12
PROMO_RANDOM_POOL = 25
PROMO_RANDOM_REUSE_HOURS = 24
SLEEP_SECONDS = 2

REDFOX_FEED = os.getenv("REDFOX_FEED", "https://bsky.app/profile/did:plc:cxrt7ggxkamgzxa47cggtees/feed/aaaoirmgh53zw")
REPOST_ALWAYS_LIST = os.getenv("REPOST_ALWAYS_LIST", "https://bsky.app/profile/did:plc:cvfulblhg2fttolrunih4ldv/lists/3mwtfemqkiy27")
MULTIBOOSTER_LIST = os.getenv("MULTIBOOSTER_LIST", "https://bsky.app/profile/did:plc:cvfulblhg2fttolrunih4ldv/lists/3mwtff5vfya23")
PROMO_LAST_LIST = os.getenv("PROMO_LAST_LIST", "https://bsky.app/profile/did:plc:cvfulblhg2fttolrunih4ldv/lists/3mwtffqd34u2l")
PROMO_RANDOM_LIST = os.getenv("PROMO_RANDOM_LIST", "https://bsky.app/profile/did:plc:cvfulblhg2fttolrunih4ldv/lists/3mwtfgf5egc22")
HASHTAG_BLACKLIST_LIST = os.getenv("HASHTAG_BLACKLIST_LIST", "https://bsky.app/profile/did:plc:5tbowzedh5d6wvhc5dncydbx/lists/3mwm5xxglhp2r")

# Empty slots are disabled.
HASHTAGS = []


def now_utc():
    return datetime.now(timezone.utc)


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def load_state():
    default = {
        "normal_reposts": {},
        "repost_always_reboosted": {},
        "multibooster_seen": {},
        "promo_random_used": {},
        "own_last_new_uri": None,
        "likes": {},
    }
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in default.items():
                data.setdefault(k, v)
            return data
    except Exception:
        return default


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, sort_keys=True)


def uri_parts(uri):
    p = uri.split("/")
    return p[2], p[-1]


def get_attr(obj, path, default=None):
    cur = obj
    for name in path.split("."):
        if cur is None:
            return default
        cur = getattr(cur, name, None)
    return default if cur is None else cur


def post_datetime(post):
    return parse_dt(get_attr(post, "record.created_at")) or parse_dt(
        get_attr(post, "indexed_at")
    )


def is_reply(post):
    return get_attr(post, "record.reply") is not None


def embed_type(post):
    for embed in (get_attr(post, "record.embed"), get_attr(post, "embed")):
        if embed is None:
            continue
        blob = " ".join(
            (
                embed.__class__.__name__.lower(),
                str(getattr(embed, "py_type", "") or "").lower(),
                str(getattr(embed, "$type", "") or "").lower(),
            )
        )
        if "record_with_media" in blob or "recordwithmedia" in blob:
            return "quote_media"
        if "images" in blob:
            return "images"
        if "video" in blob:
            return "video"
        if "external" in blob:
            return "external"
        if "record" in blob:
            return "quote"
    return "none"


def is_quote(post):
    return embed_type(post) in {"quote", "quote_media"}


def has_media(post):
    return embed_type(post) in {"images", "video"}


def is_repost_feed_item(item):
    reason = getattr(item, "reason", None)
    return reason is not None and "repost" in reason.__class__.__name__.lower()


def suitable(post, allow_reply=False):
    return has_media(post) and not is_quote(post) and (allow_reply or not is_reply(post))


def age_ok(post, hours):
    dt = post_datetime(post)
    return bool(dt and dt >= now_utc() - timedelta(hours=hours))


def list_uri(url):
    parts = url.rstrip("/").split("/")
    owner = parts[-3]
    rkey = parts[-1]
    if owner.startswith("did:"):
        did = owner
    else:
        did = client.resolve_handle(owner).did
    return f"at://{did}/app.bsky.graph.list/{rkey}"


def feed_uri(url):
    parts = url.rstrip("/").split("/")
    owner = parts[-3]
    rkey = parts[-1]
    if owner.startswith("did:"):
        did = owner
    else:
        did = client.resolve_handle(owner).did
    return f"at://{did}/app.bsky.feed.generator/{rkey}"


def members_from_list(url, label="List"):
    out, cursor = [], None
    uri = list_uri(url)
    print(f"[{label}] list ophalen: {uri}")
    while True:
        try:
            res = client.app.bsky.graph.get_list(
                {"list": uri, "limit": 100, "cursor": cursor}
            )
            out.extend([x.subject.did for x in res.items])
            cursor = res.cursor
            if not cursor:
                break
        except Exception as e:
            print(f"LIST ERROR {url}: {e}")
            break
    out = list(dict.fromkeys(out))
    print(f"[{label}] {len(out)} account(s) gevonden")
    return out


def author_feed(actor, limit=50, label="AUTHOR"):
    """Fetch only the newest page."""
    try:
        res = client.app.bsky.feed.get_author_feed(
            {"actor": actor, "limit": min(100, limit)}
        )
        posts = []
        for item in res.feed:
            if is_repost_feed_item(item):
                continue
            posts.append(item.post)
        print(
            f"[{label}] {actor}: {len(posts)} recente feed-item(s) bekeken "
            f"(1 API page)"
        )
        return posts
    except Exception as e:
        print(f"AUTHOR ERROR {actor}: {type(e).__name__}: {e}")
        return []


def diagnostic_rejections(posts, label, max_show=5):
    counts = defaultdict(int)
    examples = []
    for p in posts:
        kind = embed_type(p)
        if not has_media(p):
            reason = f"geen foto/video ({kind})"
        elif is_quote(p):
            reason = "quote"
        elif is_reply(p):
            reason = "reply"
        else:
            reason = "geschikt"
        counts[reason] += 1
        if reason != "geschikt" and len(examples) < max_show:
            examples.append(f"{getattr(p, 'uri', '?')} -> {reason}")
    print(f"[{label}] filter: {dict(counts)}")
    for x in examples:
        print(f"[{label}] FILTER VOORBEELD: {x}")


def like_after_action(post, label):
    """Like only after a successful repost/reboost. Never unlike."""
    uri = post.uri
    if uri in state["likes"]:
        return
    try:
        client.like(uri, post.cid)
        state["likes"][uri] = now_utc().isoformat()
        print(f"LIKE [{label}] {uri}")
        time.sleep(0.5)
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg or "duplicate" in msg:
            state["likes"][uri] = now_utc().isoformat()
        else:
            print(f"LIKE ERROR [{label}] {uri}: {e}")


def repost(post, label, force=False, do_like=True):
    global actions
    if actions >= MAX_ACTIONS:
        return False

    uri, cid = post.uri, post.cid

    if not force and uri in state["normal_reposts"]:
        return False

    try:
        client.repost(uri, cid)
        actions += 1

        if not force:
            state["normal_reposts"][uri] = now_utc().isoformat()

        print(f"REPOST [{label}] {uri}")

        if do_like:
            like_after_action(post, label)

        time.sleep(SLEEP_SECONDS)
        return True

    except Exception as e:
        msg = str(e).lower()
        if not force and ("already" in msg or "duplicate" in msg):
            state["normal_reposts"][uri] = now_utc().isoformat()
        print(f"REPOST ERROR [{label}] {uri}: {e}")
        return False


def reboost(post, label, do_like=True):
    global actions
    if actions >= MAX_ACTIONS:
        return False

    uri, cid = post.uri, post.cid

    try:
        try:
            res = client.app.bsky.feed.get_posts({"uris": [uri]})
            if res.posts:
                viewer = res.posts[0].viewer
                repost_uri = getattr(viewer, "repost", None) if viewer else None
                if repost_uri:
                    client.delete_repost(uri)
                    time.sleep(SLEEP_SECONDS)
        except Exception as e:
            print(f"UNREPOST NOTE [{label}] {uri}: {e}")

        client.repost(uri, cid)
        actions += 1
        print(f"REBOOST [{label}] {uri}")

        if do_like:
            like_after_action(post, label)

        time.sleep(SLEEP_SECONDS)
        return True

    except Exception as e:
        print(f"REBOOST ERROR [{label}] {uri}: {e}")
        return False


def collect_redfox():
    candidates = []
    print("[REDFOX] feed ophalen...")

    try:
        res = None
        for attempt in range(1, 4):
            try:
                res = client.app.bsky.feed.get_feed(
                    {"feed": feed_uri(REDFOX_FEED), "limit": 100}
                )
                break
            except Exception as e:
                print(
                    f"[REDFOX] poging {attempt}/3 mislukt: "
                    f"{type(e).__name__}: {e}"
                )
                if attempt < 3:
                    time.sleep(5)
                else:
                    raise

        print(f"[REDFOX] {len(res.feed)} feed item(s) opgehaald")

        per_author = defaultdict(int)
        media_count = 0
        recent_count = 0

        for item in res.feed:
            if is_repost_feed_item(item):
                continue

            p = item.post

            if suitable(p, allow_reply=True):
                media_count += 1
                if age_ok(p, NORMAL_LOOKBACK_HOURS):
                    recent_count += 1

            if (
                suitable(p, allow_reply=True)
                and age_ok(p, NORMAL_LOOKBACK_HOURS)
                and per_author[p.author.did] < MAX_PER_USER
            ):
                candidates.append((p, "RedFoxOfficial"))
                per_author[p.author.did] += 1

        print(
            f"[REDFOX] geschikte media totaal={media_count}, "
            f"binnen {NORMAL_LOOKBACK_HOURS}u={recent_count}, "
            f"repost kandidaten={len(candidates)}"
        )

    except Exception as e:
        print(f"FEED ERROR RedFoxOfficial: {type(e).__name__}: {e}")

    return candidates


def collect_repost_always():
    candidates, cache = [], {}
    print("[REPOST ALWAYS] starten...")

    for actor in members_from_list(REPOST_ALWAYS_LIST, "REPOST ALWAYS"):
        count = 0
        actor_posts = author_feed(actor, 50, "REPOST ALWAYS")
        cache[actor] = actor_posts
        diagnostic_rejections(actor_posts, f"REPOST ALWAYS {actor}", 2)

        for p in actor_posts:
            if suitable(p) and age_ok(p, NORMAL_LOOKBACK_HOURS):
                if count < MAX_PER_USER:
                    candidates.append((p, "Repost Always"))
                    count += 1

    print(f"[REPOST ALWAYS] repost kandidaten={len(candidates)}")
    return candidates, cache


def process_repost_always_reboost(cache):
    threshold = now_utc() - timedelta(hours=REPOST_ALWAYS_REBOOST_HOURS)
    print(f"[REPOST ALWAYS +8H] cache gebruiken voor {len(cache)} account(s)")

    for actor, posts in cache.items():
        for p in posts:
            if not suitable(p):
                continue

            first = parse_dt(state["normal_reposts"].get(p.uri))

            if (
                not first
                or first > threshold
                or p.uri in state["repost_always_reboosted"]
            ):
                continue

            if reboost(p, "Repost Always +8h", do_like=False):
                state["repost_always_reboosted"][p.uri] = now_utc().isoformat()


def search_hashtag(tag, limit=100):
    """Search recent Bluesky posts for one hashtag."""
    query = tag if tag.startswith("#") else f"#{tag}"
    try:
        res = client.app.bsky.feed.search_posts(
            {"q": query, "limit": min(100, limit), "sort": "latest"}
        )
        return list(res.posts)
    except Exception as e:
        print(f"HASHTAG SEARCH ERROR {query}: {type(e).__name__}: {e}")
        return []


def collect_hashtags():
    active = [x.strip() for x in HASHTAGS if x and x.strip()]

    if not active:
        print("[HASHTAGS] geen actieve hashtags")
        return []

    print(f"[HASHTAGS] actief: {', '.join(active)}")

    blacklist = set(members_from_list(HASHTAG_BLACKLIST_LIST, "HASHTAG BLACKLIST"))
    candidates = []
    seen = set()
    per_author = defaultdict(int)

    for tag in active:
        posts = search_hashtag(tag, 100)
        print(f"[HASHTAG {tag}] {len(posts)} zoekresultaten opgehaald")

        accepted = 0
        rejected_blacklist = 0
        rejected_filter = 0
        rejected_age = 0

        for p in posts:
            if p.uri in seen:
                continue
            seen.add(p.uri)

            if p.author.did in blacklist:
                rejected_blacklist += 1
                continue

            if not suitable(p):
                rejected_filter += 1
                continue

            if not age_ok(p, NORMAL_LOOKBACK_HOURS):
                rejected_age += 1
                continue

            if per_author[p.author.did] >= MAX_PER_USER:
                continue

            candidates.append((p, f"Hashtag {tag}"))
            per_author[p.author.did] += 1
            accepted += 1

        print(
            f"[HASHTAG {tag}] kandidaten={accepted}, "
            f"blacklist={rejected_blacklist}, "
            f"filter={rejected_filter}, oud={rejected_age}"
        )

    print(f"[HASHTAGS] totaal kandidaten={len(candidates)}")
    return candidates


def process_multibooster():
    print("[MULTIBOOSTER] starten...")

    for actor in members_from_list(MULTIBOOSTER_LIST, "MULTIBOOSTER"):
        eligible = [
            p
            for p in author_feed(actor, 20, "MULTIBOOSTER")
            if suitable(p) and age_ok(p, PROMO_MAX_AGE_HOURS)
        ][:3]

        print(
            f"[MULTIBOOSTER] {actor}: {len(eligible)} geschikte post(s) "
            f"in laatste 3 / max {PROMO_MAX_AGE_HOURS}u"
        )

        if not eligible:
            continue

        seen = state["multibooster_seen"].setdefault(actor, {})
        unvisited = [p for p in eligible if p.uri not in seen]

        if not unvisited:
            for p in eligible:
                seen.pop(p.uri, None)
            unvisited = eligible[:]

        chosen = sorted(
            unvisited, key=lambda p: post_datetime(p) or now_utc()
        )[0]

        if reboost(chosen, "Multibooster", do_like=False):
            seen[chosen.uri] = now_utc().isoformat()


def process_promo_last():
    print("[PROMO LAST] starten...")

    for actor in members_from_list(PROMO_LAST_LIST, "PROMO LAST"):
        eligible = [
            p
            for p in author_feed(actor, 20, "PROMO LAST")
            if suitable(p) and age_ok(p, PROMO_MAX_AGE_HOURS)
        ]

        if eligible:
            reboost(eligible[0], "Promo Last", do_like=False)


def process_promo_random():
    print("[PROMO RANDOM] starten...")

    for actor in members_from_list(PROMO_RANDOM_LIST, "PROMO RANDOM"):
        eligible = [
            p
            for p in author_feed(actor, 60, "PROMO RANDOM")
            if suitable(p)
        ][:PROMO_RANDOM_POOL]

        print(
            f"[PROMO RANDOM] {actor}: {len(eligible)} geschikte post(s) in pool"
        )

        if not eligible:
            continue

        used = state["promo_random_used"].setdefault(actor, {})
        cutoff = now_utc() - timedelta(hours=PROMO_RANDOM_REUSE_HOURS)

        fresh = [p for p in eligible if p.uri not in used]

        if fresh:
            chosen = random.choice(fresh)
        else:
            reusable = [
                p
                for p in eligible
                if (parse_dt(used.get(p.uri)) or now_utc()) <= cutoff
            ]

            if not reusable:
                print(
                    f"PROMO RANDOM SKIP {actor}: "
                    f"geen post beschikbaar na {PROMO_RANDOM_REUSE_HOURS}u-regel"
                )
                continue

            chosen = random.choice(reusable)

        if reboost(chosen, "Promo Random", do_like=False):
            used[chosen.uri] = now_utc().isoformat()


def process_own_posts():
    """Reboost the newest 3 own original media posts, using the proven author-feed method."""
    print("[OWN POSTS] ophalen via eigen author feed...")

    own_did = client.me.did

    try:
        result = client.get_author_feed(actor=own_did, limit=100)
    except Exception as e:
        print(f"OWN POSTS ERROR: {type(e).__name__}: {e}")
        return

    own_posts = []

    for item in result.feed:
        post = item.post
        record = post.record

        # Ignore repost feed items completely.
        if getattr(item, "reason", None) is not None:
            continue

        # Must really be HotBleusky's own post.
        if post.author.did != own_did:
            continue

        if not isinstance(record, models.AppBskyFeedPost.Record):
            continue

        # Original standalone posts only.
        if getattr(record, "reply", None) is not None:
            continue

        embed = getattr(record, "embed", None)

        # No quotes / record-with-media.
        if isinstance(
            embed,
            (
                models.AppBskyEmbedRecord.Main,
                models.AppBskyEmbedRecordWithMedia.Main,
            ),
        ):
            continue

        # Own media tab behaviour: direct image/video posts only.
        if not isinstance(
            embed,
            (
                models.AppBskyEmbedImages.Main,
                models.AppBskyEmbedVideo.Main,
            ),
        ):
            continue

        own_posts.append(post)

        if len(own_posts) >= 3:
            break

    print(f"[OWN POSTS] {len(own_posts)} eigen originele mediapost(s) gevonden")

    if not own_posts:
        print("OWN POSTS SKIP: geen eigen originele mediapost gevonden")
        return

    # Oldest first, newest last.
    own_posts.reverse()
    print("[OWN POSTS] reboost laatste 3 oud -> nieuw; state wordt genegeerd")

    for post in own_posts:
        reboost(post, "Own Posts", do_like=False)


if not PASSWORD:
    raise SystemExit("BEAUTYFAN_BSKY_PASSWORD ontbreekt")

if RUN_MODE not in {"RUN_1", "RUN_2"}:
    raise SystemExit("RUN_MODE moet RUN_1 of RUN_2 zijn")


client = Client()
client.login(USERNAME, PASSWORD)

state = load_state()
actions = 0
normal_candidates = []

print("=" * 60)
print("BEAUTYFAN TOTAL REPOSTER")
print(f"MODE: {RUN_MODE}")
print(f"TIME: {now_utc().isoformat()}")
print("=" * 60)

# ------------------------------------------------------------
# NORMAL SOURCES
# Gather first, deduplicate, mix chronologically old -> new.
# ------------------------------------------------------------

redfox = collect_redfox()
normal_candidates.extend(redfox)

ra, ra_cache = collect_repost_always()
normal_candidates.extend(ra)

hashtags = collect_hashtags()
normal_candidates.extend(hashtags)

# Deduplicate and enforce max 3/account across ALL normal sources.
unique = {}
for p, label in normal_candidates:
    unique.setdefault(p.uri, (p, label))

ordered = sorted(
    unique.values(),
    key=lambda x: post_datetime(x[0]) or now_utc()
)

per_author = defaultdict(int)

for p, label in ordered:
    if actions >= MAX_ACTIONS:
        break

    if per_author[p.author.did] >= MAX_PER_USER:
        continue

    if repost(p, label, do_like=True):
        per_author[p.author.did] += 1


# ------------------------------------------------------------
# ONE-TIME +8H REPOST ALWAYS REFRESH
# ------------------------------------------------------------

process_repost_always_reboost(ra_cache)


# ------------------------------------------------------------
# RUN-SPECIFIC BOOSTERS
# ------------------------------------------------------------

if RUN_MODE == "RUN_1":
    process_multibooster()
    process_promo_random()
else:
    process_promo_last()


# ------------------------------------------------------------
# OWN POSTS ALWAYS LAST
# ------------------------------------------------------------

process_own_posts()


save_state(state)
print(f"DONE: {actions} repost/reboost actions; state opgeslagen.")
