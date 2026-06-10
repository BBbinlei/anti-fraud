"""Unit tests for services/rag.py retrieve() runtime path."""

import pytest

from config import RAG_SIMILARITY_THRESHOLD
from services import rag
from services.rag import retrieve


class _FakeModel:
    def encode(self, texts):
        class _Array:
            def tolist(self_inner):
                return [[0.1] * 10]
        return _Array()


class _FakeCollection:
    def __init__(self, distances):
        self._distances = distances

    def query(self, query_embeddings, n_results):
        return {
            "documents": [["fake document about scam"]],
            "distances": [self._distances],
            "metadatas": [[{"fraud_type": "shuadan"}]],
        }


def _patch(monkeypatch, distances):
    monkeypatch.setattr(rag, "_get_model", lambda: _FakeModel())
    monkeypatch.setattr(rag, "_get_collection", lambda: _FakeCollection(distances))


def test_retrieve_returns_documents_above_threshold(monkeypatch):
    _patch(monkeypatch, [0.15])

    results = retrieve("刷单兼职")

    assert len(results) == 1
    assert results[0]["score"] == round(1.0 - 0.15, 4)
    assert results[0]["score"] >= RAG_SIMILARITY_THRESHOLD
    assert results[0]["document"] == "fake document about scam"
    assert results[0]["metadata"]["fraud_type"] == "shuadan"


def test_retrieve_filters_documents_below_threshold(monkeypatch):
    _patch(monkeypatch, [0.85])

    results = retrieve("刷单兼职")

    assert results == []


def test_retrieve_returns_empty_list_when_model_import_fails(monkeypatch):
    def _raise_import():
        raise ImportError("sentence_transformers not found")

    monkeypatch.setattr(rag, "_get_model", _raise_import)
    monkeypatch.setattr(rag, "_get_collection", lambda: _FakeCollection([0.1]))

    results = retrieve("任意查询")

    assert results == []


def test_retrieve_returns_empty_list_when_collection_unavailable(monkeypatch):
    def _raise_collection():
        raise RuntimeError("chroma collection not found")

    monkeypatch.setattr(rag, "_get_model", lambda: _FakeModel())
    monkeypatch.setattr(rag, "_get_collection", _raise_collection)

    results = retrieve("任意查询")

    assert results == []


def test_retrieve_resets_module_state_between_calls(monkeypatch):
    call_log = []

    def _spy_get_model():
        call_log.append("model")
        return _FakeModel()

    def _spy_get_collection():
        call_log.append("collection")
        return _FakeCollection([0.1])

    monkeypatch.setattr(rag, "_model", None)
    monkeypatch.setattr(rag, "_chroma_client", None)
    monkeypatch.setattr(rag, "_get_model", _spy_get_model)
    monkeypatch.setattr(rag, "_get_collection", _spy_get_collection)

    retrieve("第一次调用")
    retrieve("第二次调用")

    assert call_log.count("model") == 2
    assert call_log.count("collection") == 2


def test_retrieve_handles_empty_query_without_crashing(monkeypatch):
    _patch(monkeypatch, [0.1])

    results = retrieve("")

    assert isinstance(results, list)
