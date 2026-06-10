import json

from config import FRAUD_TYPES, REVIEW_CARDS_FILE
from scripts import build_vectorstore


def _load_review_cards() -> list[dict]:
    payload = json.loads(REVIEW_CARDS_FILE.read_text(encoding="utf-8"))
    return payload.get("cards", [])


def test_review_cards_file_exists_and_covers_all_fraud_types():
    assert REVIEW_CARDS_FILE.exists()

    cards = _load_review_cards()
    assert cards
    assert {card.get("fraud_type") for card in cards} == set(FRAUD_TYPES)


def test_review_cards_have_indexable_content():
    for card in _load_review_cards():
        assert str(card.get("id", "")).startswith("review_")
        assert card.get("fraud_type") in FRAUD_TYPES
        assert str(card.get("title", "")).strip()
        assert str(card.get("content", "")).strip()


def test_review_cards_can_be_prepared_for_vectorstore():
    cards = _load_review_cards()

    ids, documents, metadatas = build_vectorstore._prepare_documents(cards, REVIEW_CARDS_FILE.name)

    assert len(ids) == len(FRAUD_TYPES)
    assert len(documents) == len(FRAUD_TYPES)
    assert len(metadatas) == len(FRAUD_TYPES)
    assert all(item.startswith("review_cards_review_") for item in ids)
    assert all("知识正文：" in document for document in documents)
    assert {metadata["fraud_type"] for metadata in metadatas} == set(FRAUD_TYPES)
    assert {metadata["source_file"] for metadata in metadatas} == {REVIEW_CARDS_FILE.name}
