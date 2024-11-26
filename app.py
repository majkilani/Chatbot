import os
from flask import Flask, request
import requests
from dotenv import load_dotenv
import json
import logging
import re
from typing import Dict, Optional
from email.mime.text import MIMEText
import smtplib

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration variables
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Your existing PriceInfo class
class PriceInfo:
    def __init__(self, price: str, unit: str, quantity: Optional[int] = None):
        self.price = price
        self.unit = unit
        self.quantity = quantity

    def __str__(self):
        quantity_str = f" ({self.quantity} шт)" if self.quantity else ""
        return f"{self.price} грн/{self.unit}{quantity_str}"

# Add email sending function
def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        
        # Connect to Outlook SMTP server
        server = smtplib.SMTP('smtp.office365.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.debug("Email sent successfully")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

# Your existing functions
[Keep all your existing functions here]

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
                    logger.debug(f"Sender ID: {sender_id}")
                    
                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"].lower()
                        logger.debug(f"Received message: {message_text}")
                        
                        # Define keywords
                        price_keywords = {'ціна', 'прайс', 'вартість', 'почем', 'прайс-лист', 'price', 
                                       'скільки коштує', 'почому', 'по чому', 'коштує'}
                        order_keywords = {'замовити', 'замовлення', 'купити', 'order', 'buy'}
                        
                        # Handle order-related messages
                        if any(keyword in message_text for keyword in order_keywords):
                            email_subject = "Нове замовлення"
                            email_body = f"Отримано нове замовлення через Facebook Messenger.\nID користувача: {sender_id}\nПовідомлення: {message_text}"
                            send_email(email_subject, email_body)
                        
                        # Handle price-related messages
                        if any(keyword in message_text for keyword in price_keywords):
                            response = get_latest_price_list()
                            if not response or "Не вдалося отримати" in response:
                                response = ("🏷️ Актуальний прайс:\n\n"
                                          "🥚 Яйця - 50-55 грн/лоток (20 шт)\n\n"
                                          "📞 Для замовлення:\n"
                                          "Телефон/Viber: 0953314400")
                        else:
                            response = get_perplexity_response(message_text)
                        
                        logger.debug(f"Response to send: {response}")
                        
                        if send_message(sender_id, response):
                            logger.debug("Message sent successfully")
                        else:
                            logger.error("Failed to send message")
    
    return "ok", 200

@app.route('/', methods=['GET'])
def verify():
    """Handle the initial verification from Facebook"""
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return "Hello world", 200

if __name__ == "__main__":
    app.run(debug=True)
