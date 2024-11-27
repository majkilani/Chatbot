import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import Flask, request, jsonify
import requests
import logging

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "default_key_if_not_set")

class OrderState:
    def __init__(self):
        self.step = 'start'
        self.quantity = None
        self.phone = None
        self.delivery_type = None
        self.post_office = None

user_states = {}

def send_message(sender_id, message):
    """Send a response back to the user"""
    # Implement your function to send the message. Example using the API:
    response_url = f"https://graph.facebook.com/v13.0/me/messages?access_token={os.getenv('PAGE_ACCESS_TOKEN')}"
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }
    try:
        response = requests.post(response_url, json=payload)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Error while sending message to user: {e}")

def send_admin_notification(order_details: str):
    """Send order notification to admin via email"""
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
        return True
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")
        return False

def get_ai_response(prompt):
    """Call Perplexity AI API for a response"""
    url = 'the_perplexity_api_endpoint'  # Replace with actual API endpoint
    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}'
    }
    data = {
        "input": {
            "text": prompt
        }
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)  # Set timeout to ensure quick response
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return response.json()['response']['text']
    except requests.RequestException as e:
        logger.error(f"Perplexity AI API request failed: {e}")
        return "There seems to be an issue with the AI service. Please try again later."

def handle_order_flow(sender_id: str, message_text: str) -> str:
    """Handle the ordering process flow"""
    if sender_id not in user_states:
        user_states[sender_id] = OrderState()
    
    state = user_states[sender_id]
    message_text = message_text.strip().lower()

    if state.step == 'start':
        state.step = 'quantity'
        return ("Дякуємо за ваше замовлення! 🥚\n\n"
                "Скільки лотків яєць ви бажаєте замовити?\n"
                "(1 лоток = 20 шт)")
    elif state.step == 'quantity':
        try:
            quantity = int(message_text)
            if quantity <= 0:
                return "Будь ласка, введіть правильну кількість лотків (більше 0)"
            state.quantity = quantity
            state.step = 'phone'
            return ("Введіть, будь ласка, ваш номер телефону у форматі:\n"
                   "0971234567")
        except ValueError:
            return "Будь ласка, введіть число (кількість лотків)"
    elif state.step == 'phone':
        if re.match(r'^(?:\+?38)?0\d{9}$', message_text.replace(' ', '')):
            state.phone = message_text
            state.step = 'delivery'
            return ("Оберіть спосіб доставки:\n\n"
                   "1 - Нова Пошта\n"
                   "2 - Укрпошта")
        else:
            return "Будь ласка, введіть правильний номер телефону (наприклад: 0971234567)"
    elif state.step == 'delivery':
        if message_text == '1':
            state.delivery_type = 'Нова Пошта'
        elif message_text == '2':
            state.delivery_type = 'Укрпошта'
        else:
            return "Будь ласка, виберіть 1 (Нова Пошта) або 2 (Укрпошта)"
        
        state.step = 'post_office'
        return f"Введіть номер відділення {state.delivery_type}:"
    elif state.step == 'post_office':
        state.post_office = message_text
        
        # Create order details for admin
        order_details = (
            "🥚 НОВЕ ЗАМОВЛЕННЯ!\n\n"
            f"Кількість лотків: {state.quantity} (по 20 шт)\n"
            f"Телефон: {state.phone}\n"
            f"Доставка: {state.delivery_type}\n"
            f"Відділення: {state.post_office}\n"
            f"ID користувача: {sender_id}\n"
            f"Час замовлення: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Send notification to admin
        if send_admin_notification(order_details):
            logger.info("Admin notification sent successfully")
        else:
            logger.error("Failed to send admin notification")

        # Response to customer
        customer_response = (
            "🥚 Ваше замовлення:\n\n"
            f"Кількість лотків: {state.quantity} (по 20 шт)\n"
            f"Телефон: {state.phone}\n"
            f"Доставка: {state.delivery_type}\n"
            f"Відділення: {state.post_office}\n\n"
            "Ми зв'яжемося з вами найближчим часом для підтвердження замовлення!\n"
            "Дякуємо, що обрали нас! 🙏"
        )
        
        # Reset the state
        del user_states[sender_id]
        return customer_response
    else:
        return "Щось пішло не так. Спробуйте почати замовлення знову."

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Webhook Verification"""
    hub_mode = request.args.get('hub.mode')
    hub_verify_token = request.args.get('hub.verify_token')
    if hub_mode == 'subscribe' and hub_verify_token == os.getenv('VERIFY_TOKEN'):
        return request.args.get('hub.challenge'), 200
    else:
        return 'Verification Token Mismatch', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """Process incoming messages"""
    data = request.json
    try:
        messaging_events = data['entry'][0]['messaging']
        for event in messaging_events:
            if event.get('message'):
                sender_id = event['sender']['id']
                user_input = event['message'].get('text')
                # Process message
                if user_input and user_input.lower() in ['добрий день', 'hello']:
                    bot_response = get_ai_response(user_input)
                    send_message(sender_id, bot_response)
                else:
                    # Handle order flow
                    response = handle_order_flow(sender_id, user_input)
                    send_message(sender_id, response)
        return "EVENT_RECEIVED", 200
    except KeyError:
        logger.error("Key Error in incoming data")
        return "Invalid input request.", 400
    except Exception as e:
        logger.error(f"Webhooking processing error: {e}")
        return "Processing error", 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', '5000'))  # Render dynamically sets ports
    app.run(host='0.0.0.0', port=port)
