"""
Twitter/X Scraper - mencari endpoint GraphQL secara otomatis
"""

import csv
import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

QUERY      = os.getenv("SEARCH_QUERY", 'putin (populis OR populisme OR "pemimpin kuat" OR strongman OR "anti elit" OR anti-elit OR rakyat OR "anti barat" OR anti-barat OR "anti Barat") lang:id')
MAX_TWEETS = int(os.getenv("MAX_TWEETS", "200"))
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

AUTH_TOKEN = os.getenv("TW_AUTH_TOKEN", "")
CT0        = os.getenv("TW_CT0", "")
TWID       = os.getenv("TW_TWID", "")

BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"


def make_headers(extra=None):
    h = {
        "authorization":             f"Bearer {BEARER}",
        "cookie":                    f"auth_token={AUTH_TOKEN}; ct0={CT0}; twid={TWID}",
        "x-csrf-token":              CT0,
        "x-twitter-active-user":     "yes",
        "x-twitter-auth-type":       "OAuth2Session",
        "x-twitter-client-language": "en",
        "content-type":              "application/json",
        "user-agent":                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "referer":                   "https://x.com/search",
        "accept":                    "*/*",
        "accept-language":           "en-US,en;q=0.9",
    }
    if extra:
        h.update(extra)
    return h


