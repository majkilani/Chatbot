import os
import re
import requests
from flask import Flask, request, jsonify
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from datetime import datetime
import logging
import json

app = Flask(__name__)

# Global variables
class OrderStatus:
    START = 'start'
    QUANTITY = 'quantity'
    CONFIRM = 'confirm'
    EMAIL = 'email'
    DONE = 'done'

class UserState:
    def __init__(self):
        self.status = OrderStatus.START
        self.quantity = None
        self.email = None

user_states = {}

# Environment variables
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
PERPLEXITY_API_URL = os.environ.get("PERPLEXITY_API_URL")
SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
MAIL_RECIPIENT = os.environ.get("MAIL_RECIPIENT")
FB_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")

# Configuration
logging.basicConfig(level=logging.INFO)

# Utility functions

def send_text(sender_id, message):
    """Sends text message back to the user via the Messenger platform."""
    url = f"https://graph.facebook.com/v13.0/me/messages?access_token={FB_TOKEN}"
    headers = {
        'Content-Type': 'application/json',
    }
    payload = {
        'recipient': {'id': sender_id},
        'message': {'text': message},
    }
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        logging.error(f"Failed to send response to {sender_id}. Error: {response.text}")
    else:
        logging.info(f"Message sent to {sender_id}")

def send_perplex_response(sender_id, query):
    """Query Perplexity AI or similar AI API for a response."""
    if not PERPLEXITY_API_KEY or not PERPLEXITY_API_URL:
        return "На жаль, AI помічник не доступний 🙃. Прошу, спробуйте пізніше."
    
    data = {
        "api_key": PERPLEXITY_API_KEY,
        "query": query,
        "max_tokens": 150
    }
    try:
        response = requests.post(PERPLEXITY_API_URL, data=data)
        if response.status_code == 200:
            answer = response.json().get("answer")
            return answer if answer else "На жаль, я не знайшов відповідь на ваше питання."
        else:
            logging.error(f"Failed to query AI API: {response.text}")
            return "На жаль, щось пішло не так. Спробуйте ще раз."
    except Exception as e:
        logging.error(f"An error occurred while querying AI API: {e}")
        return "Схоже, що AI зараз на перерві. Спробуйте ще раз!"

def handle_order_flow(sender_id, message_text):
    if sender_id not in user_states:
        user_states[sender_id] = UserState()
    
    state = user_states[sender_id]

    if state.status == OrderStatus.START:
        state.status = OrderStatus.QUANTITY
        return "Дякуємо за ваше замовлення! 🥚 Скільки лотків яєць ви бажаєте замовити? (1 лоток = 20 шт)"

    elif state.status == OrderStatus.QUANTITY:
        try:
            quantity = int(message_text)
            price = quantity * 2.5  # 2.5 UAH per tray
            order_message = f"Ви замовили {quantity} лотків яєць. Загальна вартість становить {price:.2f} UAH. \n\nБудь ласка, підтвердіть чи відмовте від замовлення."
            state.quantity = quantity
            state.status = OrderStatus.CONFIRM
            return order_message
        
        except ValueError:
            return "Будь ласка, введіть кількість лотків."

    elif state.status == OrderStatus.CONFIRM:
        if re.match("^п(ри)дтвердити$", message_text.lower()):
            state.status = OrderStatus.EMAIL
            return "Введіть вашу електронну адресу для підтвердження замовлення."
        elif "відмовитись" in message_text.lower():
            user_states[sender_id] = UserState()  # Reset user state
            return "Ваше замовлення скасовано. Якщо у вас є ще питання, спитайте мене."
        else:
            return "Будь ласка, відправте повідомлення 'підтвердити' або 'відмовитись'."

    elif state.status == OrderStatus.EMAIL:
        if re.match(r'^[\w\.-]+@[\w\.-]+$', message_text):
            state.email = message_text
            send_email_confirmation(state.email, state.quantity)
            send_text(sender_id, "Дякуємо за ваше замовлення! Скоро з вами зв'яжеться наш менеджер для уточнення деталей.")
            state.status = OrderStatus.DONE
            return "Ваше замовлення обробляється нашим менеджером. Якщо у вас є ще питання, спитайте мене."
        else:
            return "Будь ласка, введіть корректну електронну адресу."

    elif state.status == OrderStatus.DONE:
        user_states[sender_id] = UserState()  # Reset user state
        return "Чим ще можу допомогти? Поки ви чекаєте, можете задати мені будь-яке питання."

def send_email_confirmation(recipient_email, quantity):
    """Function to send an Email Confirmation to the Manager."""
    subject = f"Нове замовлення яєць ({quantity} лотків)"
    body = f"Менеджер, вам надійшло нове замовлення на {quantity} лотків яєць. Будь ласка, зв'яжіться з клієнтом для уточнення деталей."

    msg = MIMEMultipart()
    msg['From'] = SMTP_EMAIL
    msg['To'] = MAIL_RECIPIENT
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        logging.info("Email confirmation sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email. Error: {e}")

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Handle webhook events from Messenger."""
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Invalid token", 403

    if request.method == 'POST':
        data = request.json
        if data["object"] == "page":
            for entry in data["entry"]:
                for messaging_event in entry["messaging"]:
                    if messaging_event.get("message") and messaging_event['message'].get('text') is not None:
                        sender_id = messaging_event["sender"]["id"]
                        message_text = messaging_event["message"]["text"]

                        if sender_id in user_states and user_states[sender_id].status != OrderStatus.START:
                            response = handle_order_flow(sender_id, message_text)
                        else:
                            # Use AI to handle general queries
                            response = send_perplex_response(sender_id, message_text)

                        send_text(sender_id, response)
        
        return "ok", 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
