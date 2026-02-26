"""
Twitter/X Scraper via Nitter RSS Feed
Tidak butuh login / API key
"""

import csv
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import quote

# ─── CONFIG ───────────────────────────────────────────────────────────────────
QUERY      = os.getenv("SEARCH_QUERY", "#indonesia")
MAX_TWEETS = int(os.getenv("MAX_TWEETS", "200"))
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

# Daftar instance Nitter publik (fallback kalau satu mati)
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.lucabased.xyz",
    "https://nitter.net",
    "https://nitter.1d4.us",
]
# ──────────────────────────────────────────────────────────────────────────────


def fetch_rss(instance: str, query: str, cursor: str = "") -> str | None:
    """Fetch RSS dari Nitter instance."""
    encoded = quote(query)
    url = f"{instance}/search/rss?q={encoded}&f=tweets"
    if cursor:
        url += f"&cursor={cursor}"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8")
    except Exception as e:
        print(f"  ⚠️  {instance} gagal: {e}")
        return None


def parse_rss(xml_text: str) -> list[dict]:
    """Parse RSS XML menjadi list tweet."""
    tweets = []
    try:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item"):
            title     = item.findtext("title", "")
            link      = item.findtext("link", "")
            pub_date  = item.findtext("pubDate", "")
            creator   = item.findtext("{http://purl.org/dc/elements/1.1/}creator", "")
            desc      = item.findtext("description", "")

            # Ekstrak tweet_id dari link
            tweet_id = link.rstrip("/").split("/")[-1].split("#")[0]

            # Ekstrak username dari link
            parts = link.replace("https://", "").split("/")
            username = parts[1] if len(parts) > 1 else creator

            # Parse tanggal
            try:
                dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                created_at = dt.isoformat()
            except Exception:
                created_at = pub_date

            # Cek tipe interaksi
            is_retweet = title.startswith("RT by ")
            is_reply   = title.startswith("R to ")

            tweets.append({
                "tweet_id":    tweet_id,
                "created_at":  created_at,
                "username":    username.lstrip("@"),
                "tweet_text":  desc,
                "link":        link,
                "is_retweet":  is_retweet,
                "is_reply":    is_reply,
                "raw_title":   title,
            })
    except ET.ParseError as e:
        print(f"  ⚠️  XML parse error: {e}")
    return tweets


def build_sna_files(tweets: list[dict], nodes_file: Path, edges_file: Path):
    """Buat nodes & edges untuk SNA dari tweet."""
    nodes = {}
    edges = []

    for t in tweets:
        uname = t["username"]
        if uname and uname not in nodes:
            nodes[uname] = {"id": uname, "label": uname,
                            "tweet_count": 0, "retweet_count": 0}
        if uname:
            nodes[uname]["tweet_count"] += 1

        # Edge: Retweet
        if t["is_retweet"]:
            # Format title: "RT by @user: @original_user: ..."
            title = t["raw_title"]
            try:
                original = title.split("@")[2].split(":")[0].strip()
                if original and original != uname:
                    if original not in nodes:
                        nodes[original] = {"id": original, "label": original,
                                           "tweet_count": 0, "retweet_count": 0}
                    nodes[original]["retweet_count"] += 1
                    edges.append({"source": uname, "target": original,
                                  "type": "retweet", "weight": 1})
            except IndexError:
                pass

        # Edge: Reply
        if t["is_reply"]:
            title = t["raw_title"]
            try:
                target = title.split("@")[1].split(":")[0].strip()
                if target and target != uname:
                    if target not in nodes:
                        nodes[target] = {"id": target, "label": target,
                                         "tweet_count": 0, "retweet_count": 0}
                    edges.append({"source": uname, "target": target,
                                  "type": "reply", "weight": 1})
            except IndexError:
                pass

    # Agregasi edge weight
    edge_agg = {}
    for e in edges:
        key = (e["source"], e["target"], e["type"])
        if key not in edge_agg:
            edge_agg[key] = {**e}
        else:
            edge_agg[key]["weight"] += 1

    save_csv(nodes.values(), nodes_file,
             ["id", "label", "tweet_count", "retweet_count"])
    save_csv(edge_agg.values(), edges_file,
             ["source", "target", "type", "weight"])
    print(f"   Nodes: {len(nodes)} | Edges: {len(edge_agg)}")


