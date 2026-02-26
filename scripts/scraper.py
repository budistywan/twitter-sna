"""
Twitter/X Scraper via twscrape dengan cookies browser
Tidak perlu login dari server - pakai cookies yang sudah ada
"""

import asyncio
import csv
import os
from datetime import datetime
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
QUERY      = os.getenv("SEARCH_QUERY", "#indonesia")
MAX_TWEETS = int(os.getenv("MAX_TWEETS", "200"))
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
# ──────────────────────────────────────────────────────────────────────────────


async def scrape():
    from twscrape import API
    from twscrape.logger import set_log_level
    set_log_level("WARNING")

    auth_token = os.getenv("TW_AUTH_TOKEN", "")
    ct0        = os.getenv("TW_CT0", "")
    twid       = os.getenv("TW_TWID", "").replace("u%3D", "")

    if not auth_token or not ct0:
        print("❌ TW_AUTH_TOKEN atau TW_CT0 tidak ditemukan di secrets.")
        return

    api = API()

    # Tambah akun via cookies langsung
    username = f"user_{twid}"
    await api.pool.add_account(
        username=username,
        password="placeholder",
        email="placeholder@placeholder.com",
        email_password="placeholder",
        cookies={
            "auth_token": auth_token,
            "ct0": ct0,
        }
    )

    print(f"🔍 Query: '{QUERY}' | Max: {MAX_TWEETS} tweets")

    tweets_data = []
    async for tweet in api.search(QUERY, limit=MAX_TWEETS):
        row = {
            "tweet_id":         str(tweet.id),
            "created_at":       tweet.date.isoformat(),
            "username":         tweet.user.username,
            "display_name":     tweet.user.displayname,
            "user_id":          str(tweet.user.id),
            "followers":        tweet.user.followersCount,
            "following":        tweet.user.friendsCount,
            "tweet_text":       tweet.rawContent,
            "retweet_count":    tweet.retweetCount,
            "like_count":       tweet.likeCount,
            "reply_count":      tweet.replyCount,
            "quote_count":      tweet.quoteCount,
            "lang":             tweet.lang,
            "in_reply_to_user": tweet.inReplyToUser.username if tweet.inReplyToUser else "",
            "retweet_from":     tweet.retweetedTweet.user.username if tweet.retweetedTweet else "",
            "mentions":         "|".join([m.username for m in tweet.mentionedUsers]) if tweet.mentionedUsers else "",
            "hashtags":         "|".join(tweet.hashtags) if tweet.hashtags else "",
        }
        tweets_data.append(row)
        if len(tweets_data) % 50 == 0:
            print(f"   ... {len(tweets_data)} tweets terkumpul")

    if not tweets_data:
        print("❌ Tidak ada tweet ditemukan.")
        return

    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    q_safe = QUERY[:30].replace(" ", "_").replace("#", "htag_").replace('"', "")

    tweets_file = OUTPUT_DIR / f"tweets_{q_safe}_{ts}.csv"
    nodes_file  = OUTPUT_DIR / f"nodes_{q_safe}_{ts}.csv"
    edges_file  = OUTPUT_DIR / f"edges_{q_safe}_{ts}.csv"

    save_csv(tweets_data, tweets_file, tweets_data[0].keys())
    print(f"\n✅ {len(tweets_data)} tweets → {tweets_file}")

    build_sna_files(tweets_data, nodes_file, edges_file)
    print(f"✅ SNA files siap di folder data/")

    from collections import Counter
    users = Counter(t["username"] for t in tweets_data)
    print(f"\n📊 Top 5 users:")
    for u, c in users.most_common(5):
        print(f"   @{u}: {c} tweets")


def build_sna_files(tweets, nodes_file, edges_file):
    nodes = {}
    edges = {}

    for t in tweets:
        u = t["username"]
        if u not in nodes:
            nodes[u] = {"id": u, "label": t["display_name"],
                        "followers": t["followers"], "tweet_count": 0,
                        "total_likes": 0, "total_rts": 0}
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
                edges[key] = {"source": src, "target": tgt,
                              "type": etype, "weight": 0}
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
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "twscrape", "-q"])
    asyncio.run(scrape())
