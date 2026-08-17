"""
Transcribes recording.wav into Arabic text using Whisper (via faster-whisper),
run locally — no API key, no internet needed once the model is downloaded.

Usage:
    python transcribe.py
"""

from faster_whisper import WhisperModel

AUDIO_FILE = "recording.wav"
MODEL_SIZE = "small"  # good balance of accuracy vs. speed/size for Arabic on CPU


def transcribe(audio_path=AUDIO_FILE):
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, language="ar")
    text = " ".join(segment.text.strip() for segment in segments)
    return text


def main():
    print("Loading Whisper model (first run downloads it, ~500MB)...")
    text = transcribe()
    print("Transcribed text:")
    print(text)


if __name__ == "__main__":
    main()
