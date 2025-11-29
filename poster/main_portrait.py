# poster/main.py
import json
import os
from datetime import datetime, timedelta
from dateutil import tz
import requests

from ig_client_portrait import ig_publish

# 常數設定
TIMEZONE = "Asia/Taipei"
BASE_JSON_URL = "https://raw.githubusercontent.com/gainote/portrait/refs/heads/main/images//{date}/data.json"
BASE_IMAGE_RAW = "https://raw.githubusercontent.com/gainote/portrait/refs/heads/main/"  # + filename
RECORD_ROOT = "history_portrait"  # 紀錄根資料夾：history/YYYY_MM_DD/posted.json
MAX_DAYS_BACK = 366      # 最多回溯天數，避免無限迴圈

def today_tpe():
    tzinfo = tz.gettz(TIMEZONE)
    return datetime.now(tzinfo).date()

def date_str(d):
    return d.strftime("%Y_%m_%d")

def fetch_day_json(date_s: str):
    url = BASE_JSON_URL.format(date=date_s)
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:
        return None

def ensure_record_file(date_s: str):
    """
    在 repo 建立 history/YYYY_MM_DD/posted.json 的檔案結構
    """
    folder = os.path.join(RECORD_ROOT, date_s)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "posted.json")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"date": date_s, "posted": []}, f, ensure_ascii=False, indent=2)
    return path

def load_posted_set(date_s: str):
    path = ensure_record_file(date_s)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("posted", [])), path

def append_posted(date_s: str, filename: str):
    posted_set, path = load_posted_set(date_s)
    if filename not in posted_set:
        posted_set.add(filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"date": date_s, "posted": sorted(list(posted_set))}, f, ensure_ascii=False, indent=2)

def find_next_unposted():
    """
    從今天起往回找，回傳 (date_s, image_dict) 或 (None, None)
    規則：
      - data.json 存在
      - 其中 images[].prompt 不是空字串
      - 且 images[].filename 尚未在 repo 紀錄檔中
    """
    start = today_tpe()
    for i in range(MAX_DAYS_BACK):
        d = start - timedelta(days=i)
        ds = date_str(d)
        day_json = fetch_day_json(ds)
        if not day_json:
            # 沒有這天的 JSON 就繼續往前
            continue
        images = day_json.get("images", [])
        posted_set, _ = load_posted_set(ds)

        for img in images:
            prompt = (img.get("prompt") or "").strip()
            filename = img.get("filename") or ""
            if not filename:
                continue
            if not prompt:
                # prompt 空字串 -> 忽略
                continue
            if filename in posted_set:
                continue
            # 找到第一張符合規則的
            return ds, img

    return None, None

def build_image_url(filename: str) -> str:
    """
    將 images/2025_10_05/xxx.webp 轉成 raw 檔案 URL
    """
    filename = filename.lstrip("/")
    return BASE_IMAGE_RAW + filename

def main():
    date_s, img = find_next_unposted()
    if not date_s:
        print("沒有找到未發過且有 prompt 的圖片（已回溯到上限天數）。")
        return

    filename = img["filename"]
    prompt = img["prompt"].strip()
    image_url = build_image_url(filename)

    # 3) 發文（目前是 stub）
    ig_publish(
        image_url=image_url,
        original_prompt=prompt,   # 交給 ig_publish 生成文案 + hashtags
        # 可選參數：
        # is_carousel_item=False,
        # alt_text="替代文字",
        # location_id="",
        # user_tags=[{"username":"someone","x":0.5,"y":0.5}],
        # product_tags=[{"product_id":"123","x":0.5,"y":0.5}],
    )

    # 4) 紀錄到本 repo
    append_posted(date_s, filename)

    print(f"✅ 完成：{date_s} -> {filename}")

if __name__ == "__main__":
    main()
