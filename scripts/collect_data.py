"""
MLB日本人選手データ収集スクリプト
GitHubリポジトリ内に直接データを保存する版
"""
import os
import json
import requests
import feedparser
from datetime import datetime
from urllib.parse import quote

TODAY = datetime.now().strftime('%Y-%m-%d')
DATA_DIR = 'data'

# ===== MLB成績データ取得 =====
def get_mlb_stats(player_id, player_type):
    season = datetime.now().year
    if player_type == 'pitcher':
        group = 'pitching'
    elif player_type == 'two_way':
        group = 'hitting,pitching'
    else:
        group = 'hitting'
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&season={season}&group={group}"
    try:
        r = requests.get(url, timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def get_news(player_name_jp, player_name_en):
    news = {"jp": [], "en": []}
    
    jp_url = f"https://news.google.com/rss/search?q={quote(player_name_jp)}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(jp_url)
        for entry in feed.entries[:15]:
            news["jp"].append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", "") if hasattr(entry, 'source') else ""
            })
    except Exception as e:
        news["jp_error"] = str(e)
    
    en_url = f"https://news.google.com/rss/search?q={quote(player_name_en)}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(en_url)
        for entry in feed.entries[:15]:
            news["en"].append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", "") if hasattr(entry, 'source') else ""
            })
    except Exception as e:
        news["en_error"] = str(e)
    
    return news

# ===== Reddit RSSから現地ファンの声取得 =====
def get_reddit_posts(player_name_en):
    query = quote(player_name_en)
    url = f"https://www.reddit.com/r/baseball/search.rss?q={query}&restrict_sr=1&sort=new"
    posts = []
    try:
        headers = {'User-Agent': 'mlb-tracker/1.0'}
        r = requests.get(url, headers=headers, timeout=15)
        feed = feedparser.parse(r.content)
        for entry in feed.entries[:10]:
            posts.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", "")
            })
    except Exception as e:
        return {"error": str(e), "posts": []}
    return {"posts": posts}

# ===== ファイル保存 =====
def save_file(player_name_jp, filename, content):
    folder = os.path.join(DATA_DIR, player_name_jp, TODAY)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  ✓ Saved: {path}")

# ===== メイン処理 =====
def main():
    with open(os.path.join(os.path.dirname(__file__), 'players.json'), 'r', encoding='utf-8') as f:
        players = json.load(f)
    
    print(f"Started: {TODAY}")
    print(f"Tracking {len(players)} players")
    
    for player in players:
        print(f"\n--- {player['name_jp']} ({player['name_en']}) ---")
        
        # 1. 成績データ
        stats = get_mlb_stats(player['id'], player['type'])
        save_file(player['name_jp'], 'stats.json', json.dumps(stats, ensure_ascii=False, indent=2))
        
        # 2. ニュース
        news = get_news(player['name_jp'], player['name_en'])
        save_file(player['name_jp'], 'news.json', json.dumps(news, ensure_ascii=False, indent=2))
        
        # 3. Reddit
        reddit = get_reddit_posts(player['name_en'])
        save_file(player['name_jp'], 'reddit.json', json.dumps(reddit, ensure_ascii=False, indent=2))
    
    print(f"\nCompleted: {TODAY}")

if __name__ == '__main__':
    main()
