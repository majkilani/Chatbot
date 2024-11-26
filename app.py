import os
from flask import Flask, request
import requests
from datetime import datetime
import re
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')
DUMPLING_API_KEY = os.environ.get('DUMPLING_API_KEY')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')

# Store product information
PRODUCTS = {
    "product1": {"name": "Product 1", "price": 100},
    "product2": {"name": "Product 2", "price": 200},
}

# Order storage
orders = []

def get_dumpling_response(user_message):
    """Get response from Dumpling AI API"""
    logger.info(f"Attempting to get Dumpling response for message: {user_message}")
    
    headers = {
        "Authorization": f"Bearer {DUMPLING_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """Ви є помічником з обслуговування клієнтів для Facebook-сторінки магазину. 
    Дотримуйтесь наступних правил:
    1. Відповідайте ТІЛЬКИ українською мовою
    2. Надавайте інформацію про ціни та товари ТІЛЬКИ з останніх оновлених постів сторінки
    3. При оформленні замовлення:
       - Запитуйте кожну деталь по черзі
       - Перевіряйте правильність введених даних
       - Підтверджуйте кожен крок замовлення
    4. Збирайте наступну інформацію для замовлення:
       - Назва та кількість товарів
       - ПІБ замовника
       - Номер телефону (формат: +380XXXXXXXXX)
       - Спосіб доставки (Нова пошта або Укрпошта)
       - Повна адреса доставки з індексом (індекс: 5 цифр)
    5. Для запитів про ціни використовуйте актуальний прайс-лист
    6. Відхиляйте некоректні дані та просіть надати правильний формат"""
    
    payload = {
        "prompt": f"{system_prompt}\n\n{get_latest_price_list()}\n\nПовідомлення користувача: {user_message}",
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(
            "https://dumpling.gumption.ai/completion",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get('text', '')
        else:
            logger.error(f"Dumpling API Error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error calling Dumpling API: {str(e)}")
        return None

def get_perplexity_response(user_message):
    """Get response from Perplexity API"""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """Ви є помічником з обслуговування клієнтів для Facebook-сторінки магазину. 
    Дотримуйтесь наступних правил:
    1. Відповідайте ТІЛЬКИ українською мовою
    2. Надавайте інформацію про ціни та товари ТІЛЬКИ з останніх оновлених постів сторінки
    3. При оформленні замовлення:
       - Запитуйте кожну деталь по черзі
       - Перевіряйте правильність введених даних
       - Підтверджуйте кожен крок замовлення
    4. Збирайте наступну інформацію для замовлення:
       - Назва та кількість товарів
       - ПІБ замовника
       - Номер телефону (формат: +380XXXXXXXXX)
       - Спосіб доставки (Нова пошта або Укрпошта)
       - Повна адреса доставки з індексом (індекс: 5 цифр)
    5. Для запитів про ціни використовуйте актуальний прайс-лист
    6. Відхиляйте некоректні дані та просіть надати правильний формат"""
    
    formatted_message = f"{system_prompt}\n\n{get_latest_price_list()}\n\nПовідомлення користувача: {user_message}"
    
    payload = {
        "model": "mixtral-8x7b-instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": formatted_message}
        ]
    }
    
    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            logger.error(f"Perplexity API Error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error calling Perplexity API: {str(e)}")
        return None

def get_ai_response(user_message):
    """Try multiple AI services in sequence"""
    logger.info("Attempting to get AI response")
    
    # Try Perplexity first
    response = get_perplexity_response(user_message)
    if response:
        logger.info("Successfully got response from Perplexity")
        return response
    
    # If Perplexity fails, try Dumpling
    logger.info("Perplexity failed, trying Dumpling AI")
    response = get_dumpling_response(user_message)
    if response:
        logger.info("Successfully got response from Dumpling")
        return response
    
    # If both fail, return error message
    return "Вибачте, зараз виникли технічні труднощі. Спробуйте, будь ласка, пізніше."

# [Previous functions remain the same: validate_phone_number, validate_postal_code, parse_order_details]

def send_message(recipient_id, message_text):
    """Send message to user"""
    logger.info(f"Sending message to {recipient_id}: {message_text[:100]}...")

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
            "text": message_text[:2000]
        }
    }

    try:
        response = requests.post(
            "https://graph.facebook.com/v18.0/me/messages",
            params=params,
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to send message: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
        return True
            
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return False

@app.route('/', methods=['GET'])
def home():
    return "Bot is running!"

@app.route('/webhook', methods=['GET'])
def verify():
    """Handle webhook verification"""
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return "Hello world", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming messages"""
    data = request.get_json()
    logger.debug(f"Received webhook data: {data}")
    
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    
                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                        logger.info(f"Received message: {message_text}")
                        
                        # Get AI response with fallback
                        ai_response = get_ai_response(message_text)
                        
                        # Process order if applicable
                        if "НОВЕ ЗАМОВЛЕННЯ" in ai_response:
                            order_details = parse_order_details(ai_response)
                            if order_details:
                                if not validate_phone_number(order_details['phone']):
                                    ai_response = "Невірний формат номера телефону. Будь ласка, введіть номер у форматі +380XXXXXXXXX"
                                elif order_details['delivery_method'] not in ['Нова пошта', 'Укрпошта']:
                                    ai_response = "Будь ласка, виберіть спосіб доставки: Нова пошта або Укрпошта"
                                else:
                                    order_details['order_id'] = len(orders) + 1
                                    order_details['timestamp'] = datetime.now().isoformat()
                                    order_details['sender_id'] = sender_id
                                    orders.append(order_details)
                                    ai_response = f"""Замовлення №{order_details['order_id']} прийнято!
Дякуємо за замовлення. Ми зв'яжемося з вами найближчим часом для підтвердження."""
                            else:
                                ai_response = "Виникла помилка при обробці замовлення. Спробуйте ще раз."
                        
                        # Send response
                        send_message(sender_id, ai_response)

    return "ok", 200

@app.route('/orders', methods=['GET'])
def get_orders():
    """Admin endpoint to view orders"""
    return {"orders": orders}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
