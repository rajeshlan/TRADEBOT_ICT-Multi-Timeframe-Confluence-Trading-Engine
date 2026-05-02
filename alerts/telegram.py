import requests
import threading

class TelegramAlerter:
    """
    Handles communication with the Telegram Bot API to send market alerts.
    Utilizes threading to prevent network latency from blocking the main engine.
    """
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send(self, message):
        """
        🚀 TELEGRAM NON-BLOCKING FIX
        Spawns a background thread to handle the POST request.
        """
        def _send():
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }

            try:
                # Send the POST request to Telegram with a timeout
                response = requests.post(url, json=payload, timeout=10)
                
                # Internal logging for debugging (optional, can be silenced)
                if response.status_code != 200:
                    print(f"❌ Telegram Failed: {response.status_code} - {response.text}")
                else:
                    print("✅ Telegram message sent")
                    
            except Exception as e:
                # Catch network timeouts or connection issues in the background thread
                print(f"[TELEGRAM ERROR] {e}")

        # Start the thread as a daemon so it doesn't block system exit
        threading.Thread(target=_send, daemon=True).start()