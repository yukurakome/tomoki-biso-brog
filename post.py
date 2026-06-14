import os
import json
import requests
import random
from pathlib import Path
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
from requests.auth import HTTPBasicAuth

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WP_USER        = os.environ.get("WP_USER")
WP_PASSWORD    = os.environ.get("WP_PASSWORD")
WP_URL         = os.environ.get("WP_URL")
UNSPLASH_KEY   = os.environ.get("UNSPLASH_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# ── JST ──────────────────────────────────────────────────────────────────
JST = timezone(timedelta(hours=9))

def get_jst_now():
    return datetime.now(JST)

def get_current_season(month: int) -> str:
    if month in (3, 4, 5):     return "春"
    elif month in (6, 7, 8):   return "夏"
    elif month in (9, 10, 11): return "秋"
    else:                       return "冬"

# ════════════════════════════════════════════════════════════════════════
# 月別・季節別 塗装業トピック
# ════════════════════════════════════════════════════════════════════════
SEASONAL_PAINT_INFO = {
    1:  "冬は気温が低く塗料が乾きにくい季節。適切な気温管理と工期設定が重要です。",
    2:  "2月は晴れた日が増え、塗装工事の計画を立てるのに最適な時期です。",
    3:  "春は気温・湿度ともに安定し、外壁塗装の最適シーズン到来です。",
    4:  "4月は塗装工事の繁忙期。早めの見積もり・予約がおすすめです。",
    5:  "ゴールデンウィーク明けは工事を進めやすい好季節です。",
    6:  "梅雨入り前に外壁塗装を完了させたいお客様からのご相談が増える時期です。",
    7:  "梅雨明け後は晴天が続き、夏の外壁塗装シーズンが本格化します。",
    8:  "真夏は高温で塗料の乾燥が速い反面、塗膜品質に注意が必要です。",
    9:  "秋は気温・湿度が安定し、春と並んで塗装に最適なシーズンです。",
    10: "秋の塗装工事の繁忙期。冬前に仕上げたいお客様はお早めに。",
    11: "冬前の最後の繁忙期。屋根・外壁のメンテナンスは今がラストチャンス。",
    12: "年末は工事完了を急ぐ案件が多くなります。早めのご依頼を。",
}

# ════════════════════════════════════════════════════════════════════════
# 月内重複なし抽選
# ════════════════════════════════════════════════════════════════════════
def pick_for_week(items: list, year: int, month: int, week_of_month: int, day_offset: int = 0):
    pool = items.copy()
    rng  = random.Random(year * 1000 + month * 10 + day_offset)
    rng.shuffle(pool)
    return pool[week_of_month % len(pool)]

# ── CTAブロック ──────────────────────────────────────────────────────────
TOMOMI_CTA = """
<div style="background:#f0f4f8; border-left:4px solid #2c7bb6; padding:20px; margin:30px 0; border-radius:8px;">
  <p style="margin:0 0 8px 0; font-weight:bold; font-size:16px;">外壁・屋根塗装のご相談は智己美装へ</p>
  <p style="margin:0 0 12px 0;">埼玉県川口市を中心に、丁寧な施工と適正価格でお客様の大切なお家を守ります。無料見積もり・現地調査実施中です。お気軽にお問い合わせください。</p>
  <a href="https://tomomi-biso.com" target="_blank" style="display:inline-block; background:#2c7bb6; color:#fff; padding:10px 24px; border-radius:4px; text-decoration:none; font-weight:bold;">智己美装 公式サイトを見る</a>
</div>
"""

# ── 共通ルール ──────────────────────────────────────────────────────────
COMMON_RULES = """
【共通ルール】
- 読者（一般住宅オーナー）に語りかける温かい口調（丁寧語）
- 冒頭に「この記事でわかること」をリスト形式で3点
- 各H2見出しの直後に1〜2文のリード文を置く
- 具体的な数字・費用感・年数を積極的に使う（「約15年」「約80〜120万円」など）
- 読者が「へえ！」と思える豆知識を最低1つ（<blockquote>タグで囲む）
- よくある失敗例とその対策を1箇所盛り込む
- まとめの前にFAQ（よくある質問）をH2見出しで3問3答
- 一人称エピソード風の表現を1〜2箇所（例：「現場でよく聞かれるのが…」「実際にお客様から…」）
- HTMLタグはh2, h3, p, ul, ol, li, strong, blockquote, table, tr, th, td のみ使用
- imgタグは不要
"""

# ════════════════════════════════════════════════════════════════════════
# キーワードリスト（曜日別）
# ════════════════════════════════════════════════════════════════════════

# 月曜：外壁・屋根塗装の基礎知識
BASIC_KEYWORDS = [
    "外壁塗装 時期 おすすめ {season}",
    "屋根塗装 費用 相場 埼玉",
    "外壁塗装 塗料 種類 選び方",
    "外壁塗装 業者 選び方 失敗しない",
    "外壁塗装 工程 流れ わかりやすく",
    "チョーキング 外壁 サイン 塗り替え",
]

# 水曜：防水・補修・特殊工事
REPAIR_KEYWORDS = [
    "ベランダ 防水工事 費用 種類",
    "雨漏り 原因 修理 費用",
    "コーキング シーリング 打ち替え 費用",
    "棟板金 浮き 修理 費用",
    "屋根 カバー工法 葺き替え 比較",
    "鉄部塗装 ガレージ フェンス 費用",
]

# 金曜：塗料・色・トレンド・お役立ち情報
TIPS_KEYWORDS = [
    "外壁 色 選び方 失敗しない コツ",
    "遮熱塗料 断熱塗料 効果 費用",
    "外壁塗装 色 シミュレーション 活用法",
    "艶あり 艶なし 塗料 違い 選び方",
    "フッ素塗料 シリコン塗料 無機塗料 比較",
    "外壁塗装 保証 アフター 確認ポイント",
]

# ── 画像キーワード ────────────────────────────────────────────────────────
IMAGE_KEYWORDS_BASIC = [
    "house exterior painting renovation Japan",
    "wall painting professional painter Japan",
    "japanese house exterior renovation before after",
]

IMAGE_KEYWORDS_REPAIR = [
    "roof repair waterproofing Japan",
    "house waterproofing construction work",
    "japanese house roof maintenance repair",
]

IMAGE_KEYWORDS_TIPS = [
    "house paint color exterior design Japan",
    "exterior wall paint brush roller close up",
    "japanese suburban house fresh paint exterior",
]

# ════════════════════════════════════════════════════════════════════════
# Instagram専用キャプション生成
# ════════════════════════════════════════════════════════════════════════
def generate_instagram_caption(model, title: str, excerpt: str, season: str, month: int) -> str:
    seasonal_info = SEASONAL_PAINT_INFO.get(month, "")
    prompt = f"""
あなたは埼玉県川口市の外壁・屋根塗装会社「智己美装」のInstagram担当です。
以下の情報をもとに、Instagramの投稿キャプションを日本語で書いてください。

記事タイトル: {title}
記事の要約: {excerpt}
今の季節: {season}（{month}月）
季節情報: {seasonal_info}

【キャプション条件】
- 冒頭1行で強く引きつける（疑問形・驚きの事実・共感できる一言）
- 2〜4行でその記事の「一番大切なポイント」を伝える
- 智己美装は埼玉県川口市を中心とした地域密着の塗装会社であることを自然に1回だけ触れる
- 絵文字を4〜6個使う（文中・文末に散りばめる）
- 「詳しくはブログで👇」の一文を入れる
- 最後にハッシュタグを改行して10個（#智己美装 #外壁塗装 #屋根塗装 #川口市 #埼玉塗装 必須、残り5個は記事内容に合わせて）
- 全体200字以内（ハッシュタグ除く）
- SNS的な話し言葉で

ハッシュタグは最後にまとめて、本文と1行空けて記載。
キャプション本文のみ出力（前置きや説明は不要）。
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"   Instagram キャプション生成失敗: {e}")
        return (
            f"🏠 {title}\n\n"
            f"{excerpt}\n\n"
            f"詳しくはブログで👇\n\n"
            f"#智己美装 #外壁塗装 #屋根塗装 #川口市 #埼玉塗装 #塗装工事 #リフォーム"
        )


# ════════════════════════════════════════════════════════════════════════
# 記事生成
# ════════════════════════════════════════════════════════════════════════
def generate_content(jst_now):
    model         = genai.GenerativeModel("gemini-2.5-flash")
    year          = jst_now.year
    month         = jst_now.month
    weekday       = jst_now.weekday()
    week_of_month = (jst_now.day - 1) // 7
    season        = get_current_season(month)
    seasonal_info = SEASONAL_PAINT_INFO.get(month, "")

    # ── 月曜日 → 外壁・屋根塗装の基礎知識 ──────────────────────────────
    if weekday == 0:
        raw_kw      = pick_for_week(BASIC_KEYWORDS, year, month, week_of_month, day_offset=1)
        seo_kw      = raw_kw.replace("{season}", season)
        img_kws     = IMAGE_KEYWORDS_BASIC
        category_id_default = 1

        prompt_text = (
            f"あなたはSEOに強い住宅リフォームブログライターです。\n"
            f"「{seo_kw}」をメインキーワードにした記事を日本語で書いてください。\n"
            f"今は{season}（{month}月）です。\n"
            f"【季節情報】{seasonal_info}\n\n"
            f"条件:\n"
            f"- 文字数2000字以上\n"
            f"- タイトルにキーワードを含める（32字以内）\n"
            f"- 冒頭100字以内にキーワードを入れる\n"
            f"- H2見出し4つ、H3見出し3つ以上\n"
            f"- 具体的な費用相場・工期・耐用年数を数字で示す\n"
            f"- 業者選びの注意点を1段落で盛り込む\n"
            f"- 材料・工法の比較は<table>形式で表示\n"
            f"- まとめの後に: 外壁・屋根のことでお困りの際は、埼玉県川口市の智己美装へお気軽にご相談ください。現地調査・見積もりは無料です。\n"
            f"{COMMON_RULES}\n"
            f"出力形式:\n"
            f"【TITLE】タイトル\n"
            f"【EXCERPT】記事の要約（120字以内・SEO用）\n"
            f"【TAGS】タグをカンマ区切りで5個（例: 外壁塗装,屋根塗装,川口市,埼玉,リフォーム）\n"
            f"【CATEGORY_ID】1\n"
            f"【BODY】本文HTML\n"
        )

    # ── 水曜日 → 防水・補修・特殊工事 ──────────────────────────────────
    elif weekday == 2:
        raw_kw      = pick_for_week(REPAIR_KEYWORDS, year, month, week_of_month, day_offset=2)
        seo_kw      = raw_kw.replace("{season}", season)
        img_kws     = IMAGE_KEYWORDS_REPAIR
        category_id_default = 1

        prompt_text = (
            f"あなたはSEOに強い住宅リフォームブログライターです。\n"
            f"「{seo_kw}」をメインキーワードにした記事を日本語で書いてください。\n"
            f"今は{season}（{month}月）です。\n"
            f"【季節情報】{seasonal_info}\n\n"
            f"条件:\n"
            f"- 文字数2000字以上\n"
            f"- タイトルにキーワードを含める（32字以内）\n"
            f"- 冒頭100字以内にキーワードを入れる\n"
            f"- H2見出し4つ、H3見出し3つ以上\n"
            f"- 工事の種類・費用・工期を具体的な数字で説明\n"
            f"- 放置するとどうなるか（リスク）を1段落で明記\n"
            f"- 工法の比較は<table>形式で表示\n"
            f"- まとめの後に: 雨漏り・防水・補修工事のご相談は、埼玉県川口市の智己美装へ。無料診断・見積もり受付中です。\n"
            f"{COMMON_RULES}\n"
            f"出力形式:\n"
            f"【TITLE】タイトル\n"
            f"【EXCERPT】記事の要約（120字以内・SEO用）\n"
            f"【TAGS】タグをカンマ区切りで5個（例: 防水工事,雨漏り,補修,川口市,埼玉）\n"
            f"【CATEGORY_ID】1\n"
            f"【BODY】本文HTML\n"
        )

    # ── 金曜日 → 塗料・色・トレンド・お役立ち情報 ──────────────────────
    else:
        raw_kw      = pick_for_week(TIPS_KEYWORDS, year, month, week_of_month, day_offset=3)
        seo_kw      = raw_kw.replace("{season}", season)
        img_kws     = IMAGE_KEYWORDS_TIPS
        category_id_default = 1

        prompt_text = (
            f"あなたはSEOに強い住宅リフォームブログライターです。\n"
            f"「{seo_kw}」をメインキーワードにした記事を日本語で書いてください。\n"
            f"今は{season}（{month}月）です。\n"
            f"【季節情報】{seasonal_info}\n\n"
            f"条件:\n"
            f"- 文字数2000字以上\n"
            f"- タイトルにキーワードを含める（32字以内）\n"
            f"- 冒頭100字以内にキーワードを入れる\n"
            f"- H2見出し4つ、H3見出し3つ以上\n"
            f"- 製品・塗料の比較は<table>形式で（製品名・特徴・耐用年数・費用目安）\n"
            f"- 選び方の判断基準をol・liの番号付きリストで\n"
            f"- まとめの後に: 塗料・色選びのご相談も智己美装にお任せください。埼玉県川口市を中心に無料でアドバイスいたします。\n"
            f"{COMMON_RULES}\n"
            f"出力形式:\n"
            f"【TITLE】タイトル\n"
            f"【EXCERPT】記事の要約（120字以内・SEO用）\n"
            f"【TAGS】タグをカンマ区切りで5個（例: 塗料,色選び,外壁,川口市,埼玉）\n"
            f"【CATEGORY_ID】1\n"
            f"【BODY】本文HTML\n"
        )

    response = model.generate_content(prompt_text)
    raw_text = response.text

    try:
        title        = raw_text.split("【TITLE】")[1].split("【EXCERPT】")[0].strip()
        excerpt      = raw_text.split("【EXCERPT】")[1].split("【TAGS】")[0].strip()
        tags_raw     = raw_text.split("【TAGS】")[1].split("【CATEGORY_ID】")[0].strip()
        category_str = raw_text.split("【CATEGORY_ID】")[1].split("【BODY】")[0].strip()
        content      = raw_text.split("【BODY】")[1].strip()
        category_id  = int(category_str) if category_str.isdigit() else category_id_default
        tags_list    = [t.strip() for t in tags_raw.split(",") if t.strip()]
    except Exception:
        title       = "塗装コラム " + jst_now.strftime("%Y-%m-%d")
        excerpt     = ""
        tags_list   = []
        category_id = category_id_default
        content     = raw_text

    instagram_caption = generate_instagram_caption(model, title, excerpt, season, month)

    return title, excerpt, tags_list, img_kws, content, category_id, instagram_caption


# ════════════════════════════════════════════════════════════════════════
# 使用済み画像URL管理（重複防止）
# ════════════════════════════════════════════════════════════════════════
USED_IMAGES_FILE = Path(__file__).parent / "used_images.json"

def load_used_images() -> set:
    if USED_IMAGES_FILE.exists():
        try:
            return set(json.loads(USED_IMAGES_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()

def save_used_images(used: set) -> None:
    try:
        USED_IMAGES_FILE.write_text(
            json.dumps(sorted(used), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"   used_images.json 保存失敗: {e}")

FALLBACK_URLS = [
    "https://images.unsplash.com/photo-1558618666-fcd25c85cd64",
    "https://images.unsplash.com/photo-1504307651254-35680f356dfd",
    "https://images.unsplash.com/photo-1581578731548-c64695cc6952",
]

def fetch_unsplash_image(keyword: str, year: int, month: int, day: int,
                         slot: int = 0, used: set = None) -> str:
    fallback = FALLBACK_URLS[slot % len(FALLBACK_URLS)]
    if used is None:
        used = set()
    if not UNSPLASH_KEY:
        return fallback
    try:
        res = requests.get(
            "https://api.unsplash.com/search/photos",
            params={
                "query":       keyword,
                "client_id":   UNSPLASH_KEY,
                "per_page":    30,
                "orientation": "landscape",
            },
            timeout=15
        )
        photos = res.json().get("results", [])
        if not photos:
            return fallback
        rng = random.Random(year * 100000 + month * 1000 + day * 10 + slot * 37)
        rng.shuffle(photos)
        for photo in photos:
            url = photo["urls"]["regular"]
            if url not in used:
                return url
        print(f"   ⚠️ キーワード '{keyword}' の写真が全件使用済み。再利用します。")
        return photos[0]["urls"]["regular"]
    except Exception:
        return fallback

def fetch_unsplash_images(img_kws: list, year: int, month: int, day: int,
                          used: set = None) -> list:
    if used is None:
        used = set()
    urls = []
    for i, kw in enumerate(img_kws):
        url = fetch_unsplash_image(kw, year, month, day, slot=i, used=used)
        urls.append(url)
        used.add(url)
    return urls

def upload_image_to_wp(base_url: str, auth: HTTPBasicAuth, img_url: str, title: str) -> int | None:
    try:
        img_data   = requests.get(img_url, timeout=15).content
        safe_title = "".join(c for c in title[:20] if c.isalnum() or c in ("-", "_"))
        filename   = f"{safe_title or 'paint'}.jpg"
        res = requests.post(
            f"{base_url}/wp-json/wp/v2/media",
            auth=auth,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type":        "image/jpeg",
            },
            data=img_data,
            timeout=30
        )
        if res.status_code == 201:
            media_id = res.json()["id"]
            print(f"   画像アップロード完了 (media_id: {media_id})")
            return media_id
        else:
            print(f"   画像アップロード失敗: {res.status_code}")
    except Exception as e:
        print(f"   画像アップロード例外: {e}")
    return None

def get_or_create_tag_ids(base_url, auth, tag_names):
    tag_ids = []
    for name in tag_names:
        res = requests.get(
            f"{base_url}/wp-json/wp/v2/tags",
            params={"search": name, "per_page": 5},
            auth=auth,
            timeout=30
        )
        matches = [t for t in res.json() if t.get("name") == name]
        if matches:
            tag_ids.append(matches[0]["id"])
        else:
            create_res = requests.post(
                f"{base_url}/wp-json/wp/v2/tags",
                auth=auth,
                json={"name": name},
                timeout=30
            )
            if create_res.status_code == 201:
                tag_ids.append(create_res.json()["id"])
    return tag_ids


# ── メイン ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not WP_URL:
        print("エラー: WP_URL が設定されていません。")
    else:
        jst_now       = get_jst_now()
        year          = jst_now.year
        month         = jst_now.month
        week_of_month = (jst_now.day - 1) // 7

        ai_title, ai_excerpt, ai_tags, ai_img_kws, ai_body, ai_category_id, ai_instagram_caption = generate_content(jst_now)

        used_images = load_used_images()
        print(f"   使用済み画像数: {len(used_images)}件")

        img_urls = fetch_unsplash_images(ai_img_kws, year, month, jst_now.day, used=used_images)
        img_top, img_mid, img_end = img_urls

        def img_tag(url, alt, margin="20px 0"):
            return f'<img src="{url}" alt="{alt}" style="width:100%; border-radius:10px; margin:{margin};">\n'

        h2_positions = [i for i in range(len(ai_body)) if ai_body[i:i+3] == "<h2"]
        split_pos = h2_positions[2] if len(h2_positions) >= 3 else len(ai_body) // 2
        body_first  = ai_body[:split_pos]
        body_second = ai_body[split_pos:]

        full_body = (
            img_tag(img_top, ai_title, margin="0 0 20px 0")
            + body_first
            + img_tag(img_mid, f"{ai_title} - 施工イメージ")
            + body_second
            + img_tag(img_end, f"{ai_title} - まとめ")
            + TOMOMI_CTA
        )

        base_url = WP_URL.rstrip("/")
        auth     = HTTPBasicAuth(WP_USER, WP_PASSWORD)
        tag_ids  = get_or_create_tag_ids(base_url, auth, ai_tags)
        media_id = upload_image_to_wp(base_url, auth, img_top, ai_title)

        data = {
            "title":      ai_title,
            "content":    full_body,
            "excerpt":    ai_excerpt,
            "status":     "publish",
            "categories": [ai_category_id],
            "tags":       tag_ids,
            "meta": {
                "_aioseo_description": ai_excerpt,
            },
        }
        if media_id:
            data["featured_media"] = media_id

        response = requests.post(
            f"{base_url}/wp-json/wp/v2/posts",
            auth=auth,
            json=data,
            timeout=60
        )

        if response.status_code == 201:
            post_url = response.json().get("link", "")
            print(f"✅ 投稿完了 : {ai_title}")
            print(f"   カテゴリー     : {ai_category_id}")
            print(f"   タグ           : {', '.join(ai_tags)}")
            print(f"   画像URL(先頭)  : {img_top}")
            print(f"   画像URL(中盤)  : {img_mid}")
            print(f"   画像URL(末尾)  : {img_end}")
            print(f"   アイキャッチID : {media_id}")
            print(f"   メタディスク   : {ai_excerpt[:60]}…")
            print(f"   記事URL        : {post_url}")

            MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL")
            if MAKE_WEBHOOK_URL:
                try:
                    make_payload = {
                        "image_url": img_top,
                        "caption":   ai_instagram_caption
                    }
                    make_res = requests.post(
                        MAKE_WEBHOOK_URL,
                        json=make_payload,
                        timeout=30
                    )
                    print(f"   Instagram投稿  : {make_res.status_code}")
                    print(f"   Instagramキャプション:\n{ai_instagram_caption[:120]}…")
                except Exception as e:
                    print(f"   Instagram投稿失敗: {e}")
            else:
                print("   MAKE_WEBHOOK_URL未設定のためInstagram投稿スキップ")

            used_images.update(img_urls)
            save_used_images(used_images)
            print(f"   used_images.json 更新 ({len(used_images)}件)")

            if os.environ.get("GITHUB_ACTIONS"):
                import subprocess
                try:
                    subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)
                    subprocess.run(["git", "config", "user.name", "GitHub Actions"], check=True)
                    subprocess.run(["git", "add", str(USED_IMAGES_FILE)], check=True)
                    subprocess.run(
                        ["git", "commit", "-m", f"chore: update used_images [{jst_now.strftime('%Y-%m-%d')}]"],
                        check=True
                    )
                    subprocess.run(["git", "push"], check=True)
                    print("   ✅ used_images.json をリポジトリにコミット済み")
                except subprocess.CalledProcessError as e:
                    print(f"   ⚠️ gitコミット失敗: {e}")

        else:
            print(f"❌ 失敗: {response.status_code}")
            print(response.text)
import json
import requests
import random
from pathlib import Path
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
from requests.auth import HTTPBasicAuth

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WP_USER        = os.environ.get("WP_USER")
WP_PASSWORD    = os.environ.get("WP_PASSWORD")
WP_URL         = os.environ.get("WP_URL")
UNSPLASH_KEY   = os.environ.get("UNSPLASH_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# ── JST ──────────────────────────────────────────────────────────────────
JST = timezone(timedelta(hours=9))

def get_jst_now():
    return datetime.now(JST)

def get_current_season(month: int) -> str:
    if month in (3, 4, 5):     return "春"
    elif month in (6, 7, 8):   return "夏"
    elif month in (9, 10, 11): return "秋"
    else:                       return "冬"

# ════════════════════════════════════════════════════════════════════════
# 月別・季節別 塗装業トピック
# ════════════════════════════════════════════════════════════════════════
SEASONAL_PAINT_INFO = {
    1:  "冬は気温が低く塗料が乾きにくい季節。適切な気温管理と工期設定が重要です。",
    2:  "2月は晴れた日が増え、塗装工事の計画を立てるのに最適な時期です。",
    3:  "春は気温・湿度ともに安定し、外壁塗装の最適シーズン到来です。",
    4:  "4月は塗装工事の繁忙期。早めの見積もり・予約がおすすめです。",
    5:  "ゴールデンウィーク明けは工事を進めやすい好季節です。",
    6:  "梅雨入り前に外壁塗装を完了させたいお客様からのご相談が増える時期です。",
    7:  "梅雨明け後は晴天が続き、夏の外壁塗装シーズンが本格化します。",
    8:  "真夏は高温で塗料の乾燥が速い反面、塗膜品質に注意が必要です。",
    9:  "秋は気温・湿度が安定し、春と並んで塗装に最適なシーズンです。",
    10: "秋の塗装工事の繁忙期。冬前に仕上げたいお客様はお早めに。",
    11: "冬前の最後の繁忙期。屋根・外壁のメンテナンスは今がラストチャンス。",
    12: "年末は工事完了を急ぐ案件が多くなります。早めのご依頼を。",
}

# ════════════════════════════════════════════════════════════════════════
# 月内重複なし抽選
# ════════════════════════════════════════════════════════════════════════
def pick_for_week(items: list, year: int, month: int, week_of_month: int, day_offset: int = 0):
    pool = items.copy()
    rng  = random.Random(year * 1000 + month * 10 + day_offset)
    rng.shuffle(pool)
    return pool[week_of_month % len(pool)]

# ── CTAブロック ──────────────────────────────────────────────────────────
TOMOMI_CTA = """
<div style="background:#f0f4f8; border-left:4px solid #2c7bb6; padding:20px; margin:30px 0; border-radius:8px;">
  <p style="margin:0 0 8px 0; font-weight:bold; font-size:16px;">外壁・屋根塗装のご相談は智己美装へ</p>
  <p style="margin:0 0 12px 0;">埼玉県川口市を中心に、丁寧な施工と適正価格でお客様の大切なお家を守ります。無料見積もり・現地調査実施中です。お気軽にお問い合わせください。</p>
  <a href="https://tomomi-biso.com" target="_blank" style="display:inline-block; background:#2c7bb6; color:#fff; padding:10px 24px; border-radius:4px; text-decoration:none; font-weight:bold;">智己美装 公式サイトを見る</a>
</div>
"""

# ── 共通ルール ──────────────────────────────────────────────────────────
COMMON_RULES = """
【共通ルール】
- 読者（一般住宅オーナー）に語りかける温かい口調（丁寧語）
- 冒頭に「この記事でわかること」をリスト形式で3点
- 各H2見出しの直後に1〜2文のリード文を置く
- 具体的な数字・費用感・年数を積極的に使う（「約15年」「約80〜120万円」など）
- 読者が「へえ！」と思える豆知識を最低1つ（<blockquote>タグで囲む）
- よくある失敗例とその対策を1箇所盛り込む
- まとめの前にFAQ（よくある質問）をH2見出しで3問3答
- 一人称エピソード風の表現を1〜2箇所（例：「現場でよく聞かれるのが…」「実際にお客様から…」）
- HTMLタグはh2, h3, p, ul, ol, li, strong, blockquote, table, tr, th, td のみ使用
- imgタグは不要
"""

# ════════════════════════════════════════════════════════════════════════
# キーワードリスト（曜日別）
# ════════════════════════════════════════════════════════════════════════

# 月曜：外壁・屋根塗装の基礎知識
BASIC_KEYWORDS = [
    "外壁塗装 時期 おすすめ {season}",
    "屋根塗装 費用 相場 埼玉",
    "外壁塗装 塗料 種類 選び方",
    "外壁塗装 業者 選び方 失敗しない",
    "外壁塗装 工程 流れ わかりやすく",
    "チョーキング 外壁 サイン 塗り替え",
]

# 水曜：防水・補修・特殊工事
REPAIR_KEYWORDS = [
    "ベランダ 防水工事 費用 種類",
    "雨漏り 原因 修理 費用",
    "コーキング シーリング 打ち替え 費用",
    "棟板金 浮き 修理 費用",
    "屋根 カバー工法 葺き替え 比較",
    "鉄部塗装 ガレージ フェンス 費用",
]

# 金曜：塗料・色・トレンド・お役立ち情報
TIPS_KEYWORDS = [
    "外壁 色 選び方 失敗しない コツ",
    "遮熱塗料 断熱塗料 効果 費用",
    "外壁塗装 色 シミュレーション 活用法",
    "艶あり 艶なし 塗料 違い 選び方",
    "フッ素塗料 シリコン塗料 無機塗料 比較",
    "外壁塗装 保証 アフター 確認ポイント",
]

# ── 画像キーワード ────────────────────────────────────────────────────────
IMAGE_KEYWORDS_BASIC = [
    "house exterior painting renovation Japan",
    "wall painting professional painter Japan",
    "japanese house exterior renovation before after",
]

IMAGE_KEYWORDS_REPAIR = [
    "roof repair waterproofing Japan",
    "house waterproofing construction work",
    "japanese house roof maintenance repair",
]

IMAGE_KEYWORDS_TIPS = [
    "house paint color exterior design Japan",
    "exterior wall paint brush roller close up",
    "japanese suburban house fresh paint exterior",
]

# ════════════════════════════════════════════════════════════════════════
# Instagram専用キャプション生成
# ════════════════════════════════════════════════════════════════════════
def generate_instagram_caption(model, title: str, excerpt: str, season: str, month: int) -> str:
    seasonal_info = SEASONAL_PAINT_INFO.get(month, "")
    prompt = f"""
あなたは埼玉県川口市の外壁・屋根塗装会社「智己美装」のInstagram担当です。
以下の情報をもとに、Instagramの投稿キャプションを日本語で書いてください。

記事タイトル: {title}
記事の要約: {excerpt}
今の季節: {season}（{month}月）
季節情報: {seasonal_info}

【キャプション条件】
- 冒頭1行で強く引きつける（疑問形・驚きの事実・共感できる一言）
- 2〜4行でその記事の「一番大切なポイント」を伝える
- 智己美装は埼玉県川口市を中心とした地域密着の塗装会社であることを自然に1回だけ触れる
- 絵文字を4〜6個使う（文中・文末に散りばめる）
- 「詳しくはブログで👇」の一文を入れる
- 最後にハッシュタグを改行して10個（#智己美装 #外壁塗装 #屋根塗装 #川口市 #埼玉塗装 必須、残り5個は記事内容に合わせて）
- 全体200字以内（ハッシュタグ除く）
- SNS的な話し言葉で

ハッシュタグは最後にまとめて、本文と1行空けて記載。
キャプション本文のみ出力（前置きや説明は不要）。
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"   Instagram キャプション生成失敗: {e}")
        return (
            f"🏠 {title}\n\n"
            f"{excerpt}\n\n"
            f"詳しくはブログで👇\n\n"
            f"#智己美装 #外壁塗装 #屋根塗装 #川口市 #埼玉塗装 #塗装工事 #リフォーム"
        )


