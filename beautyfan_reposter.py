from atproto import Client
import os
import re
import time
import json
import sys
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Set, Tuple

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

print("=== BEAUTYFAN BOT STARTED ===", flush=True)

# ============================================================
# BOT INFO
# ============================================================
# BOT NAAM        : Beautyfan
# PYTHON FILE     : beautyfan_reposter.py
# STATE FILE      : state_beautyfan.json
#
# GITHUB SECRETS:
#   BSKY_USERNAME_BEAUTYFAN
#   BSKY_PASSWORD_BEAUTYFAN
#
# In workflows mappen naar:
#   BSKY_USERNAME
#   BSKY_PASSWORD
# ============================================================

FEEDS: Dict[str, Dict] = {
    f"feed {i}": {
        "link": "",
        "note": "",
        "enabled": 0,
        "allow_posts": 1,
        "allow_replies": 0,
        "allow_reposts": 0,
        "priority": 0,
    }
    for i in range(1, 21)
}

FEEDS["feed 1"].update({
    "link": "",
    "note": "PROMO FEED",
    "enabled": 0,
    "allow_posts": 1,
    "allow_replies": 0,
    "allow_reposts": 0,
    "priority": 10,
})

FEEDS["feed 2"].update({
    "link": "https://bsky.app/profile/did:plc:cxrt7ggxkamgzxa47cggtees/feed/aaaoirmgh53zw",
    "note": "redfox",
    "enabled": 1,
    "allow_posts": 1,
    "allow_replies": 1,
    "allow_reposts": 0,
    "priority": 5,
})

FEEDS["feed 3"].update({
    "link": "",
    "note": "",
    "enabled": 1,
    "allow_posts": 1,
    "allow_replies": 0,
    "allow_reposts": 1,
    "priority": 5,
})

LIJSTEN: Dict[str, Dict] = {
    f"lijst {i}": {
        "link": "",
        "note": "",
        "enabled": 0,
        "allow_posts": 1,
        "allow_replies": 0,
        "allow_reposts": 0,
        "priority": 0,
    }
    for i in range(1, 21)
}

LIJSTEN["lijst 1"].update({
    "link": "https://bsky.app/profile/did:plc:zmyydkc2zzznc4smjufuerlx/lists/3mhs2vtwixg2q",
    "note": "bleuskyphoto 1",
    "enabled": 1,
    "allow_posts": 1,
    "allow_replies": 0,
    "allow_reposts": 0,
    "priority": 3,
})

LIJSTEN["lijst 2"].update({
    "link": "https://bsky.app/profile/did:plc:zmyydkc2zzznc4smjufuerlx/lists/3mhs2xmxmos2l",
    "note": "BLEUSKYPHOTO 2",
    "enabled": 1,
    "allow_posts": 1,
    "allow_replies": 0,
    "allow_reposts": 0,
    "priority": 3,
})

LIJSTEN["lijst 3"].update({
    "link": "",
    "note": "",
    "enabled": 1,
    "allow_posts": 1,
    "allow_replies": 0,
    "allow_reposts": 0,
    "priority": 2,
})

LIJSTEN["lijst 4"].update({
    "link": "",
    "note": "",
    "enabled": 1,
    "allow_posts": 1,
    "allow_replies": 0,
    "allow_reposts": 0,
    "priority": 2,
})

LIJSTEN["lijst 5"].update({
    "link": "https://bsky.app/profile/did:plc:cvfulblhg2fttolrunih4ldv/lists/3mieeazmxw422",
    "note": "PROMO RANDOM",
    "enabled": 1,
    "allow_posts": 1,
    "allow_replies": 0,
    "allow_reposts": 0,
    "priority": 10,
})

LIJSTEN["lijst 6"].update({
    "link": "https://bsky.app/profile/did:plc:cvfulblhg2fttolrunih4ldv/lists/3mfpgt3d5332n",
    "note": "PROMO LATEST",
    "enabled": 1,
    "allow_posts": 1,
    "allow_replies": 0,
    "allow_reposts": 0,
    "priority": 10,
})

