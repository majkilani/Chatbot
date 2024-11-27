import os
import requests
import re
from flask import Flask, request, jsonify
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from datetime import datetime
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Environment variables for SMTP configuration
SMTP_SERVER = "smtp-mail.outlook.com"
SMTP_PORT = 587
SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')

# Environment variables for application configuration
# SECRET KEY should be environment variables in production
try:
    app.secret_key = os.environ['SECRET_KEY']
except KeyError:
    # Use a default secret key for development purposes only
    app.secret_key = 'development-secret-key-not-for-production-use'

# Class to manage user state
class OrderState:
    def __init__(self):
        self.step = 'start'
        self.quantity = None
        self.phone = None
        self.delivery_type = None
        self.post_office = None

# A dictionary to keep track of user states
user_states = {}

def send_text(sender_id, message):
    """Sends text message back to the user via the Messenger platform."""
    params = {
        "access_token": os.environ['PAGE_ACCESS_TOKEN']
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "recipient": {
            "id": sender_id
        },
        "message": {
            "text": message
        }
    }
    response = requests.post(
        "https://graph.facebook.com/v13.0/me/messages",
        params=params,
        headers=headers,
        data=json.dumps(data)
    )
    if response.status_code != 200:
        logging.error(f"Failed to send response to {sender_id}. Error: {response.text}")

def send_admin_notification(order_details):
    """Send order notification to admin via email."""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = ADMIN_EMAIL
        msg['Subject'] = "🥚 Нове замовлення яєць"
        
        msg.attach(MIMEText(order_details, 'plain', 'utf-8'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        logging.info("Admin notification sent successfully")
        return True
    except Exception as e:
        logging.error(f"Failed to send admin notification: {e}")
        return False

def handle_order_flow(sender_id, message_text):
    if sender_id not in user_states:
        user_states[sender_id] = OrderState()
    
    state = user_states[sender_id]
    
    if state.step == 'start':
        state.step = 'quantity'
        return "Дякуємо за ваше замовлення! 🥚\n\nСкільки лотків яєць ви бажаєте замовити?\n(1 лоток = 20 шт)"
    
    elif state.step == 'quantity':
        try:
            quantity = int(message_text)
            if quantity <= 0:
                return "Будь ласка, введіть правильну кількість лотків (більше 0)"
            state.quantity = quantity
            state.step = 'phone'
            return "Введіть, будь ласка, ваш номер телефону у форматі:\n0971234567"

        except ValueError:
            return "Будь ласка, введіть число (кількість лотків)"
    
    elif state.step == 'phone':
        if re.match(r'^(?:\+?38)?0\d{9}$', message_text.replace(' ', '')):
            state.phone = message_text
            state.step = 'delivery'
            return "Оберіть спосіб доставки:\n\n1 - Нова Пошта\n2 - Укрпошта"
        else:
            return "Будь ласка, введіть правильний номер телефону (наприклад: 0971234567)"

    elif state.step == 'delivery':
        if message_text in ['1', '2']:
            state.delivery_type = 'Нова Пошта' if message_text == '1' else 'Укрпошта'
            state.step = 'post_office'
            return f"Введіть номер відділення {state.delivery_type}:"
        else:
            return "Будь ласка, виберіть 1 (Нова Пошта) або 2 (Укрпошта)"
    
    elif state.step == 'post_office':
        state.post_office = message_text

        order_details = (
            f"🥚 НОВЕ ЗАМОВЛЕННЯ!\n\n"
            f"Кількість лотків: {state.quantity} (по 20 шт)\n"
            f"Телефон: {state.phone}\n"
            f"Доставка: {state.delivery_type}\n"
            f"Відділення: {state.post_office}\n"
            f"ID користувача: {sender_id}\n"
            f"Час замовлення: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        send_admin_notification(order_details)

        customer_response = (
            "🥚 Ваше замовлення:\n\n"
            f"Кількість лотків: {state.quantity} (по 20 шт)\n"
            f"Телефон: {state.phone}\n"
            f"Доставка: {state.delivery_type}\n"
            f"Відділення: {state.post_office}\n\n"
            "Ми зв'яжемося з вами найближчим часом для підтвердження замовлення!\n"
            "Дякуємо, що обрали нас! 🙏"
        )
        
        del user_states[sender_id]
        return customer_response

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == os.environ.get("VERIFY_TOKEN"):
            return request.args.get("hub.challenge")
        return "Invalid token", 403
    
    if request.method == 'POST':
        data = request.get_json()
        if data["object"] == "page":
            for entry in data["entry"]:
                for messaging_event in entry["messaging"]:
                    if messaging_event.get("message"):
                        sender_id = messaging_event["sender"]["id"]
                        if "text" in messaging_event["message"]:
                            message_text = messaging_event["message"]["text"].lower()
                            
                            if any(keyword in message_text for keyword in ['ціна', 'прайс', 'вартість', 'замовити']):
                                response = "Вибачте, але прайс-лист поки що недоступний. Ми працюємо над цим."
                            else:
                                response = handle_order_flow(sender_id, message_text)

                            send_text(sender_id, response)

        return "ok", 200

@app.route('/')
def hello_world():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
