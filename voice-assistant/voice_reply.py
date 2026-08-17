"""
Full voice-conversation test loop: record your voice -> transcribe (Whisper)
-> get an AI reply (roleplaying the outbound follow-up call scenario from the
original plan) -> speak the reply back (gTTS). Proves the core voice-in/
voice-out loop works before we touch real telephony.

Usage:
    python voice_reply.py [seconds]
"""

import os
import sys

import sounddevice as sd
from scipy.io.wavfile import write
from dotenv import load_dotenv
from openai import OpenAI
from gtts import gTTS

from transcribe import transcribe

load_dotenv()

SAMPLE_RATE = 16000
RECORDING_FILE = "recording.wav"
REPLY_AUDIO_FILE = "reply.mp3"

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-flash-lite-latest")
LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

SYSTEM_PROMPT = """أنت مساعد صوتي آلي تابع لشركة، تجري مكالمة متابعة هاتفية مع عميل بعد
مكالمته السابقة مع خدمة العملاء. مهمتك التأكد من أن العميل قام فعلاً باتباع
الخطوات التي تمت مناقشتها في تلك المكالمة. تحدث بأسلوب طبيعي ومختصر كما لو
كنت تتحدث فعليًا في مكالمة هاتفية، وليس كأنك تكتب رسالة. إذا قال العميل إنه
أتم الخطوات بنجاح، اشكره وأنهِ المكالمة بلطف. إذا قال إنه لم يتمها أو غير متأكد،
اعرض عليه المساعدة أو تحويله لموظف حقيقي."""

GREETING = (
    "صباح الخير، معك نظام المتابعة من الشركة، نتأكد الآن من استكمال "
    "الإجراءات التي ناقشناها في مكالمتك الأخيرة، هل تم تنفيذها؟"
)


def record_audio(seconds=5):
    print(f"Recording for {seconds} seconds... speak now.")
    audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    write(RECORDING_FILE, SAMPLE_RATE, audio)


def get_reply(customer_text, client):
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": GREETING},
            {"role": "user", "content": customer_text},
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content


def speak(text, output_file=REPLY_AUDIO_FILE):
    tts = gTTS(text=text, lang="ar")
    tts.save(output_file)


def main():
    if not LLM_API_KEY:
        print("ERROR: LLM_API_KEY not set in .env")
        return

    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"AI greeting: {GREETING}\n")

    record_audio(seconds)

    print("Transcribing (Whisper)...")
    customer_text = transcribe(RECORDING_FILE)
    print(f"You said: {customer_text}")

    print("Getting AI reply (Gemini)...")
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    reply_text = get_reply(customer_text, client)
    print(f"AI reply: {reply_text}")

    print("Generating speech (gTTS)...")
    speak(reply_text)
    print(f"Saved spoken reply to {REPLY_AUDIO_FILE} — open it to listen.")


if __name__ == "__main__":
    main()
