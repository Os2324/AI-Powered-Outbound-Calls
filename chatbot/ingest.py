"""
Step 1 of the pipeline: read documents from data/, split them into chunks,
turn each chunk into an embedding (a list of numbers representing its meaning),
and store them in a local Chroma vector database (./chroma_db).

Run this again any time you add/change documents in data/.
"""

import os
import glob

import chromadb
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from docx import Document as DocxDocument

DATA_DIR = "data"
DB_DIR = "chroma_db"
COLLECTION_NAME = "kb_docs"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"  # free, local, multilingual (Arabic included)
CHUNK_SIZE = 800   # characters per chunk
CHUNK_OVERLAP = 150  # characters shared between consecutive chunks


def read_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_pdf(path):
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def read_docx(path):
    doc = DocxDocument(path)
    return "\n".join(p.text for p in doc.paragraphs)


def load_document(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        return read_txt(path)
    if ext == ".pdf":
        return read_pdf(path)
    if ext == ".docx":
        return read_docx(path)
    raise ValueError(f"Unsupported file type: {ext}")


# Tried in this order: paragraph breaks, then line breaks, then sentence
# endings (Arabic and Latin punctuation), before falling back to a hard cut.
SEPARATORS = ["\n\n", "\n", "۔ ", ". ", "؟ ", "? ", "؛ ", "; ", " "]


def _hard_cut(text, chunk_size, overlap):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += chunk_size - overlap
    return chunks


def recursive_chunk(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP, separators=None):
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    separators = SEPARATORS if separators is None else separators
    if not separators:
        return _hard_cut(text, chunk_size, overlap)

    sep, remaining_separators = separators[0], separators[1:]
    parts = text.split(sep)

    chunks = []
    current = ""
    for part in parts:
        candidate = f"{current}{sep}{part}" if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(part) > chunk_size:
                # This single part is still too big even on its own —
                # recurse into it using the next, finer-grained separator.
                chunks.extend(recursive_chunk(part, chunk_size, overlap, remaining_separators))
                current = ""
            else:
                current = part
    if current:
        chunks.append(current)

    return [c.strip() for c in chunks if c.strip()]


def main():
    files = [
        p for p in glob.glob(os.path.join(DATA_DIR, "*"))
        if os.path.splitext(p)[1].lower() in (".txt", ".pdf", ".docx")
    ]
    if not files:
        print(f"No documents found in {DATA_DIR}/. Add .txt, .pdf, or .docx files there.")
        return

    print(f"Found {len(files)} document(s). Loading embedding model ({EMBEDDING_MODEL})...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    client = chromadb.PersistentClient(path=DB_DIR)
    # Start fresh each run so re-ingesting doesn't duplicate old chunks.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME)

    all_chunks = []
    all_ids = []
    all_metadatas = []

    for path in files:
        filename = os.path.basename(path)
        text = load_document(path)
        chunks = recursive_chunk(text)
        print(f"  {filename}: {len(chunks)} chunk(s)")
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_ids.append(f"{filename}::{i}")
            all_metadatas.append({"source": filename, "chunk_index": i})

    print(f"Embedding {len(all_chunks)} chunk(s)...")
    # e5 models expect a "passage: " prefix on the text being stored.
    embeddings = model.encode(
        [f"passage: {c}" for c in all_chunks],
        show_progress_bar=True,
    ).tolist()

    collection.add(
        ids=all_ids,
        embeddings=embeddings,
        documents=all_chunks,
        metadatas=all_metadatas,
    )

    print(f"Done. Stored {len(all_chunks)} chunks in {DB_DIR}/ (collection '{COLLECTION_NAME}').")


if __name__ == "__main__":
    main()
