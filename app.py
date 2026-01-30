完璧！

次：ファイルを追加する
今からプログラムのファイルを3つ作ります。

1つ目のファイルを作る

今の画面で「Add file」ボタンをクリック
「Create new file」を選択
ファイル名のところに app.py と入力
下の大きい入力欄に、以下のコードを貼り付けてください：

pythonimport os
import json
import hashlib
import hmac
import base64
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent
from linebot.v3.exceptions import InvalidSignatureError

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET', '')
CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN', '')

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ユーザーデータを保存する辞書
user_data = {}

def get_user_members(user_id):
    if user_id not in user_data:
        user_data[user_id] = []
    return user_data[user_id]

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        if text == "メンバー登録":
            reply = create_register_flex()
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text="メンバー登録", contents=FlexContainer.from_dict(reply))]
                )
            )
        elif text == "メンバー一覧":
            members = get_user_members(user_id)
            if not members:
                reply_text = "まだメンバーが登録されていません。"
            else:
                reply_text = "【登録メンバー】\n"
                for i, m in enumerate(members, 1):
                    reply_text += f"{i}. {m['name']}（{m['gender']}・{m['age']}歳・{m['mbti']}）\n"
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        elif text == "リセット":
            user_data[user_id] = []
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="全データをリセットしました！")]
                )
            )
        elif text == "ヘルプ":
            help_text = """【使い方】
1. 「メンバー登録」で友達を登録
2. 全員登録したら「診断スタート」
3. 相性一覧から詳細を見れます

【コマンド】
・メンバー登録
・メンバー一覧
・診断スタート
・リセット
・ヘルプ"""
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=help_text)]
                )
            )
        elif text == "診断スタート":
            members = get_user_members(user_id)
            if len(members) < 2:
                reply_text = "診断には2人以上の登録が必要です。\n「メンバー登録」から追加してください。"
            else:
                reply_text = create_compatibility_result(members)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        else:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="「ヘルプ」と送ると使い方が見れます！")]
                )
            )

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        if data.startswith("register:"):
            parts = data.replace("register:", "").split(",")
            if len(parts) == 4:
                name, gender, age, mbti = parts
                members = get_user_members(user_id)
                
                if len(members) >= 20:
                    reply_text = "最大20人まで登録できます。"
                else:
                    members.append({
                        "name": name,
                        "gender": gender,
                        "age": int(age),
                        "mbti": mbti
                    })
                    reply_text = f"{name}さんを登録しました！（{len(members)}人目）\n\n続けて登録するか、「診断スタート」で診断できます。"
                
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )

def create_register_flex():
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "メンバー登録", "weight": "bold", "size": "lg"},
                {"type": "text", "text": "下のボタンから入力してください", "size": "sm", "color": "#888888", "margin": "md"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "登録フォームを開く",
                        "uri": f"https://liff.line.me/placeholder"
                    },
                    "style": "primary"
                }
            ]
        }
    }

def create_compatibility_result(members):
    result = "【相性診断結果】\n\n"
    
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            m1 = members[i]
            m2 = members[j]
            compatibility = calculate_compatibility(m1, m2)
            result += f"💫 {m1['name']} × {m2['name']}：{compatibility}%\n"
    
    result += "\n（詳細コメント機能は開発中です）"
    return result

def calculate_compatibility(m1, m2):
    # MBTI相性ベーススコア
    mbti_scores = get_mbti_base_score(m1['mbti'], m2['mbti'])
    
    # 年齢差による補正
    age_diff = abs(m1['age'] - m2['age'])
    if age_diff <= 5:
        age_bonus = 5
    elif age_diff <= 15:
        age_bonus = 0
    else:
        age_bonus = -5
    
    total = mbti_scores + age_bonus
    return max(0, min(100, total))

def get_mbti_base_score(mbti1, mbti2):
    # 簡易的な相性スコア（後で詳細化）
    # 同じタイプ
    if mbti1 == mbti2:
        return 75
    
    # 相性の良い組み合わせ（代表例）
    good_pairs = [
        ("INTJ", "ENFP"), ("INFJ", "ENTP"), ("INFP", "ENTJ"), ("INTP", "ENFJ"),
        ("ISTJ", "ESFP"), ("ISFJ", "ESTP"), ("ISTP", "ESFJ"), ("ISFP", "ESTJ")
    ]
    
    for pair in good_pairs:
        if (mbti1, mbti2) == pair or (mbti2, mbti1) == pair:
            return 85
    
    # 同じ機能を持つタイプ
    if mbti1[1:3] == mbti2[1:3]:  # NTとかNFが同じ
        return 70
    
    return 60  # デフォルト

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
