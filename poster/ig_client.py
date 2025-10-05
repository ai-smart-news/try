# poster/ig_client.py

def ig_publish(image_url: str, caption: str) -> None:
    """
    這是 IG 發文函式的替代（stub）。
    之後你可以把這個函式改成真正的 IG 發文流程。
    目前只會 print 出要發的圖片與文字。
    """
    print(f"[IG_PUBLISH] image_url={image_url}")
    print(f"[IG_PUBLISH] caption={caption[:120]}{'...' if len(caption) > 120 else ''}")
