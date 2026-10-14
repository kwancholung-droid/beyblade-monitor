import requests
from bs4 import BeautifulSoup
import time
import os
import json
from datetime import datetime
from pathlib import Path

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ========== Amazon 指定商品 ==========
AMAZON_TARGETS = {
    "B0HJ783F18": {
        "name": "BX-52 ラスタードラグーン 6-60LC",
        "official_price": 2300,
        "min_price": 1800,
        "max_price": 3200
    },
    "B0HJ75X3PN": {
        "name": "BX-53 オールインワンセット",
        "official_price": 7480,
        "min_price": 6000,
        "max_price": 9500
    }
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept-Language": "zh-HK,zh;q=0.9,ja;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SEEN_FILE = Path("seen_toysrus.json")

def load_seen():
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except:
            return set()
    return set()

def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(list(seen), ensure_ascii=False, indent=2), encoding="utf-8")

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("缺少 Token 或 Chat ID")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        print(f"Telegram 回應: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"Telegram 發送失敗: {e}")
        return False

# ========== Amazon 部分 ==========
def extract_amazon_price(soup):
    selectors = [
        "#corePrice_feature_div .a-price .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        ".a-price .a-offscreen",
        "span.a-price-whole",
    ]
    for sel in selectors:
        elem = soup.select_one(sel)
        if elem:
            text = elem.get_text(strip=True)
            digits = ''.join(filter(str.isdigit, text.replace(",", "")))
            if digits:
                price = int(digits)
                if 1000 < price < 50000:
                    return price
    return None

def check_amazon():
    for asin, info in AMAZON_TARGETS.items():
        url = f"https://www.amazon.co.jp/dp/{asin}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            price = extract_amazon_price(soup)
            page_text = soup.get_text()
            in_stock = "在庫切れ" not in page_text and "Currently unavailable" not in page_text

            print(f"[Amazon] {info['name']} 價格: ¥{price if price else '無法取得'}")

            if price and in_stock and info["min_price"] <= price <= info["max_price"]:
                msg = (
                    f"🔔 <b>Amazon 正價上架！</b>\n\n"
                    f"📦 {info['name']}\n"
                    f"💰 ¥{price:,}\n"
                    f"🏷 官方定價 ¥{info['official_price']:,}\n"
                    f"🔗 <a href='{url}'>立即查看</a>\n"
                    f"時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                send_telegram(msg)
        except Exception as e:
            print(f"[Amazon] {asin} 錯誤: {e}")

# ========== 玩具反鬥城部分 ==========
def check_toysrus():
    search_url = "https://www.toysrus.com.hk/zh-hk/search/?q=%E7%88%86%E6%97%8B%E9%99%80%E8%9E%BA"
    category_url = "https://www.toysrus.com.hk/zh-hk/beyblade/"

    seen = load_seen()
    new_items = []

    for url in [search_url, category_url]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 抓取商品
            products = soup.select("div.product-tile, div.product, li.product, a.product-link")
            if not products:
                products = soup.select("a[href*='beyblade'], a[href*='爆旋']")

            for p in products:
                link_elem = p if p.name == "a" else p.select_one("a")
                if not link_elem:
                    continue
                href = link_elem.get("href", "")
                if not href:
                    continue
                if href.startswith("/"):
                    href = "https://www.toysrus.com.hk" + href
                if "toysrus.com.hk" not in href:
                    continue

                title = link_elem.get_text(strip=True) or p.get_text(strip=True)
                title_lower = title.lower()

                # 只關注 BX / UX / CX 系列
                title_upper = title.upper()
                if not any(x in title_upper for x in ["BX-", "UX-", "CX-", "BX ", "UX ", "CX "]):
                    if "爆旋陀螺" not in title and "beyblade" not in title_lower:
                        continue

                # 用連結當唯一識別
                if href in seen:
                    continue

                # 新商品
                seen.add(href)
                new_items.append({
                    "title": title[:80],
                    "url": href
                })

        except Exception as e:
            print(f"[ToysRUs] 檢查 {url} 失敗: {e}")

    if new_items:
        save_seen(seen)
        for item in new_items:
            msg = (
                f"🆕 <b>玩具反鬥城 新商品上架！</b>\n\n"
                f"📦 {item['title']}\n"
                f"🔗 <a href='{item['url']}'>立即查看</a>\n"
                f"時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            send_telegram(msg)
            print(f"[ToysRUs] 已通知新商品: {item['title']}")
    else:
        print("[ToysRUs] 沒有發現新商品")

def main():
    print("爆旋陀螺監控系統啟動（Amazon + 玩具反鬥城）...")
    send_telegram("✅ 監控系統已更新\n現在同時盯著：\n• 日本 Amazon（BX-52 / BX-53）\n• 香港玩具反鬥城（BX / UX / CX 新商品）")

    while True:
        try:
            print(f"\n[{datetime.now()}] 開始檢查...")
            check_amazon()
            check_toysrus()
        except Exception as e:
            print(f"發生錯誤: {e}")
        time.sleep(60)  # 每 1 分鐘

if __name__ == "__main__":
    main()