# ════════════════════════════════════════════════════════════════════════
# 記事生成
# ════════════════════════════════════════════════════════════════════════
def generate_content(jst_now):
    model         = genai.GenerativeModel("gemini-2.5-flash")
    year          = jst_now.year
    month         = jst_now.month
    weekday       = jst_now.weekday()
    week_of_month = (jst_now.day - 1) // 7
    season        = get_current_season(month)
    seasonal_info = SEASONAL_PAINT_INFO.get(month, "")

    # ── 月曜日 → 外壁・屋根塗装の基礎知識 ──────────────────────────────
    if weekday == 0:
        raw_kw      = pick_for_week(BASIC_KEYWORDS, year, month, week_of_month, day_offset=1)
        seo_kw      = raw_kw.replace("{season}", season)
        img_kws     = IMAGE_KEYWORDS_BASIC
        category_id_default = 1

        prompt_text = (
            f"あなたはSEOに強い住宅リフォームブログライターです。\n"
            f"「{seo_kw}」をメインキーワードにした記事を日本語で書いてください。\n"
            f"今は{season}（{month}月）です。\n"
            f"【季節情報】{seasonal_info}\n\n"
            f"条件:\n"
            f"- 文字数2000字以上\n"
            f"- タイトルにキーワードを含める（32字以内）\n"
            f"- 冒頭100字以内にキーワードを入れる\n"
            f"- H2見出し4つ、H3見出し3つ以上\n"
            f"- 具体的な費用相場・工期・耐用年数を数字で示す\n"
            f"- 業者選びの注意点を1段落で盛り込む\n"
            f"- 材料・工法の比較は<table>形式で表示\n"
            f"- まとめの後に: 外壁・屋根のことでお困りの際は、千葉市の智己美装へお気軽にご相談ください。現地調査・見積もりは無料です。\n"
            f"{COMMON_RULES}\n"
            f"出力形式:\n"
            f"【TITLE】タイトル\n"
            f"【EXCERPT】記事の要約（120字以内・SEO用）\n"
            f"【TAGS】タグをカンマ区切りで5個（例: 外壁塗装,屋根塗装,千葉市,リフォーム）\n"
            f"【CATEGORY_ID】1\n"
            f"【BODY】本文HTML\n"
        )

    # ── 水曜日 → 防水・補修・特殊工事 ──────────────────────────────────
    elif weekday == 2:
        raw_kw      = pick_for_week(REPAIR_KEYWORDS, year, month, week_of_month, day_offset=2)
        seo_kw      = raw_kw.replace("{season}", season)
        img_kws     = IMAGE_KEYWORDS_REPAIR
        category_id_default = 1

        prompt_text = (
            f"あなたはSEOに強い住宅リフォームブログライターです。\n"
            f"「{seo_kw}」をメインキーワードにした記事を日本語で書いてください。\n"
            f"今は{season}（{month}月）です。\n"
            f"【季節情報】{seasonal_info}\n\n"
            f"条件:\n"
            f"- 文字数2000字以上\n"
            f"- タイトルにキーワードを含める（32字以内）\n"
            f"- 冒頭100字以内にキーワードを入れる\n"
            f"- H2見出し4つ、H3見出し3つ以上\n"
            f"- 工事の種類・費用・工期を具体的な数字で説明\n"
            f"- 放置するとどうなるか（リスク）を1段落で明記\n"
            f"- 工法の比較は<table>形式で表示\n"
            f"- まとめの後に: 雨漏り・防水・補修工事のご相談は、千葉市の智己美装へ。無料診断・見積もり受付中です。\n"
            f"{COMMON_RULES}\n"
            f"出力形式:\n"
            f"【TITLE】タイトル\n"
            f"【EXCERPT】記事の要約（120字以内・SEO用）\n"
            f"【TAGS】タグをカンマ区切りで5個（例: 防水工事,雨漏り,補修,千葉市,）\n"
            f"【CATEGORY_ID】1\n"
            f"【BODY】本文HTML\n"
        )

    # ── 金曜日 → 塗料・色・トレンド・お役立ち情報 ──────────────────────
    else:
        raw_kw      = pick_for_week(TIPS_KEYWORDS, year, month, week_of_month, day_offset=3)
        seo_kw      = raw_kw.replace("{season}", season)
        img_kws     = IMAGE_KEYWORDS_TIPS
        category_id_default = 1

        prompt_text = (
            f"あなたはSEOに強い住宅リフォームブログライターです。\n"
            f"「{seo_kw}」をメインキーワードにした記事を日本語で書いてください。\n"
            f"今は{season}（{month}月）です。\n"
            f"【季節情報】{seasonal_info}\n\n"
            f"条件:\n"
            f"- 文字数2000字以上\n"
            f"- タイトルにキーワードを含める（32字以内）\n"
            f"- 冒頭100字以内にキーワードを入れる\n"
            f"- H2見出し4つ、H3見出し3つ以上\n"
            f"- 製品・塗料の比較は<table>形式で（製品名・特徴・耐用年数・費用目安）\n"
            f"- 選び方の判断基準をol・liの番号付きリストで\n"
            f"- まとめの後に: 塗料・色選びのご相談も智己美装にお任せください。千葉市を中心に無料でアドバイスいたします。\n"
            f"{COMMON_RULES}\n"
            f"出力形式:\n"
            f"【TITLE】タイトル\n"
            f"【EXCERPT】記事の要約（120字以内・SEO用）\n"
            f"【TAGS】タグをカンマ区切りで5個（例: 塗料,色選び,外壁,川口市,埼玉）\n"
            f"【CATEGORY_ID】1\n"
            f"【BODY】本文HTML\n"
        )

    response = model.generate_content(prompt_text)
    raw_text = response.text

    try:
        title        = raw_text.split("【TITLE】")[1].split("【EXCERPT】")[0].strip()
        excerpt      = raw_text.split("【EXCERPT】")[1].split("【TAGS】")[0].strip()
        tags_raw     = raw_text.split("【TAGS】")[1].split("【CATEGORY_ID】")[0].strip()
        category_str = raw_text.split("【CATEGORY_ID】")[1].split("【BODY】")[0].strip()
        content      = raw_text.split("【BODY】")[1].strip()
        category_id  = int(category_str) if category_str.isdigit() else category_id_default
        tags_list    = [t.strip() for t in tags_raw.split(",") if t.strip()]
    except Exception:
        title       = "塗装コラム " + jst_now.strftime("%Y-%m-%d")
        excerpt     = ""
        tags_list   = []
        category_id = category_id_default
        content     = raw_text

    instagram_caption = generate_instagram_caption(model, title, excerpt, season, month)

    return title, excerpt, tags_list, img_kws, content, category_id, instagram_caption