LIJSTEN["lijst 7"].update({
    "link": "",
    "note": "24H PROMO LATEST",
    "enabled": 1,
    "allow_posts": 1,
    "allow_replies": 0,
    "allow_reposts": 0,
    "priority": 20,
})

LIJSTEN["lijst 8"].update({
    "link": "",
    "note": "24H PROMO RANDOM",
    "enabled": 1,
    "allow_posts": 1,
    "allow_replies": 0,
    "allow_reposts": 0,
    "priority": 20,
})

HASHTAGS = [
    "#bskypromo",
    "",
    "",
]

EXCLUDE_LISTS = {
    "exclude 1": {
        "link": "https://bsky.app/profile/did:plc:cvfulblhg2fttolrunih4ldv/lists/3mfr6dhkalx2h",
        "note": "blacklist",
    },
    "exclude 2": {
        "link": "",
        "note": "",
    },
    "exclude 3": {
        "link": "",
        "note": "",
    },
}

PROMO_FEED_KEY = "feed 1"
PROMO_RANDOM_LIST_KEY = "lijst 5"
PROMO_LATEST_LIST_KEY = "lijst 6"

PROCESS_ORDER = {
    "normal": 1,
    "promo_feed": 0,
    "promo_latest": 2,
    "promo_random": 3,
}

LIST_MEMBER_LIMIT = int(os.getenv("LIST_MEMBER_LIMIT", "1500"))
MAX_PER_RUN = int(os.getenv("MAX_PER_RUN", "100"))
MAX_PER_USER = int(os.getenv("MAX_PER_USER", "3"))
HOURS_BACK = int(os.getenv("HOURS_BACK", "2"))
SLEEP_SECONDS = float(os.getenv("SLEEP_SECONDS", "2"))

STATE_FILE = os.getenv("STATE_FILE", "state_beautyfan.json")
AUTHOR_POSTS_PER_MEMBER = int(os.getenv("AUTHOR_POSTS_PER_MEMBER", "30"))
FEED_MAX_ITEMS = int(os.getenv("FEED_MAX_ITEMS", "500"))
HASHTAG_MAX_ITEMS = int(os.getenv("HASHTAG_MAX_ITEMS", "100"))

PROMO_RANDOM_POOL = int(os.getenv("PROMO_RANDOM_POOL", "25"))
PROMO_FETCH_PER_MEMBER = int(os.getenv("PROMO_FETCH_PER_MEMBER", "100"))
POST_COOLDOWN_HOURS = int(os.getenv("POST_COOLDOWN_HOURS", "3"))

ENV_USERNAME = "BSKY_USERNAME"
ENV_PASSWORD = "BSKY_PASSWORD"

print("Config loaded", flush=True)

FEED_URL_RE = re.compile(r"^https?://(www\.)?bsky\.app/profile/([^/]+)/feed/([^/?#]+)", re.I)
LIST_URL_RE = re.compile(r"^https?://(www\.)?bsky\.app/profile/([^/]+)/lists/([^/?#]+)", re.I)


def log(msg: str):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}", flush=True)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def dt_to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def parse_time(post) -> Optional[datetime]:
    indexed = getattr(post, "indexedAt", None) or getattr(post, "indexed_at", None)
    if indexed:
        dt = parse_iso_dt(indexed)
        if dt:
            return dt

    record = getattr(post, "record", None)
    if record:
        created = getattr(record, "createdAt", None) or getattr(record, "created_at", None)
        if created:
            dt = parse_iso_dt(created)
            if dt:
                return dt
    return None


def is_quote_post(record) -> bool:
    embed = getattr(record, "embed", None)
    if not embed:
        return False
    return bool(getattr(embed, "record", None) or getattr(embed, "recordWithMedia", None))


