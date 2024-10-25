

import requests

api_key = "YOUR_IBM_WATSON_API_KEY"
url = "(link unavailable)"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}
data = {
    "text": "Hello, world!",
    "model_id": "en-es",
    "source": "en",
    "target": "es"
}

response = requests.post(url, headers=headers, json=data)
print(response.json())


Sign up for IBM Watson:

(link unavailable)

IBM Watson Language Translator Documentation:

(link unavailable)

Replace YOUR_IBM_WATSON_API_KEY, YOUR_IBM_WATSON_USERNAME, and YOUR_IBM_WATSON_PASSWORD with your actual API credentials.

Let me know if you need further assistance!