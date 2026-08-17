"""
Records a few seconds of audio from your microphone and saves it as
recording.wav — the raw input for the speech-to-text step (transcribe.py).

Usage:
    python record.py [seconds]   (defaults to 5 seconds)
"""

import sys

import sounddevice as sd
from scipy.io.wavfile import write

SAMPLE_RATE = 16000  # Whisper expects 16kHz audio
OUTPUT_FILE = "recording.wav"


def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    print(f"Recording for {seconds} seconds... speak now.")
    audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()

    write(OUTPUT_FILE, SAMPLE_RATE, audio)
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
