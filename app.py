import os
import requests
import base64
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ["LINE_TOKEN"])
handler = WebhookHandler(os.environ["LINE_SECRET"])
GEMINI_KEY = os.environ["GEMINI_KEY"]

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
    reply = ask_gemini(text="你是一個親切的家人，請參考同一個群組聊天室中的既有記憶與最近對話脈絡，直接自然回一句話即可，不必展示思考過程，不必長篇分析，不要用條列。回答一律使用台灣繁體中文，禁止簡體中文、禁止英文整句。

重要：請仔細閱讀對話歷史，確保回應緊扣當前討論的主題，不要偏離話題。如果對話歷史中有正在進行的任務（例如取名、規劃、討論），請優先延續該任務，不要因為最新一句話的詞彙就轉移話題。注意：對方的回應可能是在評論、吐槽、或開玩笑，不要把批評性的話當成對方的心情問題去開導。要像朋友一樣自然回應，可以哈哈一起笑或反駁。" + event.message.text)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    image_data = b""
    for chunk in message_content.iter_content():
        image_data += chunk
    image_base64 = base64.b64encode(image_data).decode("utf-8")
    reply = ask_gemini(text="請在3到5句內溫暖的回應這張圖片的內容", image_base64=image_base64)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    app.run()
