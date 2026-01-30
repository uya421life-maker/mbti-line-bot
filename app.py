import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, FlexSendMessage, BubbleContainer,
    BoxComponent, TextComponent, ButtonComponent,
    URIAction
)

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET', '')
CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN', '')

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text
    
    if text == "メンバー登録":
        flex = create_register_flex()
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text="メンバー登録", contents=flex)
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
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
    elif text == "リセット":
        user_data[user_id] = []
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="全データをリセットしました！")
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
            event.reply_token,
            TextSendMessage(text=help_text)
        )
    elif text == "診断スタート":
        members = get_user_members(user_id)
        if len(members) < 2:
            reply_text = "診断には2人以上の登録が必要です。\n「メンバー登録」から追加してください。"
        else:
            reply_text = create_compatibility_result(members)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
    elif text.startswith("登録:"):
        # 簡易登録: 登録:名前,性別,年齢,MBTI
        try:
            data = text.replace("登録:", "").split(",")
            if len(data) == 4:
                name, gender, age, mbti = [d.strip() for d in data]
                members = get_user_members(user_id)
                
                if len(members) >= 20:
                    reply_text = "最大20人まで登録できます。"
                else:
                    members.append({
                        "name": name,
                        "gender": gender,
                        "age": int(age),
                        "mbti": mbti.upper()
                    })
                    reply_text = f"{name}さんを登録しました！（{len(members)}人目）\n\n続けて登録する場合：\n登録:名前,性別,年齢,MBTI\n\n全員揃ったら「診断スタート」と送ってください。"
            else:
                reply_text = "形式が正しくありません。\n例：登録:田中太郎,男,25,INTJ"
        except:
            reply_text = "登録に失敗しました。\n例：登録:田中太郎,男,25,INTJ"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="「ヘルプ」と送ると使い方が見れます！")
        )

def create_register_flex():
    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(text='メンバー登録', weight='bold', size='lg'),
                TextComponent(
                    text='以下の形式でメッセージを送ってください',
                    size='sm',
                    color='#888888',
                    margin='md'
                ),
                TextComponent(
                    text='登録:名前,性別,年齢,MBTI',
                    size='md',
                    margin='lg'
                ),
                TextComponent(
                    text='例：登録:田中太郎,男,25,INTJ',
                    size='sm',
                    color='#888888',
                    margin='sm'
                )
            ]
        )
    )
    return bubble

def create_compatibility_result(members):
    result = "【相性診断結果】\n\n"
    
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            m1 = members[i]
            m2 = members[j]
            compatibility = calculate_compatibility(m1, m2)
            result += f"💫 {m1['name']} × {m2['name']}：{compatibility}%\n"
    
    result += "\n「詳細:名前1,名前2」で詳しいコメントが見れます"
    return result

def calculate_compatibility(m1, m2):
    mbti_score = get_mbti_base_score(m1['mbti'], m2['mbti'])
    
    age_diff = abs(m1['age'] - m2['age'])
    if age_diff <= 5:
        age_bonus = 5
    elif age_diff <= 15:
        age_bonus = 0
    else:
        age_bonus = -5
    
    total = mbti_score + age_bonus
    return max(0, min(100, total))

def get_mbti_base_score(mbti1, mbti2):
    if mbti1 == mbti2:
        return 75
    
    good_pairs = [
        ("INTJ", "ENFP"), ("INFJ", "ENTP"), ("INFP", "ENTJ"), ("INTP", "ENFJ"),
        ("ISTJ", "ESFP"), ("ISFJ", "ESTP"), ("ISTP", "ESFJ"), ("ISFP", "ESTJ")
    ]
    
    for pair in good_pairs:
        if (mbti1, mbti2) == pair or (mbti2, mbti1) == pair:
            return 85
    
    if mbti1[1:3] == mbti2[1:3]:
        return 70
    
    return 60

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