def has_real_media(record) -> bool:
    embed = getattr(record, "embed", None)
    if not embed:
        return False

    if getattr(embed, "images", None):
        return True
    if getattr(embed, "video", None):
        return True

    if getattr(embed, "external", None):
        return False

    rwm = getattr(embed, "recordWithMedia", None)
    if rwm and getattr(rwm, "media", None):
        media = rwm.media
        if getattr(media, "images", None):
            return True
        if getattr(media, "video", None):
            return True

    return False


def resolve_handle_to_did(client: Client, actor: str) -> Optional[str]:
    if actor.startswith("did:"):
        return actor
    try:
        out = client.com.atproto.identity.resolve_handle({"handle": actor})
        return getattr(out, "did", None)
    except Exception:
        return None


def normalize_feed_uri(client: Client, s: str) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    if s.startswith("at://") and "/app.bsky.feed.generator/" in s:
        return s
    m = FEED_URL_RE.match(s)
    if not m:
        return None
    actor = m.group(2)
    rkey = m.group(3)
    did = resolve_handle_to_did(client, actor)
    if not did:
        return None
    return f"at://{did}/app.bsky.feed.generator/{rkey}"


def normalize_list_uri(client: Client, s: str) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    if s.startswith("at://") and "/app.bsky.graph.list/" in s:
        return s
    m = LIST_URL_RE.match(s)
    if not m:
        return None
    actor = m.group(2)
    rkey = m.group(3)
    did = resolve_handle_to_did(client, actor)
    if not did:
        return None
    return f"at://{did}/app.bsky.graph.list/{rkey}"


def parse_at_uri_rkey(uri: str) -> Optional[Tuple[str, str, str]]:
    if not uri or not uri.startswith("at://"):
        return None
    parts = uri[len("at://"):].split("/")
    if len(parts) < 3:
        return None
    return parts[0], parts[1], parts[2]


def load_state(path: str) -> Dict:
    base = {
        "repost_records": {},
        "like_records": {},
        "post_last_reposted_at": {},
    }
    if not os.path.exists(path):
        return base
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return base
        for k, v in base.items():
            data.setdefault(k, v.copy() if isinstance(v, dict) else v)
        return data
    except Exception:
        return base