def save_csv(data, filepath: Path, fieldnames: list):
    rows = list(data)
    if not rows:
        return
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def scrape():
    print(f"🔍 Query: '{QUERY}' | Max: {MAX_TWEETS} tweets")

    # Cari instance yang hidup
    instance = None
    for inst in NITTER_INSTANCES:
        print(f"   Mencoba: {inst} ...")
        result = fetch_rss(inst, QUERY)
        if result and "<item>" in result:
            instance = inst
            print(f"   ✅ Pakai: {instance}")
            break
        time.sleep(1)

    if not instance:
        print("❌ Semua Nitter instance tidak tersedia. Membuat data demo...")
        generate_demo()
        return

    # Kumpulkan tweets
    all_tweets = []
    seen_ids   = set()
    page       = 0

    while len(all_tweets) < MAX_TWEETS:
        xml_text = fetch_rss(instance, QUERY)
        if not xml_text:
            break

        tweets = parse_rss(xml_text)
        new = [t for t in tweets if t["tweet_id"] not in seen_ids]

        if not new:
            print("   Tidak ada tweet baru, berhenti.")
            break

        for t in new:
            seen_ids.add(t["tweet_id"])
            all_tweets.append(t)

        page += 1
        print(f"   Halaman {page}: +{len(new)} tweets (total: {len(all_tweets)})")

        if len(new) < 20:  # Nitter RSS biasanya 20 per page
            break
        time.sleep(2)

    if not all_tweets:
        print("❌ Tidak ada tweet ditemukan.")
        generate_demo()
        return

    # Simpan
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    q_safe     = QUERY.replace(" ", "_").replace("#", "htag_").replace("@", "at_")
    tweets_file = OUTPUT_DIR / f"tweets_{q_safe}_{ts}.csv"
    nodes_file  = OUTPUT_DIR / f"nodes_{q_safe}_{ts}.csv"
    edges_file  = OUTPUT_DIR / f"edges_{q_safe}_{ts}.csv"

    tweet_fields = ["tweet_id", "created_at", "username", "tweet_text",
                    "link", "is_retweet", "is_reply"]
    save_csv(all_tweets, tweets_file, tweet_fields)
    print(f"\n✅ {len(all_tweets)} tweets → {tweets_file}")

    build_sna_files(all_tweets, nodes_file, edges_file)
    print(f"✅ SNA files siap di folder data/")

    # Summary
    from collections import Counter
    users = Counter(t["username"] for t in all_tweets)
    print(f"\n📊 Top 5 users:")
    for u, c in users.most_common(5):
        print(f"   @{u}: {c} tweets")


def generate_demo():
    import random
    print("📁 Membuat data DEMO...")
    users  = [f"user_{i}" for i in range(1, 21)]
    tweets = []
    edges  = []
    nodes  = {u: {"id": u, "label": u, "tweet_count": 0, "retweet_count": 0}
              for u in users}
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i in range(100):
        src = random.choice(users)
        tgt = random.choice([u for u in users if u != src])
        tweets.append({"tweet_id": str(i), "username": src,
                       "tweet_text": f"Demo tweet #{i}", "created_at": ts,
                       "link": "", "is_retweet": False, "is_reply": False})
        edges.append({"source": src, "target": tgt,
                      "type": random.choice(["reply", "retweet"]), "weight": 1})
        nodes[src]["tweet_count"] += 1

    save_csv(tweets, OUTPUT_DIR / f"tweets_demo_{ts}.csv",
             ["tweet_id", "username", "tweet_text", "created_at"])
    save_csv(nodes.values(), OUTPUT_DIR / f"nodes_demo_{ts}.csv",
             ["id", "label", "tweet_count", "retweet_count"])
    save_csv(edges, OUTPUT_DIR / f"edges_demo_{ts}.csv",
             ["source", "target", "type", "weight"])
    print("✅ Demo data tersimpan di folder data/")


if __name__ == "__main__":
    scrape()
