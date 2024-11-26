from flask import Flask, request
import requests
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Facebook API Configuration
PAGE_ACCESS_TOKEN = "EAAZAUKbPY0wgBO6dC79ZBtohCZBx73eaWfWw32qeIg1JQz3KKvZBMjDZBn0rOXtVoSk5uGQ7OP64V2g3DJtBhegIKCo7iT5tsmZBL2v32faqPGQgDSsZBOz0MHHKGZCTTdDUWqQ6lHOgZAG4PjcXZB9TKVBb3LoJ0NWZCLWxgOt26TRPRXDZApvfxqvQnF8H2aEEiXJlzAZCv6hdOo49wTBEWtqZCIEtZBwZDZD"
VERIFY_TOKEN = "Verify_Token_Key"

def send_message(recipient_id, message_text):
    """Send message to user"""
    params = {
        "access_token": PAGE_ACCESS_TOKEN
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    }
    
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", 
                     params=params, headers=headers, json=data)

def send_order_email(message_text: str, sender_id: str):
    """Send order details to outlook email"""
    sender_email = os.environ.get('EMAIL_ADDRESS')
    password = os.environ.get('EMAIL_PASSWORD')

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = sender_email
    msg['Subject'] = f'New Order from Customer {sender_id}'

    # Add timestamp to the order
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    body = f"""
    New order received:
    Time: {current_time}
    Customer ID: {sender_id}
    
    Message Content:
    {message_text}
    """
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.office365.com', 587)
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logging.error(f"Error sending email: {e}")
        return False

@app.route("/")
def index():
    return "Hello World!"

@app.route("/webhook", methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if mode and token:
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return challenge
            else:
                return "403 Forbidden", 403

    if request.method == 'POST':
        data = request.get_json()
        if data["object"] == "page":
            for entry in data["entry"]:
                for messaging_event in entry["messaging"]:
                    if messaging_event.get("message"):
                        sender_id = messaging_event["sender"]["id"]
                        message_text = messaging_event["message"].get("text", "").lower()

                        # Order keywords
                        order_keywords = {'замовити', 'замовлення', 'купити', 'order', 'buy'}
                        
                        # Price keywords
                        price_keywords = {'ціна', 'прайс', 'вартість', 'price', 'cost'}

                        response = ""
                        
                        # Check for order keywords
                        if any(keyword in message_text for keyword in order_keywords):
                            if send_order_email(message_text, sender_id):
                                response = "Дякуємо за замовлення! Ми зв'яжемося з вами найближчим часом."
                            else:
                                response = "Вибачте, виникла помилка при обробці замовлення. Будь ласка, спробуйте пізніше."
                        
                        # Check for price keywords
                        elif any(keyword in message_text for keyword in price_keywords):
                            response = "Ось наш прайс-лист:\n1. Товар A - 100 грн\n2. Товар B - 200 грн"
                        
                        # Default response
                        else:
                            response = "Вітаємо! Чим можемо допомогти? Напишіть 'ціна' для перегляду прайс-листа або 'замовити' для оформлення замовлення."

                        send_message(sender_id, response)

        return "ok", 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)
