"""
Build ChromaDB vector store from scam knowledge base.

Run after modifying data/scam_cards.json or data/review_cards.json:
    python scripts/build_vectorstore.py

NOTE: risk_rules.json, script_templates.json, eval_dataset.json do NOT
trigger a rebuild — they are loaded directly as JSON at runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CHROMA_COLLECTION,
    CHROMA_DIR,
    DATA_DIR,
    EMBED_MODEL,
    VECTORSTORE_DEPENDENCY_ERROR_MESSAGE,
    VECTORSTORE_FIELD_LABELS,
    VECTORSTORE_SOURCE_FILES,
)


def _load_cards(filepath: Path) -> list[dict]:
    if not filepath.exists():
        print(f"[skip] {filepath.name} not found.")
        return []
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else (data.get("scams") or data.get("cards") or [])


def _text_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _compose_document(card: dict) -> str:
    parts = []
    for field, label in VECTORSTORE_FIELD_LABELS.items():
        values = _text_values(card.get(field))
        if values:
            parts.append(f"{label}：{'；'.join(values)}")
    return "\n".join(parts)


def _metadata_for_card(card: dict, source_file: str) -> dict:
    fraud_type = card.get("fraud_type") or card.get("scam_id") or card.get("id") or ""
    title = card.get("title") or card.get("name") or card.get("id") or ""
    return {
        "fraud_type": str(fraud_type),
        "title": str(title),
        "source_file": source_file,
    }


def _prepare_documents(cards: list[dict], source_file: str) -> tuple[list[str], list[str], list[dict]]:
    ids, documents, metadatas = [], [], []
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue
        document = _compose_document(card)
        if not document:
            continue
        raw_id = str(card.get("id") or card.get("scam_id") or card.get("title") or index)
        ids.append(f"{Path(source_file).stem}_{raw_id}")
        documents.append(document)
        metadatas.append(_metadata_for_card(card, source_file))
    return ids, documents, metadatas


def build() -> None:
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        print(f"[error] Missing dependency: {e}")
        print(VECTORSTORE_DEPENDENCY_ERROR_MESSAGE)
        sys.exit(1)

    ids, documents, metadatas = [], [], []
    for name in VECTORSTORE_SOURCE_FILES:
        source_cards = _load_cards(DATA_DIR / name)
        source_ids, source_documents, source_metadatas = _prepare_documents(source_cards, name)
        ids.extend(source_ids)
        documents.extend(source_documents)
        metadatas.extend(source_metadatas)

    if not documents:
        print("[warn] No cards found. Vectorstore not built.")
        return

    model = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    try:
        client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(CHROMA_COLLECTION)

    embeddings = model.encode(documents).tolist()
    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    print(f"[ok] Built vectorstore: {len(documents)} documents → collection '{CHROMA_COLLECTION}'.")


if __name__ == "__main__":
    build()
