# poster/ig_client.py
import os
import json
import time
import requests
from typing import List, Dict, Optional

# 如果這些環境變數不存在，程式會拋出錯誤，提醒你去設定。
IG_USER_ID = os.getenv("IG_USER_ID_PORTRAIT")
ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN_PORTRAIT")

if not IG_USER_ID:
    raise RuntimeError("環境變數 IG_USER_ID 未設定。請確認已在 GitHub Secrets 或其他環境中設定。")
if not ACCESS_TOKEN:
    raise RuntimeError("環境變數 IG_ACCESS_TOKEN 未設定。請確認已在 GitHub Secrets 或其他環境中設定。")

# 將 IG_USER_ID 轉換為 int，因為它預期是數字
try:
    IG_USER_ID = int(IG_USER_ID)
except ValueError:
    raise ValueError("環境變數 IG_USER_ID 必須是一個有效的數字。")

# 可選：預設參數（也可在呼叫時覆蓋）
DEFAULT_ALT_TEXT = os.getenv("IG_ALT_TEXT", "AI generated artwork")
DEFAULT_LOCATION_ID = os.getenv("IG_LOCATION_ID", "")  # 可留空
# USER_TAGS / PRODUCT_TAGS 可以塞 JSON 字串（如果要用 secrets），或由呼叫者傳入
DEFAULT_USER_TAGS_JSON = os.getenv("IG_USER_TAGS_JSON", "")  # e.g. '[{"username":"name","x":0.5,"y":0.5}]'
DEFAULT_PRODUCT_TAGS_JSON = os.getenv("IG_PRODUCT_TAGS_JSON", "")

# === g4f ===
# try:
#     from g4f.client import Client as Client_g4f
#     _g4f_available = True
# except Exception:
#     _g4f_available = False


def _gen_caption_with_g4f(image_prompt: str) -> str:
    """
    以 g4f 依據圖片 prompt 生成「短中文文案 + 大量 #hashtag」。
    若 g4f 不可用，回退為簡單截斷的 prompt。
    """
    cleaned = (image_prompt or "").strip()
    cleaned = cleaned.replace(cleaned.split('.')[-1], '')
    if not cleaned:
        return ""

    # if not _g4f_available:
    #     # 後備方案：取 20~30 字左右並加幾個通用 hashtag
    #     short = (cleaned[:28] + "…") if len(cleaned) > 30 else cleaned
    #     return f"{short}\n#art #aiart #digitalart #illustration #creative #visualart #artwork #instaart #design"

    prompt_template = f"""
請根據以下圖片描述，幫我生成一段簡短的 IG 發文文字（10~25字內），
語氣自然、有意境，文字盡量白話文不要太文言文，
並在文末加上最多20個 hashtag（# 開頭、用空格分隔、有的用中文有的用英文、請用常見的名詞）。

圖片描述：
{cleaned}
"""
    # client = Client_g4f()
    
    from openai import OpenAI
    
    NV_KEY = os.getenv("NV_KEY")

    client_openai = OpenAI(
      base_url = "https://integrate.api.nvidia.com/v1",
      api_key = NV_KEY
    )
    
    try:
        completion = client_openai.chat.completions.create(
          model="z-ai/glm4.7",
          messages=[{"role":"user","content":prompt_template}],
          temperature=1,
          top_p=1,
          max_tokens=16384,
          extra_body={"chat_template_kwargs":{"enable_thinking":False,"clear_thinking":False}},
          stream=False
        )

        # response = client.chat.completions.create(
        #     model="gemma-3-27b-it",
        #     messages=[{"role": "user", "content": prompt_template}],
        # )
        
        caption = completion.choices[0].message.content.strip()
        return caption
    except Exception as e:
        print("[g4f] 生成文案失敗，改用後備方案：", e)
        short = (cleaned[:28] + "…") if len(cleaned) > 30 else cleaned
        return f"{short}\n#art #aiart #digitalart #illustration #creative #visualart #artwork #instaart #design"


