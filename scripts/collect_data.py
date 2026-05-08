"""
MLB日本人選手データ収集スクリプト
毎日実行して、選手別フォルダにデータを保存する
"""
import os
import json
import requests
import feedparser
from datetime import datetime
from urllib.parse import quote
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from google.oauth2 import service_account

# ===== 設定 =====
GDRIVE_FOLDER_ID = os.environ['GDRIVE_FOLDER_ID']
GDRIVE_CREDENTIALS = json.loads(os.environ['GDRIVE_CREDENTIALS'])
TODAY = datetime.now().strftime('%Y-%m-%d')

# ===== Google Drive認証 =====
def get_drive_service():
    creds = service_account.Credentials.from_service_account_info(
        GDRIVE_CREDENTIALS,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)

# ===== Google Driveにフォルダ作成（なければ） =====
def get_or_create_folder(service, name, parent_id):
    query = f"name='{name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields='files(id)').execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    folder = service.files().create(
        body={'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]},
        fields='id'
    ).execute()
    return folder['id']

# ===== Google Driveにファイル保存 =====
def upload_file(service, name, content, folder_id):
    media = MediaInMemoryUpload(content.encode('utf-8'), mimetype='text/plain')
    service.files().create(
        body={'name': name, 'parents': [folder_id]},
        media_body=media
    ).execute()
    print(f"  ✓ Saved: {name}")

# ===== MLB成績データ取得 =====
def get_mlb_stats(player_id, player_type):
    """MLB Stats APIから成績取得"""
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

# ===== Google Newsから日英ニュース取得 =====
def get_news(player_name_jp, player_name_en):
    """Google News RSSから記事取得"""
    news = {"jp": [], "en": []}
    
    # 日本語ニュース
    jp_url = f"https://news.google.com/rss/search?q={quote(player_name_jp)}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(jp_url)
        for entry in feed.entries[:15]:
            news["jp"].append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", "") if hasattr(entry, 'source') else ""
            })
    except Exception as e:
        news["jp_error"] = str(e)
    
    # 英語ニュース
    en_url = f"https://news.google.com/rss/search?q={quote(player_name_en)}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(en_url)
        for entry in feed.entries[:15]:
            news["en"].append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", "") if hasattr(entry, 'source') else ""
            })
    except Exception as e:
        news["en_error"] = str(e)
    
    return news

# ===== Reddit RSSから現地ファンの声取得 =====
def get_reddit_posts(player_name_en):
    """Reddit RSSから関連投稿取得"""
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

# ===== メイン処理 =====
def main():
    # 選手リスト読込
    with open(os.path.join(os.path.dirname(__file__), 'players.json'), 'r', encoding='utf-8') as f:
        players = json.load(f)
    
    service = get_drive_service()
    print(f"Started: {TODAY}")
    print(f"Tracking {len(players)} players")
    
    for player in players:
        print(f"\n--- {player['name_jp']} ({player['name_en']}) ---")
        
        # 選手フォルダ作成
        player_folder_id = get_or_create_folder(service, player['name_jp'], GDRIVE_FOLDER_ID)
        # 日付フォルダ作成
        date_folder_id = get_or_create_folder(service, TODAY, player_folder_id)
        
        # 1. 成績データ
        stats = get_mlb_stats(player['id'], player['type'])
        upload_file(service, 'stats.json', json.dumps(stats, ensure_ascii=False, indent=2), date_folder_id)
        
        # 2. ニュース
        news = get_news(player['name_jp'], player['name_en'])
        upload_file(service, 'news.json', json.dumps(news, ensure_ascii=False, indent=2), date_folder_id)
        
        # 3. Reddit
        reddit = get_reddit_posts(player['name_en'])
        upload_file(service, 'reddit.json', json.dumps(reddit, ensure_ascii=False, indent=2), date_folder_id)
    
    print(f"\nCompleted: {TODAY}")

if __name__ == '__main__':
    main()
