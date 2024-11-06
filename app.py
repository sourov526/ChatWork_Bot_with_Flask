import os
from flask import Flask, request, jsonify
import requests
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Constants
CHATWORK_TOKEN = os.getenv("CHATWORK_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Utility to log debug information
def log_debug(message, data=None):
    print(f"DEBUG: {message}")
    if data:
        print(data)

# Function to generate response from OpenAI API
def generate_openai_response(message):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": message}]
        )
        return response.choices[0].message['content']
    except Exception as e:
        log_debug("Failed to fetch response from OpenAI", e)
        return "An error occurred with OpenAI."

# Function to get username from Chatwork by account ID
def get_username(account_id):
    try:
        headers = {"X-ChatWorkToken": CHATWORK_TOKEN}
        response = requests.get("https://api.chatwork.com/v2/contacts", headers=headers)
        response.raise_for_status()
        users = response.json()
        log_debug("Fetched user list from Chatwork", users)
        for user in users:
            if user["account_id"] == account_id:
                return user["name"]
        return "Unknown User"
    except requests.RequestException as e:
        log_debug("Failed to fetch username from Chatwork", e)
        return "Unknown User"

# Function to send message to a Chatwork room
def send_chatwork_message(text, chatwork_room_id):
    url = f'https://api.chatwork.com/v2/rooms/{chatwork_room_id}/messages'
    headers = {"X-ChatWorkToken": CHATWORK_TOKEN}
    payload = {"body": text}
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        log_debug("Message sent to Chatwork", {"room_id": chatwork_room_id, "message": text})
        return response.json()
    except requests.RequestException as e:
        log_debug("Failed to send message to Chatwork", e)
        return None

# Flask route to handle webhook events from Chatwork
@app.route("/chatwork", methods=["POST"])
def webhook():
    payload = request.json
    log_debug("Received webhook payload", payload)

    # Check if payload is valid and contains required fields
    try:
        user_message = payload["webhook_event"]["body"][12:]
        log_debug("Extracted user message", user_message)

        if payload["webhook_event_type"] == "mention_to_me":
            openai_response = generate_openai_response(user_message)
            log_debug("Generated OpenAI response", openai_response)

            username = get_username(payload["webhook_event"]["from_account_id"])
            log_debug("Fetched username", username)

            chatwork_room_id = payload["webhook_event"]["room_id"]
            log_debug("Chatwork room ID", chatwork_room_id)

            response_message = f"[To:{payload['webhook_event']['from_account_id']}] {username}\n{openai_response}"
            send_chatwork_message(response_message, chatwork_room_id)
            return jsonify({"status": "success"}), 200

        else:
            log_debug("Unhandled webhook event type", payload["webhook_event_type"])
            return jsonify({"status": "ignored", "message": "Event type not handled"}), 200

    except KeyError as e:
        log_debug("Missing key in payload", e)
        return jsonify({"status": "error", "message": "Invalid payload format"}), 400
    except Exception as e:
        log_debug("Unexpected error processing webhook", e)
        return jsonify({"status": "error", "message": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(debug=True)
