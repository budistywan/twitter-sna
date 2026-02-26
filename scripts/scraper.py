"""
Twitter/X Comment Scraper menggunakan twscrape
Hasil disimpan sebagai CSV untuk analisis SNA
"""

import asyncio
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
QUERY = os.getenv("SEARCH_QUERY", "#indonesia")  # ganti query di env var
MAX_TWEETS = int(os.getenv("MAX_TWEETS", "500"))
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
# ──────────────────────────────────────────────────────────────────────────────


async def scrape_tweets():
    """Scrape tweets menggunakan twscrape (tidak butuh API key berbayar)."""
    try:
        import twscrape
        from twscrape import API, gather
        from twscrape.logger import set_log_level
        set_log_level("WARNING")
    except ImportError:
        print("Installing twscrape...")
        os.system("pip install twscrape --quiet")
        import twscrape
        from twscrape import API, gather
        from twscrape.logger import set_log_level
        set_log_level("WARNING")

    api = API()

    # Tambahkan akun (bisa pakai akun gratis)
    # Simpan kredensial sebagai GitHub Secrets
    username = os.getenv("TW_USERNAME", "")
    password = os.getenv("TW_PASSWORD", "")
    email    = os.getenv("TW_EMAIL", "")

    if username and password and email:
        await api.pool.add_account(username, password, email, password)
        await api.pool.login_all()
    else:
        print("⚠️  Tidak ada akun Twitter dikonfigurasi.")
        print("   Set TW_USERNAME, TW_PASSWORD, TW_EMAIL di GitHub Secrets.")
        print("   Menjalankan mode DEMO dengan data sampel...")
        generate_demo_data()
        return

    # Scraping
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    query_safe = QUERY.replace(" ", "_").replace("#", "hashtag_").replace("@", "at_")
    output_file = OUTPUT_DIR / f"tweets_{query_safe}_{timestamp}.csv"
    nodes_file  = OUTPUT_DIR / f"nodes_{query_safe}_{timestamp}.csv"
    edges_file  = OUTPUT_DIR / f"edges_{query_safe}_{timestamp}.csv"

    tweets_data = []
    print(f"🔍 Mencari: '{QUERY}' | Max: {MAX_TWEETS} tweets")

    async for tweet in api.search(QUERY, limit=MAX_TWEETS):
        row = {
            "tweet_id":       str(tweet.id),
            "created_at":     tweet.date.isoformat(),
            "username":       tweet.user.username,
            "display_name":   tweet.user.displayname,
            "user_id":        str(tweet.user.id),
            "followers":      tweet.user.followersCount,
            "following":      tweet.user.friendsCount,
            "tweet_text":     tweet.rawContent,
            "retweet_count":  tweet.retweetCount,
            "like_count":     tweet.likeCount,
            "reply_count":    tweet.replyCount,
            "quote_count":    tweet.quoteCount,
            "lang":           tweet.lang,
            "source":         tweet.source,
            "in_reply_to_id": str(tweet.inReplyToTweetId) if tweet.inReplyToTweetId else "",
            "in_reply_to_user": tweet.inReplyToUser.username if tweet.inReplyToUser else "",
            "quoted_tweet_id": str(tweet.quotedTweet.id) if tweet.quotedTweet else "",
            "retweet_from":   tweet.retweetedTweet.user.username if tweet.retweetedTweet else "",
            "hashtags":       "|".join(tweet.hashtags) if tweet.hashtags else "",
            "mentions":       "|".join([m.username for m in tweet.mentionedUsers]) if tweet.mentionedUsers else "",
            "urls":           "|".join([u.url for u in tweet.links]) if tweet.links else "",
        }
        tweets_data.append(row)

    if not tweets_data:
        print("❌ Tidak ada tweet ditemukan.")
        return

    # Simpan tweets lengkap
    save_csv(tweets_data, output_file, tweets_data[0].keys())
    print(f"✅ {len(tweets_data)} tweets disimpan → {output_file}")

    # Buat nodes & edges untuk SNA
    build_sna_files(tweets_data, nodes_file, edges_file)
    print(f"✅ SNA files → {nodes_file} | {edges_file}")

    # Summary
    print_summary(tweets_data)


