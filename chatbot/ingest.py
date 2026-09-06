"""
Step 1 of the pipeline: read documents from an organization's own data
folder, split them into chunks, embed them, and store them in the shared
Chroma vector database -- tagged with organization_id so retrieval can be
scoped to just that organization's documents.

Run this again any time an organization's documents change.
"""

import os
import glob
import hashlib

import chromadb
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from docx import Document as DocxDocument

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(_HERE, "data")
DB_DIR = os.path.join(_HERE, "chroma_db")
COLLECTION_NAME = "kb_docs"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"  # free, local, multilingual (Arabic included)
CHUNK_SIZE = 800   # characters per chunk
CHUNK_OVERLAP = 150  # characters shared between consecutive chunks


def get_org_data_dir(organization_id):
    """Each organization's documents live in their own subfolder, so
    uploads/rebuilds for one org never touch another org's files on disk."""
    path = os.path.join(DATA_ROOT, str(organization_id))
    os.makedirs(path, exist_ok=True)
    return path


def read_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_pdf(path):
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def read_docx(path):
    doc = DocxDocument(path)
    return "\n".join(p.text for p in doc.paragraphs)


def hash_text(text):
    """Content fingerprint -- used to detect the exact same document being
    ingested twice within the same organization, even under a different
    filename."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


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


def run_ingestion(organization_id, model=None, progress_callback=None):
    """
    Rebuilds this ONE organization's slice of the vector database from
    every document in their data folder. Other organizations' chunks in
    the same shared collection are never touched.

    Reuses a pre-loaded embedding model if given (e.g. from a Streamlit page
    that already has one in memory), otherwise loads its own.
    progress_callback(message) is called with a status string for each step,
    if provided -- lets a UI show live progress instead of only terminal prints.
    Returns {"file_count": int, "chunk_count": int, "files": [(filename, n_chunks), ...]}.
    """
    def report(msg):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    data_dir = get_org_data_dir(organization_id)
    files = [
        p for p in glob.glob(os.path.join(data_dir, "*"))
        if os.path.splitext(p)[1].lower() in (".txt", ".pdf", ".docx")
    ]

    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    # Remove only this organization's existing chunks before re-adding --
    # never delete the whole collection, since other orgs share it.
    existing = collection.get(where={"organization_id": organization_id})
    if existing and existing.get("ids"):
        collection.delete(ids=existing["ids"])
        report(f"Removed {len(existing['ids'])} old chunk(s) for this organization.")

    if not files:
        report(f"No documents found in {data_dir}/. Add .txt, .pdf, or .docx files there.")
        return {"file_count": 0, "chunk_count": 0, "files": []}

    if model is None:
        report(f"Loading embedding model ({EMBEDDING_MODEL})...")
        model = SentenceTransformer(EMBEDDING_MODEL)

    all_chunks = []
    all_ids = []
    all_metadatas = []
    file_summary = []

    for path in files:
        filename = os.path.basename(path)
        text = load_document(path)
        doc_hash = hash_text(text)
        chunks = recursive_chunk(text)
        report(f"  {filename}: {len(chunks)} chunk(s)")
        file_summary.append((filename, len(chunks)))
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_ids.append(f"org{organization_id}::{filename}::{i}")
            all_metadatas.append({
                "source": filename,
                "chunk_index": i,
                "doc_hash": doc_hash,
                "organization_id": organization_id,
            })

    if not all_chunks:
        return {"file_count": len(files), "chunk_count": 0, "files": file_summary}

    report(f"Embedding {len(all_chunks)} chunk(s)...")
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

    report(f"Done. Stored {len(all_chunks)} chunks for this organization in {DB_DIR}/ (collection '{COLLECTION_NAME}').")
    return {"file_count": len(files), "chunk_count": len(all_chunks), "files": file_summary}


def ingest_single_file(path, organization_id, model=None, progress_callback=None):
    """
    Adds just one document to this organization's slice of the vector DB,
    without touching any other file -- this organization's or any other's.

    Duplicate detection is by content hash, scoped to this organization: if
    the exact same document is already in THIS org's knowledge base (even
    saved under a different filename), this skips it entirely rather than
    embedding it again. Two different organizations may legitimately have
    identical documents without conflict. If a DIFFERENT document happens
    to reuse the same filename as one already ingested for this org, the
    old chunks for that filename (within this org only) are replaced.

    Returns the same shape as run_ingestion(), for this one file, plus
    "skipped": True when nothing was added because it was already there.
    """
    def report(msg):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    if model is None:
        report(f"Loading embedding model ({EMBEDDING_MODEL})...")
        model = SentenceTransformer(EMBEDDING_MODEL)

    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    filename = os.path.basename(path)
    text = load_document(path)
    doc_hash = hash_text(text)

    # Same content already ingested for THIS org -> skip entirely.
    existing_by_hash = collection.get(where={"$and": [
        {"doc_hash": doc_hash},
        {"organization_id": organization_id},
    ]})
    if existing_by_hash and existing_by_hash.get("ids"):
        existing_source = filename
        if existing_by_hash.get("metadatas"):
            existing_source = existing_by_hash["metadatas"][0].get("source", filename)
        report(f"This exact document is already in this organization's knowledge base (as '{existing_source}') — skipping, nothing duplicated.")
        return {"file_count": 0, "chunk_count": 0, "files": [], "skipped": True, "existing_as": existing_source}

    # Different content reusing an old filename within THIS org -> replace just those chunks.
    existing_by_name = collection.get(where={"$and": [
        {"source": filename},
        {"organization_id": organization_id},
    ]})
    if existing_by_name and existing_by_name.get("ids"):
        collection.delete(ids=existing_by_name["ids"])
        report(f"Replaced old version of {filename} ({len(existing_by_name['ids'])} old chunk(s) removed).")

    chunks = recursive_chunk(text)
    report(f"{filename}: {len(chunks)} chunk(s)")

    if not chunks:
        return {"file_count": 1, "chunk_count": 0, "files": [(filename, 0)], "skipped": False}

    ids = [f"org{organization_id}::{filename}::{i}" for i in range(len(chunks))]
    metadatas = [
        {"source": filename, "chunk_index": i, "doc_hash": doc_hash, "organization_id": organization_id}
        for i in range(len(chunks))
    ]

    report(f"Embedding {len(chunks)} chunk(s)...")
    embeddings = model.encode(
        [f"passage: {c}" for c in chunks],
        show_progress_bar=True,
    ).tolist()

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    report(f"Done. Added {len(chunks)} chunk(s) for {filename} (other documents untouched).")
    return {"file_count": 1, "chunk_count": len(chunks), "files": [(filename, len(chunks))], "skipped": False}


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <organization_id>")
        return
    run_ingestion(int(sys.argv[1]))


if __name__ == "__main__":
    main()
