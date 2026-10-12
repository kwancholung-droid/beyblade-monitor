import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime
import json

# ========== 從環境變數讀取（安全） ==========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 優先監控的商品
TARGET_PRODUCTS = {
    "B0HJ783F18": {  # BX-52
        "name": "BX-52 ラスタードラグーン 6-60LC",
        "official_price": 2300,
        "max_price": 2800   # 超過這個就不通知（視為炒價）
    },
    "B0HJ75X3PN": {  # BX-53
        "name": "BX-53 オールインワンセット",
        "official_price": 7480,
        "max_price": 9000
    }
}

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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram 發送失敗: {e}")

def get_product_info(asin: str):
    url = f"https://www.amazon.co.jp/dp/{asin}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 價格
        price = None
        price_elem = soup.select_one(".a-price .a-offscreen")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = int(''.join(filter(str.isdigit, price_text)))

        # 標題
        title_elem = soup.select_one("#productTitle")
        title = title_elem.get_text(strip=True) if title_elem else "未知商品"

        # 是否有庫存感（簡單判斷）
        availability = soup.select_one("#availability")
        in_stock = True
        if availability:
            text = availability.get_text()
            if "在庫切れ" in text or "Currently unavailable" in text:
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
    for asin, info in TARGET_PRODUCTS.items():
        data = get_product_info(asin)
        if not data:
            continue

        price = data["price"]
        if price is None:
            continue

        # 判斷是否接近正價
        if price <= info["max_price"] and data["in_stock"]:
            msg = (
                f"🔔 <b>正價上架通知！</b>\n\n"
                f"📦 <b>{info['name']}</b>\n"
                f"💰 目前價格：¥{price:,}\n"
                f"🏷 官方定價：¥{info['official_price']:,}\n"
                f"🔗 <a href='{data['url']}'>立即查看商品</a>\n\n"
                f"時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            send_telegram(msg)
            print(f"已通知：{info['name']} ¥{price}")

def main():
    print("爆旋陀螺X 監控系統啟動中...")
    send_telegram("✅ 監控系統已成功啟動！\n正在持續盯著 BX-52 與 BX-53 的正價上架。")

    while True:
        try:
            print(f"[{datetime.now()}] 開始檢查...")
            check_targets()
        except Exception as e:
            print(f"發生錯誤: {e}")
        
        # 每 5 分鐘檢查一次
        time.sleep(300)

if __name__ == "__main__":
    main()