def build_sna_files(tweets, nodes_file, edges_file):
    """
    Buat file nodes & edges untuk Social Network Analysis.

    Nodes  = user (dengan atribut followers, tweet_count, dll)
    Edges  = interaksi (reply, retweet, mention, quote)
    """
    nodes = {}
    edges = []

    for t in tweets:
        # Tambah node
        uname = t["username"]
        if uname not in nodes:
            nodes[uname] = {
                "id":           uname,
                "label":        t["display_name"],
                "followers":    t["followers"],
                "following":    t["following"],
                "tweet_count":  0,
                "total_likes":  0,
                "total_rts":    0,
            }
        nodes[uname]["tweet_count"] += 1
        nodes[uname]["total_likes"] += int(t["like_count"] or 0)
        nodes[uname]["total_rts"]   += int(t["retweet_count"] or 0)

        # Edge: Reply
        if t["in_reply_to_user"] and t["in_reply_to_user"] != uname:
            target = t["in_reply_to_user"]
            if target not in nodes:
                nodes[target] = {"id": target, "label": target, "followers": 0,
                                 "following": 0, "tweet_count": 0, "total_likes": 0, "total_rts": 0}
            edges.append({
                "source": uname, "target": target,
                "type": "reply", "weight": 1,
                "tweet_id": t["tweet_id"]
            })

        # Edge: Retweet
        if t["retweet_from"] and t["retweet_from"] != uname:
            target = t["retweet_from"]
            if target not in nodes:
                nodes[target] = {"id": target, "label": target, "followers": 0,
                                 "following": 0, "tweet_count": 0, "total_likes": 0, "total_rts": 0}
            edges.append({
                "source": uname, "target": target,
                "type": "retweet", "weight": 1,
                "tweet_id": t["tweet_id"]
            })

        # Edge: Mention
        for mention in t["mentions"].split("|"):
            mention = mention.strip()
            if mention and mention != uname:
                if mention not in nodes:
                    nodes[mention] = {"id": mention, "label": mention, "followers": 0,
                                      "following": 0, "tweet_count": 0, "total_likes": 0, "total_rts": 0}
                edges.append({
                    "source": uname, "target": mention,
                    "type": "mention", "weight": 1,
                    "tweet_id": t["tweet_id"]
                })

    # Agregasi edge weight (jumlah interaksi antar pasangan)
    edge_agg = {}
    for e in edges:
        key = (e["source"], e["target"], e["type"])
        if key not in edge_agg:
            edge_agg[key] = {"source": e["source"], "target": e["target"],
                              "type": e["type"], "weight": 0}
        edge_agg[key]["weight"] += 1

    save_csv(nodes.values(), nodes_file,
             ["id", "label", "followers", "following", "tweet_count", "total_likes", "total_rts"])
    save_csv(edge_agg.values(), edges_file,
             ["source", "target", "type", "weight"])


def save_csv(data, filepath, fieldnames):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def print_summary(tweets):
    from collections import Counter
    users = Counter(t["username"] for t in tweets)
    print("\n📊 SUMMARY")
    print(f"   Total tweets  : {len(tweets)}")
    print(f"   Unique users  : {len(users)}")
    print(f"   Top 5 users   :")
    for u, c in users.most_common(5):
        print(f"     @{u}: {c} tweets")


def generate_demo_data():
    """Buat data sampel jika tidak ada akun Twitter."""
    import random
    print("\n📁 Membuat data DEMO untuk testing SNA...")

    users = [f"user_{i}" for i in range(1, 21)]
    tweets = []
    edges  = []
    nodes  = {u: {"id": u, "label": u.title(), "followers": random.randint(10, 5000),
                  "following": random.randint(10, 1000), "tweet_count": 0,
                  "total_likes": 0, "total_rts": 0}
              for u in users}

    for i in range(200):
        src = random.choice(users)
        tgt = random.choice([u for u in users if u != src])
        etype = random.choice(["reply", "retweet", "mention"])
        tweets.append({
            "tweet_id": str(1000 + i),
            "username": src,
            "tweet_text": f"Demo tweet #{i} dari @{src}",
            "retweet_count": random.randint(0, 50),
            "like_count": random.randint(0, 200),
        })
        edges.append({"source": src, "target": tgt, "type": etype, "weight": 1})
        nodes[src]["tweet_count"] += 1

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_csv(tweets, OUTPUT_DIR / f"tweets_demo_{ts}.csv",
             ["tweet_id", "username", "tweet_text", "retweet_count", "like_count"])
    save_csv(nodes.values(), OUTPUT_DIR / f"nodes_demo_{ts}.csv",
             ["id", "label", "followers", "following", "tweet_count", "total_likes", "total_rts"])
    save_csv(edges, OUTPUT_DIR / f"edges_demo_{ts}.csv",
             ["source", "target", "type", "weight"])
    print(f"✅ Demo data tersimpan di /data/")


if __name__ == "__main__":
    asyncio.run(scrape_tweets())
