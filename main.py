import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime, timedelta
import json

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TARGET_PRODUCTS = {
    "B0HJ783F18": {  # BX-52
        "name": "BX-52 ラスタードラグーン 6-60LC",
        "official_price": 2300,
        "min_price": 1800,
        "max_price": 2800
    },
    "B0HJ75X3PN": {  # BX-53
        "name": "BX-53 オールインワンセット",
        "official_price": 7480,
        "min_price": 6000,
        "max_price": 9000
    }
}

# 記錄上次通知時間，避免洗版（至少間隔 30 分鐘才再通知同一商品）
last_notified = {}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja-JP,ja;q=0.9",
}

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("缺少 Token 或 Chat ID")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"Telegram 回應: {r.status_code}")
    except Exception as e:
        print(f"Telegram 發送失敗: {e}")

def extract_price(soup):
    """更穩健的價格抓取"""
    # 嘗試多個常見選擇器
    selectors = [
        "#corePrice_feature_div .a-price .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        ".a-price .a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "span.a-price-whole"
    ]
    for sel in selectors:
        elems = soup.select(sel)
        for elem in elems:
            text = elem.get_text(strip=True)
            # 只取數字
            digits = ''.join(c for c in text if c.isdigit())
            if digits:
                price = int(digits)
                # 過濾明顯不合理的價格（太小或太大）
                if 500 < price < 50000:
                    return price
    return None

def get_product_info(asin: str):
    url = f"https://www.amazon.co.jp/dp/{asin}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"{asin} 狀態碼: {resp.status_code}")
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        title_elem = soup.select_one("#productTitle")
        title = title_elem.get_text(strip=True) if title_elem else "未知商品"

        price = extract_price(soup)

        # 簡單判斷是否有庫存
        page_text = soup.get_text()
        in_stock = "カートに入れる" in page_text or "Add to Cart" in page_text
        if "在庫切れ" in page_text or "Currently unavailable" in page_text:
            in_stock = False

        return {
            "title": title,
            "price": price,
            "in_stock": in_stock,
            "url": url
        }
    except Exception as e:
        print(f"取得 {asin} 失敗: {e}")
        return None

def check_targets():
    now = datetime.now()
    for asin, info in TARGET_PRODUCTS.items():
        data = get_product_info(asin)
        if not data or data["price"] is None:
            print(f"{info['name']} 無法取得有效價格")
            continue

        price = data["price"]
        print(f"{info['name']} 目前價格: ¥{price}")

        # 只有在合理正價區間才通知
        if info["min_price"] <= price <= info["max_price"] and data["in_stock"]:
            # 檢查是否最近已經通知過（30分鐘內不重複）
            last_time = last_notified.get(asin)
            if last_time and (now - last_time) < timedelta(minutes=30):
                print(f"{info['name']} 最近已通知過，跳過")
                continue

            msg = (
                f"🔔 <b>正價上架通知！</b>\n\n"
                f"📦 <b>{info['name']}</b>\n"
                f"💰 目前價格：¥{price:,}\n"
                f"🏷 官方定價：¥{info['official_price']:,}\n"
                f"🔗 <a href='{data['url']}'>立即查看商品</a>\n\n"
                f"時間：{now.strftime('%Y-%m-%d %H:%M')}"
            )
            send_telegram(msg)
            last_notified[asin] = now
            print(f"已通知：{info['name']} ¥{price}")
        else:
            print(f"{info['name']} 價格 ¥{price} 不在正價區間或無庫存")

def main():
    print("爆旋陀螺X 監控系統啟動中...")
    send_telegram("✅ 監控系統已成功啟動！\n正在持續盯著 BX-52 與 BX-53 的正價上架。\n每 2 分鐘檢查一次。")

    while True:
        try:
            print(f"\n[{datetime.now()}] 開始檢查...")
            check_targets()
        except Exception as e:
            print(f"發生錯誤: {e}")
        
        time.sleep(120)  # 2 分鐘

if __name__ == "__main__":
    main()
