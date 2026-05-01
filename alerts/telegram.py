import requests

class TelegramAlerter:
    """
    Handles communication with the Telegram Bot API to send market alerts.
    """
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send(self, message):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        try:
            # Send the POST request to Telegram
            response = requests.post(url, json=payload, timeout=10)
            
            # Check if the request was successful (Status 200)
            if response.status_code == 200:
                print("✅ Telegram message sent")
            else:
                print(f"❌ Telegram Failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            # Catch network timeouts or connection issues
            print(f"[Telegram Error] {e}")