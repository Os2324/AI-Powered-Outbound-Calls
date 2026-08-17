"""
Places a real outbound phone call via Vonage's Voice API, using Vonage's own
built-in text-to-speech to speak an Arabic greeting into the call.

Usage:
    python make_call.py
"""

import os

from dotenv import load_dotenv
from vonage import Auth, Vonage
from vonage_voice import CreateCallRequest, Phone, ToPhone

load_dotenv()

APPLICATION_ID = os.environ["VONAGE_APPLICATION_ID"]
PRIVATE_KEY_PATH = os.environ["VONAGE_PRIVATE_KEY_PATH"]

FROM_NUMBER = os.environ["FROM_NUMBER"]
TO_NUMBER = os.environ["TO_NUMBER"]

# Public URL from the cloudflared tunnel (server.py must be running on port 5000
# and cloudflared pointed at it). This changes every time the tunnel restarts,
# so update it here before each test run.
PUBLIC_URL = "https://hdtv-change-sophisticated-regression.trycloudflare.com"

GREETING = (
    "مساء الخير يا افندم، معايا نظام المتابعة الآلي من خدمة العملاء. "
    "كنا اتكلمنا مع حضرتك في مكالمة سابقة واتفقنا على خطوات معينة لحل المشكلة. "
    "حابب أتأكد من حضرتك، هل تم تنفيذ الخطوات دي وانحلت المشكلة، ولا لسه محتاج مساعدة؟"
)


def main():
    client = Vonage(
        Auth(
            application_id=APPLICATION_ID,
            private_key=PRIVATE_KEY_PATH,
        )
    )

    response = client.voice.create_call(
        CreateCallRequest(
            to=[ToPhone(number=TO_NUMBER)],
            from_=Phone(number=FROM_NUMBER),
            ncco=[
                {
                    "action": "talk",
                    "text": GREETING,
                    "language": "ar",
                },
                {
                    "action": "input",
                    "type": ["speech"],
                    "speech": {
                        "language": "ar-EG",
                        "endOnSilence": 1.5,
                    },
                    "eventUrl": [f"{PUBLIC_URL}/speech-response"],
                },
            ],
        )
    )
    print(response)


if __name__ == "__main__":
    main()
