"""
Voice utilities for the RAG chatbot.

STT:
    Audio file -> Arabic text using faster-whisper.

RAG:
    Audio -> transcription -> retrieve relevant documents -> LLM answer.

TTS:
    Arabic text -> MP3 audio using gTTS.
"""

from pathlib import Path

from faster_whisper import WhisperModel
from gtts import gTTS

from query import (
    retrieve,
    build_context,
    ask_llm,
)


WHISPER_MODEL_SIZE = "small"
DEFAULT_LANGUAGE = "ar"

_whisper_model = None


def get_whisper_model():
    """Load Whisper once and reuse it."""
    global _whisper_model

    if _whisper_model is None:
        _whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="int8",
        )

    return _whisper_model


def transcribe_audio(audio_path):
    """
    Convert an audio file into Arabic text.
    """
    model = get_whisper_model()

    segments, _ = model.transcribe(
        str(audio_path),
        language=DEFAULT_LANGUAGE,
    )

    text = " ".join(
        segment.text.strip()
        for segment in segments
    )

    return text.strip()


def text_to_speech(text, output_path):
    """
    Convert Arabic text into an MP3 file.
    """
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tts = gTTS(
        text=text,
        lang=DEFAULT_LANGUAGE,
    )

    tts.save(str(output_path))

    return output_path


def voice_rag_answer(
    audio_path,
    collection,
    embed_model,
    llm_client,
):
    """
    Full voice-to-RAG pipeline:

    Audio
      -> STT
      -> RAG retrieval
      -> LLM answer

    Returns:
        question_text, answer_text, sources
    """

    question_text = transcribe_audio(audio_path)

    if not question_text:
        return "", "عذرًا، لم أتمكن من فهم الصوت.", []

    results = retrieve(
        question_text,
        collection,
        embed_model,
    )

    context = build_context(results)

    answer = ask_llm(
        question_text,
        context,
        llm_client,
    )

    sources = sorted(
        {
            meta["source"]
            for _, meta in results
        }
    )

    return question_text, answer, sources


def voice_rag_to_audio(
    audio_path,
    output_audio_path,
    collection,
    embed_model,
    llm_client,
):
    """
    Full voice conversation pipeline:

    Audio
      -> STT
      -> RAG
      -> LLM
      -> TTS
      -> MP3

    Returns:
        question_text, answer_text, sources, output_audio_path
    """

    question_text, answer, sources = voice_rag_answer(
        audio_path,
        collection,
        embed_model,
        llm_client,
    )

    text_to_speech(
        answer,
        output_audio_path,
    )

    return (
        question_text,
        answer,
        sources,
        output_audio_path,
    )
