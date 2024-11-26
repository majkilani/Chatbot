import os
from flask import Flask, request
import requests
from dotenv import load_dotenv
import json
import logging
import re
from typing import Dict, Optional

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')

class PriceInfo:
    def __init__(self, price: str, unit: str, quantity: Optional[int] = None):
        self.price = price
        self.unit = unit
        self.quantity = quantity

    def __str__(self):
        quantity_str = f" ({self.quantity} шт)" if self.quantity else ""
        return f"{self.price} грн/{self.unit}{quantity_str}"

@app.route('/', methods=['GET'])
def verify():
    """Handle the initial verification from Facebook"""
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return "Hello world", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming messages"""
    try:
        data = request.get_json()
        print("Raw received data:", data)  # New debug print
        logger.debug(f"Received webhook data: {data}")
        
        if data["object"] == "page":
            for entry in data["entry"]:
                for messaging_event in entry["messaging"]:
                    if messaging_event.get("message"):
                        sender_id = messaging_event["sender"]["id"]
                        logger.debug(f"Sender ID: {sender_id}")
                        print(f"Processing message from sender: {sender_id}")  # New debug print
                        
                        if "text" in messaging_event["message"]:
                            message_text = messaging_event["message"]["text"].lower()
                            logger.debug(f"Received message: {message_text}")
                            print(f"Raw message received: {messaging_event['message']['text']}")  # New debug print
                            
                            # Define price-related keywords
                            price_keywords = {'ціна', 'прайс', 'вартість', 'почем', 'прайс-лист', 'price', 
                                           'скільки коштує', 'почому', 'по чому', 'коштує'}
                            
                            # Check if any price keyword is in the message
                            if any(keyword in message_text for keyword in price_keywords):
                                response = get_latest_price_list()
                                if not response or "Не вдалося отримати" in response:
                                    # Fallback price if can't get from Facebook
                                    response = ("🏷️ Актуальний прайс:\n\n"
                                              "🥚 Яйця - 50-55 грн/лоток (20 шт)\n\n"
                                              "📞 Для замовлення:\n"
                                              "Телефон/Viber: 0953314400")
                            else:
                                response = get_perplexity_response(message_text)
                            
                            print(f"Preparing to send response: {response}")  # New debug print
                            logger.debug(f"Response to send: {response}")
                            
                            if send_message(sender_id, response):
                                logger.debug("Message sent successfully")
                                print("Message sent successfully")  # New debug print
                            else:
                                logger.error("Failed to send message")
                                print("Failed to send message")  # New debug print
        
        return "ok", 200
    except Exception as e:
        print(f"Error in webhook: {str(e)}")  # New debug print
        logger.error(f"Error in webhook: {e}")
        return str(e), 500

def get_perplexity_response(message: str) -> str:
    """Get response from Perplexity AI"""
    try:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "mistral-7b-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant for a Ukrainian egg farm."
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            logger.error(f"Perplexity API error: {response.status_code}")
            return "Вибачте, але я не можу зараз відповісти на ваше запитання."
            
    except Exception as e:
        logger.error(f"Error getting Perplexity response: {e}")
        return "Вибачте, але я не можу зараз відповісти на ваше запитання."

def parse_price_from_standardized_post(message: str) -> Dict[str, PriceInfo]:
    """Parse price information from standardized posts"""
    price_info = {}
    
    # Regular expressions for price parsing
    price_pattern = r'💸\s*Ціна:\s*(\d+(?:-\d+)?)\s*грн\/(\w+)(?:\s* $(\d+)\s*шт$ )?'
    product_name_pattern = r'^([🥚🐔\w\s]+)'
    
    try:
        # Find the price information
        price_match = re.search(price_pattern, message, re.MULTILINE)
        if price_match:
            price = price_match.group(1)
            unit = price_match.group(2)
            quantity = int(price_match.group(3)) if price_match.group(3) else None
            
            # Find the product name from the first line
            first_line = message.split('\n')[0]
            product_match = re.search(product_name_pattern, first_line)
            if product_match:
                product_name = product_match.group(1).strip()
                price_info[product_name] = PriceInfo(price, unit, quantity)
    
    except Exception as e:
        logger.error(f"Error parsing price from post: {e}")
    
    return price_info

def get_latest_price_list():
    """Get the latest price list from Facebook posts"""
    try:
        url = f"https://graph.facebook.com/v18.0/me/posts"
        params = {
            "access_token": PAGE_ACCESS_TOKEN,
            "fields": "message,created_time",
            "limit": 10
        }
        
        response = requests.get(url, params=params)
        if response.status_code != 200:
            logger.error(f"Failed to fetch posts: {response.status_code}")
            return "Не вдалося отримати актуальний прайс-лист"
        
        posts = response.json().get('data', [])
        all_prices = {}
        
        for post in posts:
            message = post.get('message', '')
            if '💸 Ціна:' in message:
                prices = parse_price_from_standardized_post(message)
                all_prices.update(prices)
        
        # Format the price list
        if all_prices:
            price_list = "🏷️ Актуальний прайс-лист:\n\n"
            for product, price_info in all_prices.items():
                price_list += f"{product}: {str(price_info)}\n"
            return price_list
        else:
            return ("🏷️ Актуальний прайс:\n\n"
                   "🥚 Яйця - 50-55 грн/лоток (20 шт)\n\n"
                   "📞 Для замовлення:\n"
                   "Телефон/Viber: 0953314400")
            
    except Exception as e:
        logger.error(f"Error getting price list from Facebook: {e}")
        return "Не вдалося отримати актуальний прайс-лист"

def send_message(recipient_id: str, message_text: str) -> bool:
    """Send message to user via Facebook Messenger"""
    try:
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
            data=json.dumps(data)
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to send message: {response.status_code}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False

if __name__ == "__main__":
    app.run(debug=True)
