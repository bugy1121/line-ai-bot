import os
import requests
import base64
import re
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, VideoMessage, TextSendMessage, SourceGroup, SourceRoom

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ["LINE_TOKEN"])
handler = WebhookHandler(os.environ["LINE_SECRET"])
GEMINI_KEY = os.environ["GEMINI_KEY"]

TEXT_PROMPT = "你是一個親切的家人，請參考同一個群組聊天室中的既有記憶與最近對話脈絡，直接自然回一句話即可，不必展示思考過程，不必長篇分析，不要用條列。回答一律使用台灣繁體中文，禁止簡體中文、禁止英文整句。重要：請仔細閱讀對話歷史，確保回應緊扣當前討論的主題，不要偏離話題。如果對話歷史中有正在進行的任務（例如取名、規劃、討論），請優先延續該任務，不要因為最新一句話的詞彙就轉移話題。注意：對方的回應可能是在評論、吐槽、或開玩笑，不要把批評性的話當成對方的心情問題去開導。要像朋友一樣自然回應，可以哈哈一起笑或反駁。如果對方只說很短的字（例如哈哈、好、喔、嗯），就用同樣簡短的方式回應，不要自己編故事或行程。絕對不可以捏造不存在的事實、地點、人名或約定。"

IMAGE_PROMPT = "你現在在家庭 LINE 群組裡回覆圖片，你是親切溫暖的家人，不是外部 AI 助理。任務：看到圖片後，用家人自然聊天的語氣接一句話。回覆原則：一律使用台灣繁體中文，禁止簡體中文。一般 1 到 2 句即可，150 字內。溫暖、簡短、得體，不要像客服。不要自稱 AI、助理、機器人。直接給可貼回 LINE 的文字，不要解釋圖片分析過程。安全規則：不要猜照片裡的人是誰。不要評論人物年齡、胖瘦、美醜、健康、情緒或精神狀態。如果是文件、信件、通知、帳單、證件或截圖，不要逐字解讀，也不要推論是哪個人或哪個機構的文件。如果不確定，就只回畫面氛圍或一句中性安全的話。"

def extract_youtube_id(text):
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def get_youtube_info(video_id):
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        title = data.get("title", "")
        author = data.get("author_name", "")
        return title, f"頻道：{author}"
    except:
        return "", ""

def ask_gemini(text=None, image_base64=None, mime_type="image/jpeg"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    parts = []
    if text:
        parts.append({"text": text})
    if image_base64:
        parts.append({"inline_data": {"mime_type": mime_type, "data": image_base64}})
    payload = {"contents": [{"parts": parts}]}
    response = requests.post(url, json=payload)
    data = response.json()
    if "candidates" in data:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    return str(data)

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_text = event.message.text
    youtube_id = extract_youtube_id(user_text)
    if youtube_id:
        title, description = get_youtube_info(youtube_id)
        if title:
            prompt = f"{TEXT_PROMPT}\n\n這則訊息包含一個 YouTube 影片，資訊如下：\n標題：{title}\n{description}\n\n請根據這部影片的標題自然回應。"
        else:
            prompt = TEXT_PROMPT + user_text
    else:
        prompt = TEXT_PROMPT + user_text
    reply = ask_gemini(text=prompt)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    image_data = b""
    for chunk in message_content.iter_content():
        image_data += chunk
    image_base64 = base64.b64encode(image_data).decode("utf-8")
    reply = ask_gemini(text=IMAGE_PROMPT, image_base64=image_base64)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@handler.add(MessageEvent, message=VideoMessage)
def handle_video(event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="影片我這邊看不到耶，說說裡面有什麼？"))

if __name__ == "__main__":
    app.run()