def save_state(path: str, state: Dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_state(path: str, state: Dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def fetch_feed_items(client: Client, feed_uri: str, max_items: int) -> List:
    items: List = []
    cursor = None
    while True:
        params = {"feed": feed_uri, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        out = client.app.bsky.feed.get_feed(params)
        batch = getattr(out, "feed", []) or []
        items.extend(batch)
        cursor = getattr(out, "cursor", None)
        if not cursor or len(items) >= max_items:
            break
    return items[:max_items]


def fetch_list_members(client: Client, list_uri: str, limit: int) -> List[Tuple[str, str]]:
    members: List[Tuple[str, str]] = []
    cursor = None
    while True:
        params = {"list": list_uri, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        try:
            out = client.app.bsky.graph.get_list(params)
        except Exception as e:
            log(f"⚠️ get_list failed for {list_uri}: {e} (skip this list)")
            return members

        items = getattr(out, "items", []) or []
        for it in items:
            subj = getattr(it, "subject", None)
            if not subj:
                continue
            h = (getattr(subj, "handle", "") or "").lower()
            d = (getattr(subj, "did", "") or "").lower()
            if h or d:
                members.append((h, d))
            if len(members) >= limit:
                return members[:limit]

        cursor = getattr(out, "cursor", None)
        if not cursor:
            break
    return members[:limit]


def fetch_author_feed(client: Client, actor: str, limit: int) -> List:
    try:
        out = client.app.bsky.feed.get_author_feed({"actor": actor, "limit": limit})
        return getattr(out, "feed", []) or []
    except Exception:
        return []


def fetch_hashtag_posts(client: Client, query: str, max_items: int) -> List:
    try:
        out = client.app.bsky.feed.search_posts({"q": query, "sort": "latest", "limit": max_items})
        return getattr(out, "posts", []) or []
    except Exception:
        return []


def item_is_repost(item) -> bool:
    return getattr(item, "reason", None) is not None


def post_matches_source_rules(record, is_repost_item: bool, allow_posts: int, allow_replies: int, allow_reposts: int) -> bool:
    if not has_real_media(record):
        return False
    if is_quote_post(record):
        return False

    is_reply = bool(getattr(record, "reply", None))

    if is_repost_item:
        return allow_reposts == 1

    if is_reply:
        return allow_replies == 1

    return allow_posts == 1


def uri_in_cooldown(uri: str, post_last_reposted_at: Dict[str, str], cooldown_hours: int) -> bool:
    last = parse_iso_dt(post_last_reposted_at.get(uri))
    if not last:
        return False
    return last > utcnow() - timedelta(hours=cooldown_hours)


def build_candidates_from_feed_items(
    items: List,
    cutoff: datetime,
    exclude_handles: Set[str],
    exclude_dids: Set[str],
    allow_posts: int,
    allow_replies: int,
    allow_reposts: int,
    force_refresh: bool = False,
    promo_bucket: Optional[str] = None,
    source_priority: int = 0,
) -> List[Dict]:
    cands: List[Dict] = []

    for item in items:
        post = getattr(item, "post", None)
        if not post:
            continue

        record = getattr(post, "record", None)
        if not record:
            continue

        is_repost_item = item_is_repost(item)

        if not post_matches_source_rules(record, is_repost_item, allow_posts, allow_replies, allow_reposts):
            continue

        uri = getattr(post, "uri", None)
        cid = getattr(post, "cid", None)
        if not uri or not cid:
            continue

        author = getattr(post, "author", None)
        ah = (getattr(author, "handle", "") or "").lower()
        ad = (getattr(author, "did", "") or "").lower()
        if ah in exclude_handles or ad in exclude_dids:
            continue

        created = parse_time(post)
        if not created:
            continue
        if created < cutoff and not force_refresh:
            continue

        cands.append({
            "uri": uri,
            "cid": cid,
            "created": created,
            "author_key": ad or ah or uri,
            "force_refresh": force_refresh,
            "promo_bucket": promo_bucket,
            "source_priority": source_priority,
        })

    cands.sort(key=lambda x: (x["created"], -x["source_priority"]))
    return cands


def build_candidates_from_postviews(
    posts: List,
    cutoff: datetime,
    exclude_handles: Set[str],
    exclude_dids: Set[str],
) -> List[Dict]:
    cands: List[Dict] = []

    for post in posts:
        record = getattr(post, "record", None)
        if not record:
            continue

        if not has_real_media(record):
            continue
        if is_quote_post(record):
            continue
        if getattr(record, "reply", None):
            continue

        uri = getattr(post, "uri", None)
        cid = getattr(post, "cid", None)
        if not uri or not cid:
            continue

        author = getattr(post, "author", None)
        ah = (getattr(author, "handle", "") or "").lower()
        ad = (getattr(author, "did", "") or "").lower()
        if ah in exclude_handles or ad in exclude_dids:
            continue

        created = parse_time(post)
        if not created or created < cutoff:
            continue

        cands.append({
            "uri": uri,
            "cid": cid,
            "created": created,
            "author_key": ad or ah or uri,
            "force_refresh": False,
            "promo_bucket": None,
            "source_priority": 0,
        })

    cands.sort(key=lambda x: (x["created"], -x["source_priority"]))
    return cands


def pick_random_weighted_candidate(
    items: List,
    exclude_handles: Set[str],
    exclude_dids: Set[str],
    pool_size: int,
    source_priority: int,
) -> Optional[Dict]:
    media_cands: List[Dict] = []

    for item in items:
        post = getattr(item, "post", None)
        if not post:
            continue
        if item_is_repost(item):
            continue

        record = getattr(post, "record", None)
        if not record:
            continue
        if getattr(record, "reply", None):
            continue
        if is_quote_post(record):
            continue
        if not has_real_media(record):
            continue

        uri = getattr(post, "uri", None)
        cid = getattr(post, "cid", None)
        if not uri or not cid:
            continue

        author = getattr(post, "author", None)
        ah = (getattr(author, "handle", "") or "").lower()
        ad = (getattr(author, "did", "") or "").lower()
        if ah in exclude_handles or ad in exclude_dids:
            continue

        created = parse_time(post)
        if not created:
            continue

        media_cands.append({
            "uri": uri,
            "cid": cid,
            "created": created,
            "author_key": ad or ah or uri,
            "source_priority": source_priority,
        })

    if not media_cands:
        return None

    media_cands.sort(key=lambda x: x["created"], reverse=True)
    pool = media_cands[:pool_size]
    weights = list(range(len(pool), 0, -1))
    chosen = random.choices(pool, weights=weights, k=1)[0]

    return {
        **chosen,
        "force_refresh": True,
        "promo_bucket": "promo_random",
    }


def pick_latest_candidate(
    items: List,
    exclude_handles: Set[str],
    exclude_dids: Set[str],
    promo_bucket: str,
    source_priority: int,
) -> Optional[Dict]:
    media_cands: List[Dict] = []

    for item in items:
        post = getattr(item, "post", None)
        if not post:
            continue
        if item_is_repost(item):
            continue

        record = getattr(post, "record", None)
        if not record:
            continue
        if getattr(record, "reply", None):
            continue
        if is_quote_post(record):
            continue
        if not has_real_media(record):
            continue

        uri = getattr(post, "uri", None)
        cid = getattr(post, "cid", None)
        if not uri or not cid:
            continue

        author = getattr(post, "author", None)
        ah = (getattr(author, "handle", "") or "").lower()
        ad = (getattr(author, "did", "") or "").lower()
        if ah in exclude_handles or ad in exclude_dids:
            continue

        created = parse_time(post)
        if not created:
            continue

        media_cands.append({
            "uri": uri,
            "cid": cid,
            "created": created,
            "author_key": ad or ah or uri,
            "source_priority": source_priority,
        })

    if not media_cands:
        return None

    media_cands.sort(key=lambda x: x["created"], reverse=True)
    chosen = media_cands[0]

    return {
        **chosen,
        "force_refresh": True,
        "promo_bucket": promo_bucket,
    }


def force_unrepost_unlike_if_needed(
    client: Client,
    me: str,
    subject_uri: str,
    repost_records: Dict[str, str],
    like_records: Dict[str, str],
):
    if subject_uri in repost_records:
        existing_repost_uri = repost_records.get(subject_uri)
        parsed = parse_at_uri_rkey(existing_repost_uri) if existing_repost_uri else None
        if parsed:
            did, collection, rkey = parsed
            if did == me and collection == "app.bsky.feed.repost":
                try:
                    client.app.bsky.feed.repost.delete({"repo": me, "rkey": rkey})
                except Exception as e:
                    log(f"⚠️ unrepost failed: {e}")
        repost_records.pop(subject_uri, None)

    if subject_uri in like_records:
        existing_like_uri = like_records.get(subject_uri)
        parsed = parse_at_uri_rkey(existing_like_uri) if existing_like_uri else None
        if parsed:
            did, collection, rkey = parsed
            if did == me and collection == "app.bsky.feed.like":
                try:
                    client.app.bsky.feed.like.delete({"repo": me, "rkey": rkey})
                except Exception as e:
                    log(f"⚠️ unlike failed: {e}")
        like_records.pop(subject_uri, None)


def repost_and_like(
    client: Client,
    me: str,
    subject_uri: str,
    subject_cid: str,
    repost_records: Dict[str, str],
    like_records: Dict[str, str],
    force_refresh: bool,
) -> bool:
    if force_refresh:
        force_unrepost_unlike_if_needed(client, me, subject_uri, repost_records, like_records)
    else:
        if subject_uri in repost_records:
            return False

    try:
        out = client.app.bsky.feed.repost.create(
            repo=me,
            record={
                "subject": {"uri": subject_uri, "cid": subject_cid},
                "createdAt": dt_to_iso(utcnow()),
            },
        )
        repost_uri = getattr(out, "uri", None)
        if repost_uri:
            repost_records[subject_uri] = repost_uri
    except Exception as e:
        log(f"⚠️ Repost error: {e}")
        return False

    try:
        out_like = client.app.bsky.feed.like.create(
            repo=me,
            record={
                "subject": {"uri": subject_uri, "cid": subject_cid},
                "createdAt": dt_to_iso(utcnow()),
            },
        )
        like_uri = getattr(out_like, "uri", None)
        if like_uri:
            like_records[subject_uri] = like_uri
    except Exception as e:
        log(f"⚠️ Like error: {e}")

    return True


def apply_anti_cluster(cands: List[Dict], lookahead: int = 3) -> List[Dict]:
    if not cands:
        return cands
    result = cands[:]
    for i in range(len(result) - 2):
        a1 = result[i]["author_key"]
        a2 = result[i + 1]["author_key"]
        a3 = result[i + 2]["author_key"]
        if a1 == a2 == a3:
            swap_idx = None
            for j in range(i + 3, min(len(result), i + 3 + lookahead)):
                if result[j]["author_key"] != a1:
                    swap_idx = j
                    break
            if swap_idx is not None:
                result[i + 2], result[swap_idx] = result[swap_idx], result[i + 2]
    return result


def main():
    log("=== BEAUTYFAN BOT START ===")

    username = os.getenv(ENV_USERNAME, "").strip()
    password = os.getenv(ENV_PASSWORD, "").strip()
    if not username or not password:
        log(f"❌ Missing env {ENV_USERNAME} / {ENV_PASSWORD}")
        return

    cutoff = utcnow() - timedelta(hours=HOURS_BACK)

    state = load_state(STATE_FILE)
    repost_records: Dict[str, str] = state.get("repost_records", {})
    like_records: Dict[str, str] = state.get("like_records", {})
    post_last_reposted_at: Dict[str, str] = state.get("post_last_reposted_at", {})

    import hashlib

    print("DEBUG USERNAME:", username)
    print("DEBUG USERNAME LEN:", len(username or ""))
    print("DEBUG PASSWORD LEN:", len(password or ""))
    print("DEBUG PASSWORD HASH:", hashlib.sha256((password or "").encode()).hexdigest()[:12])

    client = Client()
    client.login(username, password)
    me = client.me.did
    log(f"✅ Logged in as {me}")

    feed_uris: List[Tuple[str, Dict, str]] = []
    for key, obj in FEEDS.items():
        if int(obj.get("enabled", 0)) != 1:
            continue
        link = (obj.get("link") or "").strip()
        if not link:
            continue
        uri = normalize_feed_uri(client, link)
        if uri:
            feed_uris.append((key, obj, uri))
        else:
            log(f"⚠️ Feed ongeldig (skip): {key} -> {link}")

    list_uris: List[Tuple[str, Dict, str]] = []
    for key, obj in LIJSTEN.items():
        if int(obj.get("enabled", 0)) != 1:
            continue
        link = (obj.get("link") or "").strip()
        if not link:
            continue
        uri = normalize_list_uri(client, link)
        if uri:
            list_uris.append((key, obj, uri))
        else:
            log(f"⚠️ Lijst ongeldig (skip): {key} -> {link}")

    excl_uris: List[Tuple[str, Dict, str]] = []
    for key, obj in EXCLUDE_LISTS.items():
        link = (obj.get("link") or "").strip()
        if not link:
            continue
        uri = normalize_list_uri(client, link)
        if uri:
            excl_uris.append((key, obj, uri))
        else:
            log(f"⚠️ Exclude lijst ongeldig (skip): {key} -> {link}")

    exclude_handles: Set[str] = set()
    exclude_dids: Set[str] = set()
    for key, obj, luri in excl_uris:
        note = obj.get("note", "")
        log(f"🚫 Loading exclude list: {key} ({note})")
        members = fetch_list_members(client, luri, limit=max(1000, LIST_MEMBER_LIMIT))
        log(f"🚫 Exclude members: {len(members)}")
        for h, d in members:
            if h:
                exclude_handles.add(h)
            if d:
                exclude_dids.add(d)

    all_candidates: List[Dict] = []

    log(f"Feeds to process: {len(feed_uris)}")
    for key, obj, furi in feed_uris:
        note = obj.get("note", "")
        is_promo_feed = key == PROMO_FEED_KEY
        log(f"📥 Feed: {key} ({note})" + (" [PROMO FEED]" if is_promo_feed else ""))

        items = fetch_feed_items(client, furi, max_items=FEED_MAX_ITEMS)
        cands = build_candidates_from_feed_items(
            items=items,
            cutoff=cutoff,
            exclude_handles=exclude_handles,
            exclude_dids=exclude_dids,
            allow_posts=int(obj.get("allow_posts", 1)),
            allow_replies=int(obj.get("allow_replies", 0)),
            allow_reposts=int(obj.get("allow_reposts", 0)),
            force_refresh=is_promo_feed,
            promo_bucket="promo_feed" if is_promo_feed else None,
            source_priority=int(obj.get("priority", 0)),
        )
        all_candidates.extend(cands)

    log(f"Lists to process: {len(list_uris)}")
    for key, obj, luri in list_uris:
        note = obj.get("note", "")
        members = fetch_list_members(client, luri, limit=max(1000, LIST_MEMBER_LIMIT))
        total_accounts = len(members)
        active_accounts = 0

        tag = ""
        if key == PROMO_RANDOM_LIST_KEY:
            tag = " [PROMO RANDOM]"
        elif key == PROMO_LATEST_LIST_KEY:
            tag = " [PROMO LATEST]"

        log(f"📋 List: {key} ({note}){tag} -> {total_accounts} accounts")

        for h, d in members:
            actor = d or h
            if not actor:
                continue

            if key == PROMO_RANDOM_LIST_KEY:
                author_items = fetch_author_feed(client, actor, PROMO_FETCH_PER_MEMBER)
                cand = pick_random_weighted_candidate(
                    author_items,
                    exclude_handles,
                    exclude_dids,
                    PROMO_RANDOM_POOL,
                    int(obj.get("priority", 0)),
                )
                if cand and not uri_in_cooldown(cand["uri"], post_last_reposted_at, POST_COOLDOWN_HOURS):
                    cand["promo_bucket"] = "promo_random"
                    all_candidates.append(cand)
                    active_accounts += 1

            elif key == PROMO_LATEST_LIST_KEY:
                author_items = fetch_author_feed(client, actor, PROMO_FETCH_PER_MEMBER)
                cand = pick_latest_candidate(
                    author_items,
                    exclude_handles,
                    exclude_dids,
                    "promo_latest",
                    int(obj.get("priority", 0)),
                )
                if cand and not uri_in_cooldown(cand["uri"], post_last_reposted_at, POST_COOLDOWN_HOURS):
                    all_candidates.append(cand)
                    active_accounts += 1

            else:
                author_items = fetch_author_feed(client, actor, AUTHOR_POSTS_PER_MEMBER)
                cands = build_candidates_from_feed_items(
                    items=author_items,
                    cutoff=cutoff,
                    exclude_handles=exclude_handles,
                    exclude_dids=exclude_dids,
                    allow_posts=int(obj.get("allow_posts", 1)),
                    allow_replies=int(obj.get("allow_replies", 0)),
                    allow_reposts=int(obj.get("allow_reposts", 0)),
                    force_refresh=False,
                    promo_bucket=None,
                    source_priority=int(obj.get("priority", 0)),
                )
                if cands:
                    active_accounts += 1
                    all_candidates.extend(cands)

        if total_accounts >= 1400:
            log(f"⚠️ {key} bijna limiet: {total_accounts} accounts")
        elif total_accounts >= 1000:
            log(f"⚠️ {key} groot: {total_accounts} accounts")

        log(f"📊 {key}: total_accounts={total_accounts} | active_accounts={active_accounts}")

    active_hashtags = [h.strip() for h in HASHTAGS if h.strip()]
    log(f"Hashtags to process: {len(active_hashtags)}")
    for query in active_hashtags:
        log(f"🔎 Hashtag search: {query}")
        posts = fetch_hashtag_posts(client, query, HASHTAG_MAX_ITEMS)
        log(f"Hashtag posts fetched for {query}: {len(posts)}")
        all_candidates.extend(
            build_candidates_from_postviews(posts, cutoff, exclude_handles, exclude_dids)
        )

    filtered_candidates: List[Dict] = []
    cooldown_skipped = 0
    for cand in all_candidates:
        if cand.get("promo_bucket") in {"promo_random", "promo_latest"}:
            filtered_candidates.append(cand)
            continue
        if uri_in_cooldown(cand["uri"], post_last_reposted_at, POST_COOLDOWN_HOURS):
            cooldown_skipped += 1
            continue
        filtered_candidates.append(cand)

    if cooldown_skipped:
        log(f"⏳ Cooldown skipped: {cooldown_skipped}")
      
    seen: Set[str] = set()
    deduped: List[Dict] = []
    for c in sorted(filtered_candidates, key=lambda x: (x["created"], -x.get("source_priority", 0))):
        uri = c.get("uri")
        if not uri or uri in seen:
            continue
        seen.add(uri)
        deduped.append(c)

    normal_cands = [c for c in deduped if not c.get("promo_bucket")]
    promo_feed_cands = [c for c in deduped if c.get("promo_bucket") == "promo_feed"]
    promo_latest_cands = [c for c in deduped if c.get("promo_bucket") == "promo_latest"]
    promo_random_cands = [c for c in deduped if c.get("promo_bucket") == "promo_random"]

    normal_cands = apply_anti_cluster(normal_cands)

    log(
        "🧩 Candidates total (deduped): "
        f"{len(deduped)} | normal={len(normal_cands)} | promo_feed={len(promo_feed_cands)} "
        f"| promo_latest={len(promo_latest_cands)} | promo_random={len(promo_random_cands)}"
    )

    total_done = 0
    per_user_count: Dict[str, int] = {}

    buckets = {
        "normal": normal_cands,
        "promo_feed": promo_feed_cands,
        "promo_latest": promo_latest_cands,
        "promo_random": promo_random_cands,
    }

    ordered_groups = sorted(
        [(k, v) for k, v in PROCESS_ORDER.items() if v > 0],
        key=lambda x: x[1]
    )

    group_posted_count: Dict[str, int] = {k: 0 for k in buckets.keys()}

    for group_name, _ in ordered_groups:
        group = buckets.get(group_name, [])

        for c in group:
            if total_done >= MAX_PER_RUN:
                break

            is_promo = group_name != "normal"
            ak = c["author_key"]

            if not is_promo:
                per_user_count.setdefault(ak, 0)
                if per_user_count[ak] >= MAX_PER_USER:
                    continue

            ok = repost_and_like(
                client=client,
                me=me,
                subject_uri=c["uri"],
                subject_cid=c["cid"],
                repost_records=repost_records,
                like_records=like_records,
                force_refresh=is_promo,
            )

            if ok:
                total_done += 1
                group_posted_count[group_name] += 1
                post_last_reposted_at[c["uri"]] = dt_to_iso(utcnow())

                if not is_promo:
                    per_user_count[ak] += 1

                log(f"Repost [{group_name}]: {c['uri']}")
                time.sleep(SLEEP_SECONDS)

    log(
        "Posted per group: "
        + " | ".join(f"{k}={group_posted_count.get(k, 0)}" for k in buckets.keys())
    )

    state["repost_records"] = repost_records
    state["like_records"] = like_records
    state["post_last_reposted_at"] = post_last_reposted_at
    save_state(STATE_FILE, state)
    log(f"🔥 Done — total reposts this run: {total_done}")


if __name__ == "__main__":
    try:
        print("=== ABOUT TO CALL MAIN ===", flush=True)
        main()
    except Exception:
        import traceback
        print("=== FATAL ERROR ===", flush=True)
        traceback.print_exc()
        raise
