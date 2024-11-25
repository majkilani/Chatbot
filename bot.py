from flask import Flask, request
import requests
import os
import json
from datetime import datetime

app = Flask(__name__)

# Temporary order storage (replace with database in production)
user_sessions = {}

ORDER_STATES = {
    'QUANTITY': 'quantity',
    'PHONE': 'phone',
    'LOCATION': 'location',
    'ADDRESS': 'address',
    'CONFIRM': 'confirm'
}

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                sender_id = messaging_event["sender"]["id"]
                
                if messaging_event.get("message"):
                    handle_message(sender_id, messaging_event["message"])
                elif messaging_event.get("postback"):
                    handle_postback(sender_id, messaging_event["postback"])
    return "ok", 200

def handle_message(sender_id, message):
    if "text" in message:
        text = message["text"].lower()
        
        if text == "замовити":
            start_order(sender_id)
        elif sender_id in user_sessions:
            process_order_step(sender_id, text)
        else:
            send_welcome_message(sender_id)

def start_order(sender_id):
    user_sessions[sender_id] = {
        'state': ORDER_STATES['QUANTITY'],
        'order_data': {}
    }
    send_message(sender_id, "🥚 Скільки десятків яєць ви бажаєте замовити?\n\nБудь ласка, введіть число:")

def process_order_step(sender_id, text):
    current_state = user_sessions[sender_id]['state']
    
    if current_state == ORDER_STATES['QUANTITY']:
        if text.isdigit() and int(text) > 0:
            user_sessions[sender_id]['order_data']['quantity'] = int(text)
            user_sessions[sender_id]['state'] = ORDER_STATES['PHONE']
            send_message(sender_id, "📱 Введіть ваш номер телефону у форматі:\n+380XXXXXXXXX")
        else:
            send_message(sender_id, "❌ Будь ласка, введіть правильну кількість (більше 0)")

    elif current_state == ORDER_STATES['PHONE']:
        if validate_phone(text):
            user_sessions[sender_id]['order_data']['phone'] = text
            user_sessions[sender_id]['state'] = ORDER_STATES['ADDRESS']
            send_message(sender_id, "📍 Введіть адресу доставки:")
        else:
            send_message(sender_id, "❌ Неправильний формат номера. Спробуйте ще раз (например: +380991234567)")

    elif current_state == ORDER_STATES['ADDRESS']:
        user_sessions[sender_id]['order_data']['address'] = text
        show_order_confirmation(sender_id)
        user_sessions[sender_id]['state'] = ORDER_STATES['CONFIRM']

def validate_phone(phone):
    # Basic phone validation
    return phone.startswith('+380') and len(phone) == 13 and phone[1:].isdigit()

def show_order_confirmation(sender_id):
    order_data = user_sessions[sender_id]['order_data']
    confirmation_message = f"""
🧾 Підтвердіть ваше замовлення:

📦 Кількість: {order_data['quantity']} десятків
📱 Телефон: {order_data['phone']}
📍 Адреса: {order_data['address']}

💰 Сума до сплати: {order_data['quantity'] * 100} грн

Все вірно?"""
    
    data = {
        "recipient": {"id": sender_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": confirmation_message,
                    "buttons": [
                        {
                            "type": "postback",
                            "title": "✅ Підтвердити",
                            "payload": "CONFIRM_ORDER"
                        },
                        {
                            "type": "postback",
                            "title": "❌ Скасувати",
                            "payload": "CANCEL_ORDER"
                        }
                    ]
                }
            }
        }
    }
    send_api_request(data)

def handle_postback(sender_id, postback):
    payload = postback["payload"]
    
    if payload == "CONFIRM_ORDER":
        if sender_id in user_sessions:
            # Here you would save the order to your database
            order_data = user_sessions[sender_id]['order_data']
            send_message(sender_id, f"""
✅ Замовлення підтверджено!

🚚 Наш менеджер зв'яжеться з вами найближчим часом для уточнення деталей доставки.

Дякуємо за замовлення! 🙏
""")
            # Clear the session
            del user_sessions[sender_id]
        
    elif payload == "CANCEL_ORDER":
        if sender_id in user_sessions:
            del user_sessions[sender_id]
        send_message(sender_id, "❌ Замовлення скасовано. Якщо хочете зробити нове замовлення, напишіть 'Замовити'")

def send_welcome_message(sender_id):
    send_message(sender_id, """
Вітаємо! 👋

🥚 Для замовлення яєць напишіть "Замовити"

Наші переваги:
✅ Свіжі домашні яйця
✅ Доставка по місту
✅ Гнучкі ціни
""")

def send_message(recipient_id, message_text):
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    send_api_request(data)

def send_api_request(data):
    params = {"access_token": os.environ["PAGE_ACCESS_TOKEN"]}
    headers = {"Content-Type": "application/json"}
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", 
                     params=params, headers=headers, json=data)
    if r.status_code != 200:
        print(r.status_code)
        print(r.text)

@app.route('/setup', methods=['GET'])
def setup_bot():
    data = {
        "get_started": {"payload": "GET_STARTED"},
        "greeting": [
            {
                "locale": "default",
                "text": "Вітаємо! Замовляйте свіжі яйця з доставкою! 🥚"
            }
        ]
    }
    params = {"access_token": os.environ["PAGE_ACCESS_TOKEN"]}
    headers = {"Content-Type": "application/json"}
    r = requests.post("https://graph.facebook.com/v2.6/me/messenger_profile", 
                     params=params, headers=headers, json=data)
    return "Налаштування завершено!", 200

if __name__ == "__main__":
    app.run(debug=True)
