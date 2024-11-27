from flask import Flask, Response, request, jsonify
import requests
import json
import os
import logging
import sys

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='app.log')

# API keys
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")

if not PERPLEXITY_API_KEY:
    logging.error("Perplexity AI API key not set. Please set the PERPLEXITY_API_KEY environment variable.")
    sys.exit(1)

class PerplexityClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def chat_completions(self, messages):
        endpoint = "https://api.copyrighted.io/v1/chat/completions"  # Ensure this is the correct endpoint
        payload = {
            "model": "llama-3.1-sonar-large-128k-online",
            "messages": messages
        }
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Request Error: {e}")
            raise
        except Exception as e:
            logging.exception(f"Unexpected error in Perplexity AI API call", exc_info=True)
            raise

@app.route('/')
def health_check():
    return jsonify(status="Healthy", environment_variable=bool(os.environ.get("PERPLEXITY_API_KEY"))), 200

@app.route('/message', methods=['POST'])
def send_perplex_response():
    data = request.json
    user_id = data.get('user_id')
    query = data.get('message')

    if not user_id or not query:
        return Response(json.dumps({"error": "Invalid request. Please provide both user_id and message."}),
                        status=400, mimetype='application/json')

    client = PerplexityClient(PERPLEXITY_API_KEY)
    if not client.api_key:
        return Response(json.dumps("Perplexity AI API client not initialized. Please check your environment variables."),
                        content_type="application/json", status=500)

    messages = [
        {
            "role": "system",
            "content": "You are an AI chat assistant conversing with a user about their questions or comments.",
        },
        {
            "role": "user",
            "content": query,
        },
    ]
    
    try:
        response = client.chat_completions(messages)
        if response.get('choices') and len(response['choices']):
            answer = response['choices'][0].get('message', {}).get('content')
            response_data = {'response': answer}
            return jsonify(response_data), 200
        else:
            return Response(json.dumps({"error": "No response from Perplexity AI."}),
                            content_type="application/json", status=500)
    except Exception as e:
        # Log the detailed exception information
        logging.exception("Exception in Perplexity AI API call", exc_info=True)
        return Response(json.dumps({"error": f"Sorry, something went wrong. Please try again."}),
                        content_type="application/json", status=500)

@app.route('/webhook', methods=['POST'])
def webhook():
    # Handle the webhook verification or the message from a service like Meta (formerly known as Facebook)
    data = request.get_json(silent=True, force=True)
    if data and data.get("hub.mode") == "subscribe" and data.get("hub.verify_token") == "your_verification_token":
        # Return the challenge for verification
        return str(data.get("hub.challenge")), 200
    
    logging.info(f"Webhook received: {json.dumps(data)}")
    # Here you would process the actual webhook payload or return success based on your application needs
    return jsonify({"status": "success"}), 200

@app.errorhandler(404)
def not_found(error):
    return Response(json.dumps({"error": "Not found"}),
                    status=404, content_type='application/json')

@app.errorhandler(500)
def internal_server_error(error):
    return Response(json.dumps({"error": "An internal server error occurred"}),
                    status=500, content_type='application/json')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"Starting Flask service on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)

        payload = {
            "model": "llama-3.1-sonar-large-128k-online",
            "messages": messages
        }
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Request Error: {e}")
            raise

@app.route('/')
def health_check():
    return jsonify(status="Healthy", environment_variable=bool(os.environ.get("PERPLEXITY_API_KEY"))), 200

@app.route('/message', methods=['POST'])
def send_perplex_response():
    data = request.json
    user_id = data.get('user_id')
    query = data.get('message')

    if not user_id or not query:
        return Response(json.dumps({"error": "Invalid request. Please provide both user_id and message."}),
                        status=400, mimetype='application/json')

    client = PerplexityClient(PERPLEXITY_API_KEY)

    if not client.api_key:
        return Response(json.dumps("Perplexity AI API client not initialized. Please check your environment variables."),
                        content_type="application/json", status=500)

    messages = [
        {
            "role": "system",
            "content": "You are an AI chat assistant conversing with a user about their questions or comments.",
        },
        {
            "role": "user",
            "content": query,
        },
    ]

    try:
        response = client.chat_completions(messages)
        if response.get('choices') and len(response['choices']):
            answer = response['choices'][0].get('message', {}).get('content')
            response_data = {'response': answer}
            return jsonify(response_data), 200
        else:
            return Response(json.dumps({"error": "No response from Perplexity AI."}),
                            content_type="application/json", status=500)
    except Exception as e:
        logging.exception("Exception in Perplexity AI API call")
        return Response(json.dumps({"error": "Sorry, something went wrong. Please try again."}),
                        content_type="application/json", status=500)

@app.errorhandler(404)
def not_found(error):
    return Response(json.dumps({"error": "Not found"}),
                    status=404, content_type='application/json')

@app.errorhandler(500)
def internal_server_error(error):
    return Response(json.dumps({"error": "An internal server error occurred"}),
                    status=500, content_type='application/json')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"Starting Flask service on port {port}...")
    print(f"API Key: {'*' * len(PERPLEXITY_API_KEY) if PERPLEXITY_API_KEY else 'API Key not found'}")
    
    if PERPLEXITY_API_KEY:
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("Starting server with warnings: Perplexity AI API client not initialized. Some endpoints might not work correctly.")
        app.run(host='0.0.0.0', port=port, debug=False)
