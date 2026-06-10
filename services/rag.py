"""Chroma vector retrieval with Phoenix observability span."""

from __future__ import annotations

import logging

from config import (
    CHROMA_COLLECTION,
    CHROMA_DIR,
    EMBED_MODEL,
    RAG_SIMILARITY_THRESHOLD,
    RAG_TOP_K,
)

logger = logging.getLogger(__name__)

_model = None
_chroma_client = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _get_collection():
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client.get_collection(CHROMA_COLLECTION)


def retrieve(query: str) -> list[dict]:
    """Return top-K documents above the similarity threshold.

    Returns empty list if dependencies are missing or the collection does not
    exist yet (build_vectorstore.py has not been run).
    """
    try:
        from opentelemetry import trace
    except ImportError:
        logger.warning("opentelemetry not installed, skipping RAG span")
        return _query(query, tracer=None)

    tracer = trace.get_tracer(__name__)
    return _query(query, tracer=tracer)


def _query(query: str, tracer) -> list[dict]:
    try:
        model = _get_model()
        collection = _get_collection()
    except ImportError:
        logger.warning("RAG dependencies not installed, skipping retrieval")
        return []
    except Exception:
        logger.warning("RAG collection not available (run build_vectorstore.py)", exc_info=True)
        return []

    try:
        embedding = model.encode([query]).tolist()[0]

        def _do_query(span=None):
            results = collection.query(query_embeddings=[embedding], n_results=RAG_TOP_K)
            docs = []
            if results and results.get("documents") and results["documents"][0]:
                for doc, dist, meta in zip(
                    results["documents"][0],
                    results["distances"][0],
                    results["metadatas"][0],
                ):
                    score = 1.0 - dist
                    if score >= RAG_SIMILARITY_THRESHOLD:
                        docs.append({"document": doc, "score": round(score, 4), "metadata": meta})
            if span is not None:
                span.set_attribute("retrieval.top_k", RAG_TOP_K)
                span.set_attribute("retrieval.query_len", len(query))
                span.set_attribute("retrieval.returned_count", len(docs))
                if docs:
                    span.set_attribute("retrieval.top1_score", docs[0]["score"])
            return docs

        if tracer is None:
            return _do_query()

        with tracer.start_as_current_span("chroma_retrieval") as span:
            return _do_query(span)

    except Exception:
        logger.warning("RAG query failed", exc_info=True)
        return []
