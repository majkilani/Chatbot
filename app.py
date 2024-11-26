import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "your-email@gmail.com"  # You need to provide your Gmail
SMTP_PASSWORD = "your-app-password"  # You need to generate an App Password
ADMIN_EMAIL = "majid.alkilani@gmail.com"

class OrderState:
    def __init__(self):
        self.step = 'start'
        self.quantity = None
        self.phone = None
        self.delivery_type = None
        self.post_office = None

user_states: Dict[str, OrderState] = {}

def send_admin_notification(order_details: str):
    """Send order notification to admin via email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = ADMIN_EMAIL
        msg['Subject'] = "🥚 Нове замовлення яєць"
        
        msg.attach(MIMEText(order_details, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")
        return False

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

    return "Щось пішло не так. Спробуйте почати замовлення знову."

# Update your webhook function to include order handling
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    
                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"].lower()
                        
                        # Handle price request
                        if any(keyword in message_text for keyword in ['ціна', 'прайс', 'вартість', 'замовити']):
                            response = get_latest_price_list()
                        else:
                            # Handle order flow
                            response = handle_order_flow(sender_id, message_text)
                        
                        send_message(sender_id, response)
                        
    return "ok", 200
