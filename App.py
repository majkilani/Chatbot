import os
from flask import Flask, request
import requests
from datetime import datetime
import re

app = Flask(__name__)

# Configuration
PERPLEXITY_API_KEY = "your_perplexity_api_key"
DUMPLING_API_KEY = "your_dumpling_api_key"
PAGE_ACCESS_TOKEN = "your_page_access_token"

# Store product information (update this with your actual products and prices)
PRODUCTS = {
    "product1": {"name": "Product 1", "price": 100},
    "product2": {"name": "Product 2", "price": 200},
    # Add more products
}

# Order storage
orders = []

def validate_phone_number(phone):
    """Validate Ukrainian phone number"""
    pattern = r'^\+?380\d{9}$'
    return bool(re.match(pattern, phone))

def validate_postal_code(code):
    """Validate Ukrainian postal code"""
    pattern = r'^\d{5}$'
    return bool(re.match(pattern, code))

def get_latest_price_list():
    """Get the latest price list from Facebook posts"""
    # Implement your logic to fetch the latest price list
    return "Актуальний прайс-лист:\n" + "\n".join([
        f"{product['name']}: {product['price']} грн" 
        for product in PRODUCTS.values()
    ])

def parse_order_details(message):
    """Parse order details from message"""
    try:
        lines = message.split('\n')
        order = {
            'products': [],
            'customer_name': '',
            'phone': '',
            'delivery_method': '',
            'address': '',
            'status': 'new'
        }
        
        current_section = ''
        for line in lines:
            if 'Товари:' in line:
                current_section = 'products'
                continue
            elif 'ПІБ:' in line:
                order['customer_name'] = line.split('ПІБ:')[1].strip()
            elif 'Телефон:' in line:
                order['phone'] = line.split('Телефон:')[1].strip()
            elif 'Доставка:' in line:
                order['delivery_method'] = line.split('Доставка:')[1].strip()
            elif 'Адреса:' in line:
                order['address'] = line.split('Адреса:')[1].strip()
            elif current_section == 'products' and line.strip():
                order['products'].append(line.strip())
                
        return order
    except Exception as e:
        print(f"Error parsing order: {e}")
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
    6. Відхиляйте некоректні дані та просіть надати правильний формат

    Формат відповіді для замовлення:
    ================
    НОВЕ ЗАМОВЛЕННЯ
    Товари: [список товарів та кількість]
    ПІБ: [ім'я замовника]
    Телефон: [номер]
    Доставка: [спосіб доставки]
    Адреса: [повна адреса з індексом]
    ================

    Актуальний прайс-лист:
    """ + get_latest_price_list()

    formatted_message = f"Повідомлення користувача: {user_message}"
    
    payload = {
        "model": "mixtral-8x7b-instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": formatted_message}
        ]
    }
    
    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        raise Exception(f"Perplexity API Error: {response.status_code}")

def get_dumpling_response(user_message):
    """Get response from Dumpling AI API"""
    headers = {
        "Authorization": f"Bearer {DUMPLING_API_KEY}",
        "Content-Type": "application/json"
    }
    
    formatted_message = """Ви є помічником з обслуговування клієнтів для Facebook-сторінки магазину. 
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
    6. Відхиляйте некоректні дані та просіть надати правильний формат

    Актуальний прайс-лист:
    """ + get_latest_price_list() + "\n\nПовідомлення користувача: " + user_message
    
    payload = {
        "message": formatted_message,
        "stream": False
    }
    
    response = requests.post(
        "https://api.dumplingai.com/api/v1/chatbot/generate",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        return response.json()['response']
    else:
        raise Exception(f"Dumpling API Error: {response.status_code}")

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
    
    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params,
        headers=headers,
        json=data
    )
    if response.status_code != 200:
        print(f"Failed to send message: {response.status_code}")
        print(response.text)

@app.route('/', methods=['GET'])
def verify():
    """Handle webhook verification"""
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == "your_verify_token":
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return "Hello world", 200

@app.route('/', methods=['POST'])
def webhook():
    """Handle incoming messages"""
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"]["text"]
                    
                    try:
                        # Try Perplexity API first
                        try:
                            response_text = get_perplexity_response(message_text)
                        except Exception as perplexity_error:
                            print(f"Perplexity API error: {perplexity_error}")
                            response_text = get_dumpling_response(message_text)
                        
                        # Handle order processing
                        if "НОВЕ ЗАМОВЛЕННЯ" in response_text:
                            order_details = parse_order_details(response_text)
                            if order_details:
                                # Validate phone number
                                if not validate_phone_number(order_details['phone']):
                                    send_message(sender_id, "Невірний формат номера телефону. Будь ласка, введіть номер у форматі +380XXXXXXXXX")
                                    return "ok", 200
                                
                                # Validate delivery method
                                if order_details['delivery_method'] not in ['Нова пошта', 'Укрпошта']:
                                    send_message(sender_id, "Будь ласка, виберіть спосіб доставки: Нова пошта або Укрпошта")
                                    return "ok", 200
                                
                                # Add order to storage
                                order_details['order_id'] = len(orders) + 1
                                order_details['timestamp'] = datetime.now().isoformat()
                                order_details['sender_id'] = sender_id
                                orders.append(order_details)
                                
                                # Send confirmation
                                confirmation = f"""Замовлення №{order_details['order_id']} прийнято!
Дякуємо за замовлення. Ми зв'яжемося з вами найближчим часом для підтвердження."""
                                send_message(sender_id, confirmation)
                            else:
                                send_message(sender_id, "Виникла помилка при обробці замовлення. Спробуйте ще раз.")
                        else:
                            send_message(sender_id, response_text)
                            
                    except Exception as e:
                        error_message = "Вибачте, сталася помилка. Спробуйте, будь ласка, пізніше."
                        send_message(sender_id, error_message)
                        print(f"Error: {str(e)}")
    return "ok", 200

@app.route('/orders', methods=['GET'])
def get_orders():
    """Admin endpoint to view orders"""
    # Add authentication here
    return {"orders": orders}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