def find_search_endpoint():
    """Cari GraphQL ID untuk SearchTimeline dari halaman x.com."""
    print("   Mencari endpoint SearchTimeline...")
    try:
        req = urllib.request.Request(
            "https://x.com/search?q=test&src=typed_query",
            headers={
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "cookie": f"auth_token={AUTH_TOKEN}; ct0={CT0}; twid={TWID}",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8")

        # Cari JS bundle URLs
        js_urls = re.findall(r'src="(https://abs\.twimg\.com/responsive-web/client-web[^"]+\.js)"', html)
        print(f"   Ditemukan {len(js_urls)} JS bundles")

        for js_url in js_urls[:10]:
            try:
                req2 = urllib.request.Request(js_url, headers={"user-agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2, timeout=10) as r2:
                    js = r2.read().decode("utf-8")
                # Cari SearchTimeline queryId
                match = re.search(r'queryId:"([^"]+)",operationName:"SearchTimeline"', js)
                if match:
                    gql_id = match.group(1)
                    print(f"   ✅ SearchTimeline ID: {gql_id}")
                    return gql_id
            except Exception:
                continue
    except Exception as e:
        print(f"   ⚠️  Gagal fetch halaman: {e}")

    # Fallback: coba beberapa ID yang diketahui
    known_ids = [
        "gkjsKEUknALED4M5cnMQIw",
        "nK1dw4oV3k4w5TdtcAdSww",
        "lz4bnRNkBH2IFBRmRq3BSBA",
        "SZYM1ALT5XtjvFMqQXn2yw",
        "B6pFbL7qMQnJv2uMqWZKtg",
        "MJanA_2r07_lAwoK6GG7yw",
    ]
    print(f"   Mencoba {len(known_ids)} known IDs...")
    for gql_id in known_ids:
        url = f"https://x.com/i/api/graphql/{gql_id}/SearchTimeline"
        try:
            params = urllib.parse.urlencode({
                "variables": json.dumps({"rawQuery": "test", "count": 1, "product": "Latest"}),
                "features": json.dumps({"rweb_lists_timeline_redesign_enabled": True}),
            })
            req = urllib.request.Request(f"{url}?{params}", headers=make_headers())
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
                if "data" in data:
                    print(f"   ✅ ID valid: {gql_id}")
                    return gql_id
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"   ID {gql_id}: HTTP {e.code}")
                if e.code in (200, 400, 401, 403):
                    return gql_id
        except Exception:
            continue

    return None


def search_tweets(gql_id, query, max_results=200):
    features = json.dumps({
        "rweb_lists_timeline_redesign_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
    })

    all_tweets = []
    cursor     = None
    seen_ids   = set()

    while len(all_tweets) < max_results:
        variables = {
            "rawQuery":    query,
            "count":       20,
            "querySource": "typed_query",
            "product":     "Latest",
        }
        if cursor:
            variables["cursor"] = cursor

        params = urllib.parse.urlencode({
            "variables": json.dumps(variables),
            "features":  features,
        })

        url = f"https://x.com/i/api/graphql/{gql_id}/SearchTimeline?{params}"

        try:
            req = urllib.request.Request(url, headers=make_headers())
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print(f"  ⚠️  Request error: {e}")
            break

        try:
            instructions = (
                data["data"]["search_by_raw_query"]
                    ["search_timeline"]["timeline"]["instructions"]
            )
        except (KeyError, TypeError) as e:
            print(f"  ⚠️  Parse error: {e} | Response: {str(data)[:200]}")
            break

        new_cursor = None
        new_tweets = 0

        for instruction in instructions:
            if instruction.get("type") == "TimelineAddEntries":
                for entry in instruction.get("entries", []):
                    entry_id = entry.get("entryId", "")
                    if "cursor-bottom" in entry_id:
                        try:
                            new_cursor = entry["content"]["value"]
                        except Exception:
                            pass
                        continue
                    try:
                        result = entry["content"]["itemContent"]["tweet_results"]["result"]
                        if result.get("__typename") == "TweetWithVisibilityResults":
                            result = result["tweet"]
                        tweet_id = result["rest_id"]
                        if tweet_id in seen_ids:
                            continue
                        seen_ids.add(tweet_id)
                        legacy = result["legacy"]
                        user   = result["core"]["user_results"]["result"]["legacy"]

                        retweet_from = ""
                        if "retweeted_status_result" in legacy:
                            try:
                                retweet_from = (legacy["retweeted_status_result"]["result"]
                                                ["core"]["user_results"]["result"]["legacy"]["screen_name"])
                            except Exception:
                                pass

                        tweet = {
                            "tweet_id":         tweet_id,
                            "created_at":       legacy.get("created_at", ""),
                            "username":         user.get("screen_name", ""),
                            "display_name":     user.get("name", ""),
                            "user_id":          result["core"]["user_results"]["result"]["rest_id"],
                            "followers":        user.get("followers_count", 0),
                            "following":        user.get("friends_count", 0),
                            "tweet_text":       legacy.get("full_text", ""),
                            "retweet_count":    legacy.get("retweet_count", 0),
                            "like_count":       legacy.get("favorite_count", 0),
                            "reply_count":      legacy.get("reply_count", 0),
                            "quote_count":      legacy.get("quote_count", 0),
                            "lang":             legacy.get("lang", ""),
                            "in_reply_to_user": legacy.get("in_reply_to_screen_name", ""),
                            "retweet_from":     retweet_from,
                            "mentions":         "|".join([m["screen_name"] for m in legacy.get("entities", {}).get("user_mentions", [])]),
                            "hashtags":         "|".join([h["text"] for h in legacy.get("entities", {}).get("hashtags", [])]),
                        }
                        all_tweets.append(tweet)
                        new_tweets += 1
                    except Exception:
                        continue

        print(f"   +{new_tweets} tweets (total: {len(all_tweets)})")
        if not new_cursor or new_tweets == 0:
            break
        cursor = new_cursor
        time.sleep(2)

    return all_tweets


def build_sna_files(tweets, nodes_file, edges_file):
    nodes = {}
    edges = {}
    for t in tweets:
        u = t["username"]
        if u not in nodes:
            nodes[u] = {"id": u, "label": t["display_name"], "followers": t["followers"],
                        "tweet_count": 0, "total_likes": 0, "total_rts": 0}
        nodes[u]["tweet_count"] += 1
        nodes[u]["total_likes"] += int(t["like_count"] or 0)
        nodes[u]["total_rts"]   += int(t["retweet_count"] or 0)

        def add_edge(src, tgt, etype):
            if not tgt or tgt == src:
                return
            if tgt not in nodes:
                nodes[tgt] = {"id": tgt, "label": tgt, "followers": 0,
                              "tweet_count": 0, "total_likes": 0, "total_rts": 0}
            key = (src, tgt, etype)
            if key not in edges:
                edges[key] = {"source": src, "target": tgt, "type": etype, "weight": 0}
            edges[key]["weight"] += 1

        add_edge(u, t["in_reply_to_user"], "reply")
        add_edge(u, t["retweet_from"], "retweet")
        for m in t["mentions"].split("|"):
            add_edge(u, m.strip(), "mention")

    save_csv(nodes.values(), nodes_file,
             ["id", "label", "followers", "tweet_count", "total_likes", "total_rts"])
    save_csv(edges.values(), edges_file,
             ["source", "target", "type", "weight"])
    print(f"   Nodes: {len(nodes)} | Edges: {len(edges)}")


def save_csv(data, filepath, fieldnames):
    rows = list(data)
    if not rows:
        return
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    if not AUTH_TOKEN or not CT0:
        print("❌ TW_AUTH_TOKEN atau TW_CT0 tidak ditemukan.")
        exit(1)

    print(f"🔍 Query: '{QUERY}' | Max: {MAX_TWEETS} tweets")

    gql_id = find_search_endpoint()
    if not gql_id:
        print("❌ Tidak dapat menemukan GraphQL endpoint.")
        exit(1)

    tweets = search_tweets(gql_id, QUERY, MAX_TWEETS)
    if not tweets:
        print("❌ Tidak ada tweet ditemukan.")
        exit(1)

    ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
    tweets_file = OUTPUT_DIR / f"tweets_putin_{ts}.csv"
    nodes_file  = OUTPUT_DIR / f"nodes_putin_{ts}.csv"
    edges_file  = OUTPUT_DIR / f"edges_putin_{ts}.csv"

    save_csv(tweets, tweets_file, list(tweets[0].keys()))
    print(f"\n✅ {len(tweets)} tweets → {tweets_file}")
    build_sna_files(tweets, nodes_file, edges_file)

    from collections import Counter
    users = Counter(t["username"] for t in tweets)
    print(f"\n📊 Top 5 users:")
    for u, c in users.most_common(5):
        print(f"   @{u}: {c} tweets")