def _post_media_container(
    image_url: str,
    caption: str,
    is_carousel_item: bool = False,
    alt_text: Optional[str] = None,
    location_id: str = "",
    user_tags: Optional[List[Dict]] = None,
    product_tags: Optional[List[Dict]] = None,
) -> dict:
    """
    呼叫 /media 建立 container. 回傳 JSON（包含 id 或 error）
    """
    if not IG_USER_ID or not ACCESS_TOKEN:
        raise RuntimeError("缺少 IG_USER_ID 或 IG_ACCESS_TOKEN（請用 GitHub Secrets 設定）")

    url = f"https://graph.facebook.com/v23.0/{IG_USER_ID}/media"
    params = {
        "image_url": image_url,
        "is_carousel_item": str(bool(is_carousel_item)).lower(),
        "alt_text": alt_text or DEFAULT_ALT_TEXT,
        "caption": caption,
        "access_token": ACCESS_TOKEN,
    }

    if location_id:
        params["location_id"] = location_id

    # user_tags / product_tags 需要 JSON 字串
    if user_tags:
        params["user_tags"] = json.dumps(user_tags, ensure_ascii=False)
    elif DEFAULT_USER_TAGS_JSON:
        params["user_tags"] = DEFAULT_USER_TAGS_JSON

    if product_tags:
        params["product_tags"] = json.dumps(product_tags, ensure_ascii=False)
    elif DEFAULT_PRODUCT_TAGS_JSON:
        params["product_tags"] = DEFAULT_PRODUCT_TAGS_JSON

    resp = requests.post(url, data=params, timeout=60)
    try:
        data = resp.json()
    except Exception:
        data = {"error": {"message": f"Non-JSON response: {resp.text}"}}

    print("[/media] status:", resp.status_code, "| resp:", data)
    return data


def _publish_container(creation_id: str) -> dict:
    """
    呼叫 /media_publish 發佈（將 container 變成貼文）
    """
    url = f"https://graph.facebook.com/v23.0/{IG_USER_ID}/media_publish"
    params = {
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN,
    }
    resp = requests.post(url, data=params, timeout=60)
    try:
        data = resp.json()
    except Exception:
        data = {"error": {"message": f"Non-JSON response: {resp.text}"}}

    print("[/media_publish] status:", resp.status_code, "| resp:", data)
    return data


def ig_publish(
    image_url: str,
    original_prompt: str,
    *,
    force_caption: Optional[str] = None,
    is_carousel_item: bool = False,
    alt_text: Optional[str] = None,
    location_id: str = "",
    user_tags: Optional[List[Dict]] = None,
    product_tags: Optional[List[Dict]] = None,
) -> Optional[str]:
    """
    發 IG 圖片貼文（單張）：
      1) 以 g4f 依 original_prompt 生成 caption（若提供 force_caption 則直接用）
      2) 呼叫 /media 建立 container
      3) 呼叫 /media_publish 發佈
    成功則回傳 ig_media_id；失敗回傳 None
    """
    if image_url.lower().endswith(".webp"):
        print("⚠️ 提醒：IG Graph API 官方僅支援 JPG/PNG，WEBP 可能會發佈失敗：", image_url)

    # 1) 生成 caption
    caption = (force_caption or "").strip()
    if not caption:
        # 如果原始 prompt 空，直接給個簡短預設
        if not (original_prompt or "").strip():
            caption = "#art #aiart #digitalart"
        else:
            caption = _gen_caption_with_g4f(original_prompt)

    print("📝 最終 caption：", caption[:140] + ("..." if len(caption) > 140 else ""))

    # 2) 建立 container
    container = _post_media_container(
        image_url=image_url,
        caption=caption,
        is_carousel_item=is_carousel_item,
        alt_text=alt_text or DEFAULT_ALT_TEXT,
        location_id=location_id or DEFAULT_LOCATION_ID,
        user_tags=user_tags,
        product_tags=product_tags,
    )

    if "error" in container:
        print("❌ 建立 container 失敗：", container["error"])
        return None

    creation_id = container.get("id")
    if not creation_id:
        print("❌ 缺少 creation_id：", container)
        return None

    # （可選）稍等片刻，避免立刻 publish 碰到處理未完成
    time.sleep(2)

    # 3) 發佈
    publish = _publish_container(creation_id)
    if "error" in publish:
        print("❌ 發佈失敗：", publish["error"])
        return None

    ig_media_id = publish.get("id")
    if not ig_media_id:
        print("❌ 發佈結果沒有 id：", publish)
        return None

    print("✅ 發佈成功，IG media id =", ig_media_id)
    return ig_media_id
