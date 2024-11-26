# Add these imports at the top with the existing ones
from email.mime.text import MIMEText
import smtplib

# Add these environment variables after the existing ones
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Add this new function after your existing functions
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

# Modify your webhook route to include email notifications
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
                        
                        # Define price-related keywords
                        price_keywords = {'ціна', 'прайс', 'вартість', 'почем', 'прайс-лист', 'price', 
                                       'скільки коштує', 'почому', 'по чому', 'коштує'}
                        
                        # Check if message contains order-related keywords
                        order_keywords = {'замовити', 'замовлення', 'купити', 'order', 'buy'}
                        
                        if any(keyword in message_text for keyword in order_keywords):
                            # Send email notification for orders
                            email_subject = "Нове замовлення"
                            email_body = f"Отримано нове замовлення через Facebook Messenger.\nID користувача: {sender_id}\nПовідомлення: {message_text}"
                            send_email(email_subject, email_body)
                        
                        # Check if any price keyword is in the message
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
