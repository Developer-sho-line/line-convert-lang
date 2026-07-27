import os

from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

from google import genai


app = Flask(__name__)

# 環境変数
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID= os.environ["LINE_USER_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# LINE
configuration = Configuration(
    access_token=LINE_CHANNEL_ACCESS_TOKEN
)

handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

# Language
LANGUAGES = ["#猛虎弁", "#関西弁", "#英語", "#土佐弁", "#博多弁", "#津軽弁"]


@app.route("/")
def home():
    return "LINE Gemini Bot is running!"


@app.route("/callback", methods=["POST"])
def callback():

    signature = request.headers.get("X-Line-Signature")

    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)

    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_message = event.message.text

    mentionees = getattr(event.message.mention, "mentionees", None) or []
    has_my_request = any(m.user_id == LINE_USER_ID for m in mentionees)

    if not bool(has_my_request):
        return

    target_lang = None
    # テキスト内に各言語・方言が含まれているか走査
    for lang in LANGUAGES:
        if lang in user_message:
            target_lang = lang
            break  # 最初に見つかった時点でループを抜ける

    try:

        ai_text = ""

        if target_lang:
            print(f"見つかった言語: {target_lang}")
            request_text = (
                f"下記の言語を{target_lang}に翻訳してください。\n"
                f"解説や提案などの余計な言葉は不要です。\n"
                f"また一番方言色が強い言い方にしてください。\n"
                f"\" {user_message} \""
            )
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=request_text,
            )
            ai_text = response.text
        else:
            supported_langs = ", ".join(LANGUAGES)
            ai_text = (
                f"対応している言語が見つかりませんでした。\n"
                f"以下の対応言語から指定してください：\n"
                f"【 {supported_langs} 】"
            )

    except Exception as e:
        app.logger.exception("Gemini API error: %s", e)
        ai_text = "申し訳ありません。AIでエラーが発生しました。"

    with ApiClient(configuration) as api_client:

        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(
                        text=ai_text
                    )
                ]
            )
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
