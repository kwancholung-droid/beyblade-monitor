import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TARGET_PRODUCTS = {
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
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

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

def extract_price(soup):
    selectors = [
        "#corePrice_feature_div .a-price .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
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

def get_product_info(asin: str):
    url = f"https://www.amazon.co.jp/dp/{asin}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        price = extract_price(soup)
        title_elem = soup.select_one("#productTitle")
        title = title_elem.get_text(strip=True) if title_elem else ""
        page_text = soup.get_text()
        in_stock = "在庫切れ" not in page_text and "Currently unavailable" not in page_text
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
        print(f"{info['name']} 目前價格: ¥{price if price else '無法取得'}")
        if price is None:
            print(f"{info['name']} 無法取得有效價格，跳過")
            continue
        if not data["in_stock"]:
            print(f"{info['name']} 目前無庫存")
            continue
        if info["min_price"] <= price <= info["max_price"]:
            msg = (
                f"🔔 <b>正價上架通知！</b>\n\n"
                f"📦 <b>{info['name']}</b>\n"
                f"💰 目前價格：¥{price:,}\n"
                f"🏷 官方定價：¥{info['official_price']:,}\n"
                f"🔗 <a href='{data['url']}'>立即查看商品</a>\n\n"
                f"時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            if send_telegram(msg):
                print(f"已成功通知：{info['name']} ¥{price}")
            else:
                print(f"通知失敗：{info['name']}")
        else:
            print(f"{info['name']} 價格 ¥{price} 不在正價區間")

def main():
    print("爆旋陀螺X 監控系統啟動中...")
    send_telegram("✅ 監控系統已重新啟動（加強版）\n正在持續盯著 BX-52 與 BX-53。")
    while True:
        try:
            print(f"\n[{datetime.now()}] 開始檢查...")
            check_targets()
        except Exception as e:
            print(f"發生錯誤: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