# ════════════════════════════════════════════════════════════════════════
# 使用済み画像URL管理（重複防止）
# ════════════════════════════════════════════════════════════════════════
USED_IMAGES_FILE = Path(__file__).parent / "used_images.json"

def load_used_images() -> set:
    if USED_IMAGES_FILE.exists():
        try:
            return set(json.loads(USED_IMAGES_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()

def save_used_images(used: set) -> None:
    try:
        USED_IMAGES_FILE.write_text(
            json.dumps(sorted(used), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"   used_images.json 保存失敗: {e}")

FALLBACK_URLS = [
    "https://images.unsplash.com/photo-1558618666-fcd25c85cd64",
    "https://images.unsplash.com/photo-1504307651254-35680f356dfd",
    "https://images.unsplash.com/photo-1581578731548-c64695cc6952",
]

def fetch_unsplash_image(keyword: str, year: int, month: int, day: int,
                         slot: int = 0, used: set = None) -> str:
    fallback = FALLBACK_URLS[slot % len(FALLBACK_URLS)]
    if used is None:
        used = set()
    if not UNSPLASH_KEY:
        return fallback
    try:
        res = requests.get(
            "https://api.unsplash.com/search/photos",
            params={
                "query":       keyword,
                "client_id":   UNSPLASH_KEY,
                "per_page":    30,
                "orientation": "landscape",
            },
            timeout=15
        )
        photos = res.json().get("results", [])
        if not photos:
            return fallback
        rng = random.Random(year * 100000 + month * 1000 + day * 10 + slot * 37)
        rng.shuffle(photos)
        for photo in photos:
            url = photo["urls"]["regular"]
            if url not in used:
                return url
        print(f"   ⚠️ キーワード '{keyword}' の写真が全件使用済み。再利用します。")
        return photos[0]["urls"]["regular"]
    except Exception:
        return fallback

def fetch_unsplash_images(img_kws: list, year: int, month: int, day: int,
                          used: set = None) -> list:
    if used is None:
        used = set()
    urls = []
    for i, kw in enumerate(img_kws):
        url = fetch_unsplash_image(kw, year, month, day, slot=i, used=used)
        urls.append(url)
        used.add(url)
    return urls

def upload_image_to_wp(base_url: str, auth: HTTPBasicAuth, img_url: str, title: str) -> int | None:
    try:
        img_data   = requests.get(img_url, timeout=15).content
        safe_title = "".join(c for c in title[:20] if c.isalnum() or c in ("-", "_"))
        filename   = f"{safe_title or 'paint'}.jpg"
        res = requests.post(
            f"{base_url}/wp-json/wp/v2/media",
            auth=auth,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type":        "image/jpeg",
            },
            data=img_data,
            timeout=30
        )
        if res.status_code == 201:
            media_id = res.json()["id"]
            print(f"   画像アップロード完了 (media_id: {media_id})")
            return media_id
        else:
            print(f"   画像アップロード失敗: {res.status_code}")
    except Exception as e:
        print(f"   画像アップロード例外: {e}")
    return None

def get_or_create_tag_ids(base_url, auth, tag_names):
    tag_ids = []
    for name in tag_names:
        res = requests.get(
            f"{base_url}/wp-json/wp/v2/tags",
            params={"search": name, "per_page": 5},
            auth=auth,
            timeout=30
        )
        matches = [t for t in res.json() if t.get("name") == name]
        if matches:
            tag_ids.append(matches[0]["id"])
        else:
            create_res = requests.post(
                f"{base_url}/wp-json/wp/v2/tags",
                auth=auth,
                json={"name": name},
                timeout=30
            )
            if create_res.status_code == 201:
                tag_ids.append(create_res.json()["id"])
    return tag_ids


# ── メイン ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not WP_URL:
        print("エラー: WP_URL が設定されていません。")
    else:
        jst_now       = get_jst_now()
        year          = jst_now.year
        month         = jst_now.month
        week_of_month = (jst_now.day - 1) // 7

        ai_title, ai_excerpt, ai_tags, ai_img_kws, ai_body, ai_category_id, ai_instagram_caption = generate_content(jst_now)

        used_images = load_used_images()
        print(f"   使用済み画像数: {len(used_images)}件")

        img_urls = fetch_unsplash_images(ai_img_kws, year, month, jst_now.day, used=used_images)
        img_top, img_mid, img_end = img_urls

        def img_tag(url, alt, margin="20px 0"):
            return f'<img src="{url}" alt="{alt}" style="width:100%; border-radius:10px; margin:{margin};">\n'

        h2_positions = [i for i in range(len(ai_body)) if ai_body[i:i+3] == "<h2"]
        split_pos = h2_positions[2] if len(h2_positions) >= 3 else len(ai_body) // 2
        body_first  = ai_body[:split_pos]
        body_second = ai_body[split_pos:]

        full_body = (
            img_tag(img_top, ai_title, margin="0 0 20px 0")
            + body_first
            + img_tag(img_mid, f"{ai_title} - 施工イメージ")
            + body_second
            + img_tag(img_end, f"{ai_title} - まとめ")
            + TOMOMI_CTA
        )

        base_url = WP_URL.rstrip("/")
        auth     = HTTPBasicAuth(WP_USER, WP_PASSWORD)
        tag_ids  = get_or_create_tag_ids(base_url, auth, ai_tags)
        media_id = upload_image_to_wp(base_url, auth, img_top, ai_title)

        data = {
            "title":      ai_title,
            "content":    full_body,
            "excerpt":    ai_excerpt,
            "status":     "publish",
            "categories": [ai_category_id],
            "tags":       tag_ids,
            "meta": {
                "_aioseo_description": ai_excerpt,
            },
        }
        if media_id:
            data["featured_media"] = media_id

        response = requests.post(
            f"{base_url}/wp-json/wp/v2/posts",
            auth=auth,
            json=data,
            timeout=60
        )

        if response.status_code == 201:
            post_url = response.json().get("link", "")
            print(f"✅ 投稿完了 : {ai_title}")
            print(f"   カテゴリー     : {ai_category_id}")
            print(f"   タグ           : {', '.join(ai_tags)}")
            print(f"   画像URL(先頭)  : {img_top}")
            print(f"   画像URL(中盤)  : {img_mid}")
            print(f"   画像URL(末尾)  : {img_end}")
            print(f"   アイキャッチID : {media_id}")
            print(f"   メタディスク   : {ai_excerpt[:60]}…")
            print(f"   記事URL        : {post_url}")

            MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL")
            if MAKE_WEBHOOK_URL:
                try:
                    make_payload = {
                        "image_url": img_top,
                        "caption":   ai_instagram_caption
                    }
                    make_res = requests.post(
                        MAKE_WEBHOOK_URL,
                        json=make_payload,
                        timeout=30
                    )
                    print(f"   Instagram投稿  : {make_res.status_code}")
                    print(f"   Instagramキャプション:\n{ai_instagram_caption[:120]}…")
                except Exception as e:
                    print(f"   Instagram投稿失敗: {e}")
            else:
                print("   MAKE_WEBHOOK_URL未設定のためInstagram投稿スキップ")

            used_images.update(img_urls)
            save_used_images(used_images)
            print(f"   used_images.json 更新 ({len(used_images)}件)")

            if os.environ.get("GITHUB_ACTIONS"):
                import subprocess
                try:
                    subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)
                    subprocess.run(["git", "config", "user.name", "GitHub Actions"], check=True)
                    subprocess.run(["git", "add", str(USED_IMAGES_FILE)], check=True)
                    subprocess.run(
                        ["git", "commit", "-m", f"chore: update used_images [{jst_now.strftime('%Y-%m-%d')}]"],
                        check=True
                    )
                    subprocess.run(["git", "push"], check=True)
                    print("   ✅ used_images.json をリポジトリにコミット済み")
                except subprocess.CalledProcessError as e:
                    print(f"   ⚠️ gitコミット失敗: {e}")

        else:
            print(f"❌ 失敗: {response.status_code}")
            print(response.text)
