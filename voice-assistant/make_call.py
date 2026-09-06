"""
Places a real outbound phone call via Vonage's Voice API, using Vonage's own
built-in text-to-speech to speak an Arabic greeting into the call, then
listens for the customer's spoken response (handled by server.py).

Usage (CLI):
    python make_call.py [to_number]

Also importable: place_call(to_number) is reused by app.py's UI.
"""

import os

from dotenv import load_dotenv
from vonage import Auth, Vonage
from vonage_voice import CreateCallRequest, Phone, ToPhone

from crm import build_greeting

load_dotenv()

APPLICATION_ID = os.environ["VONAGE_APPLICATION_ID"]
# Absolute path, anchored to this file's own folder -- so this still works
# correctly even when imported from a different project's process (e.g. the
# chatbot app), where the current working directory isn't voice-assistant/.
PRIVATE_KEY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.environ["VONAGE_PRIVATE_KEY_PATH"],
)

FROM_NUMBER = os.environ["FROM_NUMBER"]
DEFAULT_TO_NUMBER = os.environ["TO_NUMBER"]

# Permanent ngrok static domain (free tier, one per account) -- server.py
# must be running on port 5000 with ngrok pointed at it:
#   ngrok.exe http --url=<your-static-domain> 5000
# Unlike a plain quick tunnel, this URL does not change between restarts.
PUBLIC_URL = os.environ["PUBLIC_URL"]

def place_call(to_number=None):
    to_number = to_number or DEFAULT_TO_NUMBER
    greeting = build_greeting(to_number)

    client = Vonage(
        Auth(
            application_id=APPLICATION_ID,
            private_key=PRIVATE_KEY_PATH,
        )
    )

    response = client.voice.create_call(
        CreateCallRequest(
            to=[ToPhone(number=to_number)],
            from_=Phone(number=FROM_NUMBER),
            event_url=[f"{PUBLIC_URL}/event"],
            ncco=[
                {
                    "action": "talk",
                    "text": greeting,
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
    return response


def main():
    import sys

    to_number = sys.argv[1] if len(sys.argv) > 1 else None
    response = place_call(to_number)
    print(response)


if __name__ == "__main__":
    main()
