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
        print("Raw received data:", data)
        logger.debug(f"Received webhook data: {data}")
        
        if data["object"] == "page":
            for entry in data["entry"]:
                for messaging_event in entry["messaging"]:
                    if messaging_event.get("message"):
                        sender_id = messaging_event["sender"]["id"]
                        logger.debug(f"Sender ID: {sender_id}")
                        print(f"Processing message from sender: {sender_id}")
                        
                        if "text" in messaging_event["message"]:
                            message_text = messaging_event["message"]["text"].lower()
                            logger.debug(f"Received message: {message_text}")
                            print(f"Raw message received: {messaging_event['message']['text']}")
                            
                            # Expanded multilingual price keywords
                            price_keywords = {
                                # Ukrainian
                                'ціна', 'прайс', 'вартість', 'почем', 'прайс-лист', 'скільки коштує', 
                                'почому', 'по чому', 'коштує', 'ціни', 'прайслист', 'вартiсть',
                                # English
                                'price', 'cost', 'how much', 'pricing', 'price list', 'pricelist', 
                                'prices', 'costs', 'rate', 'charge', 'fee', 'amount',
                                # Russian
                                'цена', 'стоимость', 'прайс', 'сколько стоит', 'цены', 'стоимость', 
                                'прайс-лист', 'прайслист', 'почем', 'по чем',
                                # Polish
                                'cena', 'koszt', 'ile kosztuje', 'cennik', 'ceny', 'koszty', 
                                'ile kosztują', 'po ile',
                                # German
                                'preis', 'kosten', 'wie viel kostet', 'preisliste', 'preise', 
                                'wie viel', 'wieviel kostet',
                                # French
                                'prix', 'coût', 'combien ça coûte', 'tarif', 'tarifs', 'liste des prix',
                                'combien coûte', 'coûts',
                                # Spanish
                                'precio', 'cuánto cuesta', 'cuanto', 'lista de precios', 'precios', 
                                'cuánto vale', 'tarifa',
                                # Italian
                                'prezzo', 'quanto costa', 'listino prezzi', 'prezzi', 'costo', 
                                'quanto viene',
                                # Romanian
                                'preț', 'cât costă', 'lista de prețuri', 'prețuri', 'cost', 'tarif'
                            }
                            
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
                            
                            print(f"Preparing to send response: {response}")
                            logger.debug(f"Response to send: {response}")
                            
                            if send_message(sender_id, response):
                                logger.debug("Message sent successfully")
                                print("Message sent successfully")
                            else:
                                logger.error("Failed to send message")
                                print("Failed to send message")
        
        return "ok", 200
    except Exception as e:
        print(f"Error in webhook: {str(e)}")
        logger.error(f"Error in webhook: {e}")
        return str(e), 500

[Rest of the code remains exactly the same...]
