import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, FlexSendMessage, BubbleContainer,
    BoxComponent, TextComponent, ButtonComponent,
    PostbackAction, QuickReply, QuickReplyButton
)

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET', '')
CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN', '')

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ユーザーデータ
user_data = {}
# 登録中の状態を管理
user_state = {}

def get_user_members(user_id):
    if user_id not in user_data:
        user_data[user_id] = []
    return user_data[user_id]

def get_user_state(user_id):
    if user_id not in user_state:
        user_state[user_id] = {"step": None, "temp": {}}
    return user_state[user_id]

def reset_user_state(user_id):
    user_state[user_id] = {"step": None, "temp": {}}

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
    state = get_user_state(user_id)
    
    # 登録フロー中の処理
    if state["step"] == "name":
        state["temp"]["name"] = text
        state["step"] = "gender"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"{text}さんですね！\n\n性別を選んでください👇",
                quick_reply=QuickReply(items=[
                    QuickReplyButton(action=PostbackAction(label="男", data="gender:男")),
                    QuickReplyButton(action=PostbackAction(label="女", data="gender:女")),
                    QuickReplyButton(action=PostbackAction(label="その他", data="gender:その他"))
                ])
            )
        )
        return
    
    if state["step"] == "age":
        try:
            age = int(text)
            if age < 0 or age > 120:
                raise ValueError
            state["temp"]["age"] = age
            state["step"] = "mbti"
            
            line_bot_api.reply_message(
                event.reply_token,
                create_mbti_selection()
            )
        except ValueError:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="年齢は0〜120の数字で入力してください🙏")
            )
        return
    
    # 通常のコマンド処理
    if text == "メンバー登録":
        reset_user_state(user_id)
        state = get_user_state(user_id)
        state["step"] = "name"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📝 メンバー登録を始めます！\n\n名前を入力してください👇")
        )
    
    elif text == "メンバー一覧":
        members = get_user_members(user_id)
        if not members:
            reply_text = "まだメンバーが登録されていません。\n\n「メンバー登録」と送って登録を始めましょう！"
        else:
            reply_text = "【登録メンバー】\n"
            for i, m in enumerate(members, 1):
                reply_text += f"{i}. {m['name']}（{m['gender']}・{m['age']}歳・{m['mbti']}）\n"
            reply_text += f"\n合計 {len(members)}人"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
    
    elif text == "診断スタート":
        members = get_user_members(user_id)
        if len(members) < 2:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="診断には2人以上の登録が必要です🙏\n\n「メンバー登録」と送って追加してください！")
            )
        else:
            result = create_compatibility_result(members)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=result)
            )
    
    elif text == "リセット":
        user_data[user_id] = []
        reset_user_state(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="全データをリセットしました！\n\n「メンバー登録」と送って最初から始められます。")
        )
    
    elif text == "ヘルプ":
        help_text = """📖 使い方

1️⃣ 「メンバー登録」と送る
2️⃣ 名前→性別→年齢→MBTIを順番に入力
3️⃣ 登録が終わったら「診断スタート」

📌 コマンド一覧
・メンバー登録
・メンバー一覧
・診断スタート
・リセット
・ヘルプ

💡 MBTIがわからない場合
外部サイトで診断できます（開発中）"""
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=help_text)
        )
    
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="「ヘルプ」と送ると使い方が見れます！")
        )

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    state = get_user_state(user_id)
    
    # 性別選択
    if data.startswith("gender:"):
        gender = data.replace("gender:", "")
        state["temp"]["gender"] = gender
        state["step"] = "age"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{gender}ですね！\n\n年齢を数字で入力してください👇\n（例：25）")
        )
    
    # MBTI選択
    elif data.startswith("mbti:"):
        mbti = data.replace("mbti:", "")
        state["temp"]["mbti"] = mbti
        
        # 登録完了
        members = get_user_members(user_id)
        if len(members) >= 20:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="最大20人まで登録できます🙏")
            )
        else:
            members.append({
                "name": state["temp"]["name"],
                "gender": state["temp"]["gender"],
                "age": state["temp"]["age"],
                "mbti": mbti
            })
            
            name = state["temp"]["name"]
            reset_user_state(user_id)
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"✅ {name}さんを登録しました！（{len(members)}人目）\n\n次はどうしますか？👇",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(action=PostbackAction(label="＋追加する", data="action:add")),
                        QuickReplyButton(action=PostbackAction(label="診断スタート", data="action:start"))
                    ])
                )
            )
    
    # 追加or診断選択
    elif data == "action:add":
        state["step"] = "name"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📝 続けて登録します！\n\n名前を入力してください👇")
        )
    
    elif data == "action:start":
        members = get_user_members(user_id)
        if len(members) < 2:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="診断には2人以上の登録が必要です🙏\n\n「メンバー登録」と送って追加してください！")
            )
        else:
            result = create_compatibility_result(members)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=result)
            )

def create_mbti_selection():
    mbti_types = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    items = [QuickReplyButton(action=PostbackAction(label=t, data=f"mbti:{t}")) for t in mbti_types[:13]]
    
    return TextSendMessage(
        text="MBTIを選んでください👇\n\n（表示されていないタイプは下にスクロール）",
        quick_reply=QuickReply(items=items)
    )

def create_compatibility_result(members):
    result = "🔮 相性診断結果\n\n"
    
    pairs = []
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            m1 = members[i]
            m2 = members[j]
            score = calculate_compatibility(m1, m2)
            pairs.append((m1, m2, score))
    
    pairs.sort(key=lambda x: x[2], reverse=True)
    
    for m1, m2, score in pairs:
        if score >= 80:
            emoji = "💕"
        elif score >= 60:
            emoji = "😊"
        elif score >= 40:
            emoji = "🤝"
        else:
            emoji = "💭"
        
        result += f"{emoji} {m1['name']} × {m2['name']}：{score}%\n"
    
    result += "\n\n💡 詳細を見たいペアの名前を\n「詳細:〇〇,△△」で送ってください"
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
