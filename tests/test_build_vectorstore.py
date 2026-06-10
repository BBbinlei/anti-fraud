import json
import sys
from types import ModuleType

from scripts import build_vectorstore


def test_compose_document_uses_structured_scam_card_fields():
    card = {
        "id": "shuadan",
        "name": "刷单返利诈骗",
        "target": "在校学生",
        "tactics": ["先小额返利建立信任", "逐步要求垫付"],
        "red_flags": ["刷单", "垫付"],
        "prevention": ["任何要垫资的兼职都是诈骗"],
        "legal": "《刑法》第266条诈骗罪",
        "typical_case": "某学生刷单被骗。",
    }

    document = build_vectorstore._compose_document(card)

    assert "骗局名称：刷单返利诈骗" in document
    assert "目标人群：在校学生" in document
    assert "常见套路：先小额返利建立信任；逐步要求垫付" in document
    assert "风险信号：刷单；垫付" in document
    assert "防范建议：任何要垫资的兼职都是诈骗" in document
    assert "法律依据：《刑法》第266条诈骗罪" in document
    assert "典型案例：某学生刷单被骗。" in document


def test_prepare_documents_builds_stable_ids_and_metadata_for_current_cards():
    cards = [
        {
            "id": "gongjianfa",
            "name": "冒充公检法诈骗",
            "content": "不存在安全账户。",
        }
    ]

    ids, documents, metadatas = build_vectorstore._prepare_documents(cards, "scam_cards.json")

    assert ids == ["scam_cards_gongjianfa"]
    assert documents == ["骗局名称：冒充公检法诈骗\n知识正文：不存在安全账户。"]
    assert metadatas == [
        {
            "fraud_type": "gongjianfa",
            "title": "冒充公检法诈骗",
            "source_file": "scam_cards.json",
        }
    ]


def test_load_cards_supports_cards_payload(tmp_path):
    cards_file = tmp_path / "review_cards.json"
    cards_file.write_text(
        json.dumps({"cards": [{"id": "review_shuadan", "title": "刷单复盘"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert build_vectorstore._load_cards(cards_file) == [
        {"id": "review_shuadan", "title": "刷单复盘"}
    ]


def test_prepare_documents_skips_invalid_or_empty_cards():
    ids, documents, metadatas = build_vectorstore._prepare_documents(
        [
            {},
            {"id": "empty"},
            "invalid",
            {"id": "valid", "title": "有效卡片"},
        ],
        "review_cards.json",
    )

    assert ids == ["review_cards_valid"]
    assert documents == ["标题：有效卡片"]
    assert metadatas[0]["fraud_type"] == "valid"
    assert metadatas[0]["source_file"] == "review_cards.json"


def test_build_adds_prepared_documents_to_chroma_without_real_dependencies(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "scam_cards.json").write_text(
        json.dumps(
            {
                "scams": [
                    {
                        "id": "shuadan",
                        "name": "刷单返利诈骗",
                        "red_flags": ["刷单", "垫付"],
                        "prevention": ["拒绝垫资"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {}

    class FakeEmbeddings:
        def tolist(self):
            return [[0.1, 0.2, 0.3]]

    class FakeSentenceTransformer:
        def __init__(self, model_name):
            captured["model_name"] = model_name

        def encode(self, documents):
            captured["encoded_documents"] = documents
            return FakeEmbeddings()

    class FakeCollection:
        def add(self, ids, embeddings, documents, metadatas):
            captured["ids"] = ids
            captured["embeddings"] = embeddings
            captured["documents"] = documents
            captured["metadatas"] = metadatas

    class FakeClient:
        def __init__(self, path):
            captured["path"] = path

        def delete_collection(self, collection_name):
            captured["deleted_collection"] = collection_name

        def create_collection(self, collection_name):
            captured["created_collection"] = collection_name
            return FakeCollection()

    fake_chromadb = ModuleType("chromadb")
    fake_chromadb.PersistentClient = FakeClient
    fake_sentence_transformers = ModuleType("sentence_transformers")
    fake_sentence_transformers.SentenceTransformer = FakeSentenceTransformer

    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_sentence_transformers)
    monkeypatch.setattr(build_vectorstore, "DATA_DIR", data_dir)
    monkeypatch.setattr(build_vectorstore, "VECTORSTORE_SOURCE_FILES", ("scam_cards.json",))
    monkeypatch.setattr(build_vectorstore, "CHROMA_DIR", tmp_path / "chroma_db")

    build_vectorstore.build()

    assert captured["ids"] == ["scam_cards_shuadan"]
    assert captured["embeddings"] == [[0.1, 0.2, 0.3]]
    assert captured["metadatas"] == [
        {
            "fraud_type": "shuadan",
            "title": "刷单返利诈骗",
            "source_file": "scam_cards.json",
        }
    ]
    assert "风险信号：刷单；垫付" in captured["documents"][0]
    assert "防范建议：拒绝垫资" in captured["documents"][0]
