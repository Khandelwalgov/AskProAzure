import hashlib
import logging
import os
import re
from collections import Counter

from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from langchain_openai import AzureOpenAIEmbeddings
from sklearn.feature_extraction.text import HashingVectorizer

load_dotenv()

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "how", "i", "if", "in", "into", "is", "it", "its", "of", "on",
    "or", "our", "that", "the", "their", "there", "this", "to", "was", "we",
    "were", "what", "when", "where", "which", "who", "why", "will", "with",
    "you", "your",
}
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{1,}")
_CROSS_ENCODER = None
_CROSS_ENCODER_LOAD_FAILED = False


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class LocalHashEmbeddings(Embeddings):
    """Stateless lexical embeddings for offline/local FAISS retrieval."""

    def __init__(self, n_features=None):
        self.n_features = int(n_features or os.getenv("LOCAL_EMBEDDING_DIM", "1536"))
        self.vectorizer = HashingVectorizer(
            n_features=self.n_features,
            alternate_sign=False,
            norm="l2",
            lowercase=True,
            ngram_range=(1, 2),
            token_pattern=r"(?u)\b\w+\b",
        )

    def _embed(self, texts):
        matrix = self.vectorizer.transform(texts)
        return matrix.astype("float32").toarray().tolist()

    def embed_documents(self, texts):
        return self._embed(texts)

    def embed_query(self, text):
        return self._embed([text])[0]


class SentenceTransformerEmbeddings(Embeddings):
    """Optional local semantic embeddings when a model is already available."""

    def __init__(self, model_name=None):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name or os.getenv(
            "SENTENCE_TRANSFORMER_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        local_files_only = env_bool("SENTENCE_TRANSFORMER_LOCAL_FILES_ONLY", True)
        self.model = SentenceTransformer(self.model_name, local_files_only=local_files_only)

    def _embed(self, texts):
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.astype("float32").tolist()

    def embed_documents(self, texts):
        return self._embed(texts)

    def embed_query(self, text):
        return self._embed([text])[0]


def build_embedding_model():
    provider = os.getenv("RAG_EMBEDDING_PROVIDER", "local").lower()

    if provider in {"local", "hash", "hashing"}:
        return LocalHashEmbeddings()

    if provider in {"sentence-transformers", "sentence_transformers", "sbert", "local-semantic"}:
        return SentenceTransformerEmbeddings()

    if provider == "auto":
        try:
            return SentenceTransformerEmbeddings()
        except Exception as exc:
            logger.warning("Falling back to hashing embeddings: %s", exc)
            return LocalHashEmbeddings()

    if provider in {"azure", "azure-openai"}:
        required = [
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_VERSION",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        ]
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise RuntimeError(
                "Missing Azure embedding env vars: " + ", ".join(missing)
            )

        return AzureOpenAIEmbeddings(
            model=os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        )

    raise RuntimeError(f"Unsupported RAG_EMBEDDING_PROVIDER: {provider}")


embedding_model = build_embedding_model()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "700")),
    chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "100")),
    separators=["\n\n", "\n", ". ", "; ", ", ", " "],
    add_start_index=True,
)


def tokenize(text):
    return [
        token.lower()
        for token in TOKEN_RE.findall(str(text or ""))
        if token.lower() not in STOPWORDS and len(token) > 1
    ]


def extract_keywords(text, max_keywords=24):
    counts = Counter(tokenize(text))
    return [token for token, _count in counts.most_common(max_keywords)]


def stable_hash(value, length=12):
    return hashlib.sha1(str(value).encode("utf-8", errors="ignore")).hexdigest()[:length]


def stable_chunk_id(filename, chunk_index, content):
    digest = stable_hash(content)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename or "document")[:80]
    return f"{safe_name}:{chunk_index}:{digest}"


def stable_part_id(filename, metadata):
    fields = [
        filename,
        metadata.get("source_type"),
        metadata.get("page"),
        metadata.get("section_index"),
        metadata.get("paragraph_start"),
        metadata.get("line_start"),
        metadata.get("part_index"),
    ]
    return stable_hash("|".join(str(field or "") for field in fields))


def metadata_location(metadata):
    if metadata.get("page"):
        page_label = metadata.get("page_label") or metadata.get("page")
        return f"page {page_label}"
    if metadata.get("paragraph_start"):
        start = metadata.get("paragraph_start")
        end = metadata.get("paragraph_end") or start
        return f"paragraphs {start}-{end}" if end != start else f"paragraph {start}"
    if metadata.get("line_start"):
        start = metadata.get("line_start")
        end = metadata.get("line_end") or start
        return f"lines {start}-{end}" if end != start else f"line {start}"
    if metadata.get("section_heading"):
        return f"section {metadata.get('section_heading')}"
    return ""


def source_label(metadata):
    filename = metadata.get("filename") or "uploaded document"
    location = metadata_location(metadata)
    return f"{filename}, {location}" if location else filename


def normalize_document_parts(text_or_parts, base_metadata):
    base_metadata = dict(base_metadata or {})
    if isinstance(text_or_parts, list):
        parts = text_or_parts
    else:
        parts = [{"text": str(text_or_parts or ""), "metadata": {"source_type": "text", "part_index": 0}}]

    documents = []
    for index, part in enumerate(parts):
        if isinstance(part, dict):
            text = str(part.get("text") or "").strip()
            part_metadata = dict(part.get("metadata") or {})
        else:
            text = str(part or "").strip()
            part_metadata = {"part_index": index}
        if not text:
            continue

        metadata = {**base_metadata, **part_metadata}
        metadata.setdefault("part_index", index)
        metadata["part_id"] = metadata.get("part_id") or stable_part_id(
            metadata.get("filename", "uploaded document"), metadata
        )
        metadata["source_label"] = source_label(metadata)
        documents.append(Document(page_content=text, metadata=metadata))
    return documents


def enrich_chunk_metadata(chunk, _base_metadata, chunk_index):
    metadata = dict(chunk.metadata or {})
    filename = metadata.get("filename", "uploaded document")
    keywords = extract_keywords(chunk.page_content)
    metadata.update(
        {
            "chunk_index": chunk_index,
            "chunk_id": stable_chunk_id(filename, chunk_index, chunk.page_content),
            "chunk_keywords": ", ".join(keywords),
            "token_count": len(tokenize(chunk.page_content)),
            "char_count": len(chunk.page_content),
            "source_label": source_label(metadata),
        }
    )
    chunk.metadata = metadata
    return chunk


def chunk_and_store(text_or_parts, persist_path, metadata=None):
    docs = normalize_document_parts(text_or_parts, metadata or {})
    if not docs:
        raise ValueError("No extractable text found in document")

    chunks = text_splitter.split_documents(docs)
    enriched_chunks = [
        enrich_chunk_metadata(chunk, metadata or {}, index)
        for index, chunk in enumerate(chunks)
    ]
    vector_db = FAISS.from_documents(enriched_chunks, embedding_model)

    os.makedirs(os.path.dirname(persist_path), exist_ok=True)
    vector_db.save_local(persist_path)


def load_vector_db(path):
    return FAISS.load_local(path, embedding_model, allow_dangerous_deserialization=True)


def retrieve_chunks(vectordb: FAISS, query: str, k: int = 25):
    return vectordb.similarity_search_with_score(query, k=k)


def get_all_documents(vectordb: FAISS):
    docstore = getattr(vectordb, "docstore", None)
    doc_dict = getattr(docstore, "_dict", None)
    if not doc_dict:
        return []
    return list(doc_dict.values())


def metadata_text(doc):
    metadata = doc.metadata or {}
    keys = (
        "filename",
        "storage_key",
        "source_type",
        "source_label",
        "section_heading",
        "page",
        "page_label",
        "line_start",
        "line_end",
        "paragraph_start",
        "paragraph_end",
        "chunk_keywords",
    )
    return " ".join(str(metadata.get(key, "")) for key in keys)


def keyword_features(query, doc):
    query_tokens = tokenize(query)
    if not query_tokens:
        return {"keyword": 0.0, "metadata": 0.0, "phrase": 0.0, "matched_terms": []}

    doc_tokens = tokenize(doc.page_content)
    doc_token_set = set(doc_tokens)
    query_token_set = set(query_tokens)
    matched = sorted(query_token_set & doc_token_set)

    keyword = len(matched) / max(len(query_token_set), 1)

    metadata_tokens = set(tokenize(metadata_text(doc)))
    metadata_overlap = len(query_token_set & metadata_tokens) / max(len(query_token_set), 1)

    lower_content = " ".join(doc.page_content.lower().split())
    lower_query = " ".join((query or "").lower().split())
    phrase = 0.0
    if lower_query and len(lower_query) > 8 and lower_query in lower_content:
        phrase = 1.0
    else:
        bigrams = [" ".join(query_tokens[i : i + 2]) for i in range(len(query_tokens) - 1)]
        if bigrams:
            phrase = sum(1 for phrase_text in bigrams if phrase_text in lower_content) / len(bigrams)

    return {
        "keyword": keyword,
        "metadata": metadata_overlap,
        "phrase": phrase,
        "matched_terms": matched[:12],
    }


def doc_identity(doc):
    metadata = doc.metadata or {}
    return metadata.get("chunk_id") or stable_hash(doc.page_content, length=24)


def normalized_semantic_score(raw_distance):
    try:
        distance = max(float(raw_distance), 0.0)
    except (TypeError, ValueError):
        distance = 0.0
    return 1.0 / (1.0 + distance)


def get_cross_encoder():
    global _CROSS_ENCODER, _CROSS_ENCODER_LOAD_FAILED

    model_name = os.getenv("RAG_CROSS_ENCODER_MODEL", "").strip()
    if not model_name or _CROSS_ENCODER_LOAD_FAILED:
        return None
    if _CROSS_ENCODER is not None:
        return _CROSS_ENCODER

    try:
        from sentence_transformers import CrossEncoder

        _CROSS_ENCODER = CrossEncoder(
            model_name,
            local_files_only=env_bool("RAG_CROSS_ENCODER_LOCAL_FILES_ONLY", True),
        )
        logger.info("Loaded cross-encoder reranker %s", model_name)
        return _CROSS_ENCODER
    except Exception as exc:
        _CROSS_ENCODER_LOAD_FAILED = True
        logger.warning("Cross-encoder reranker disabled: %s", exc)
        return None


def apply_cross_encoder_rerank(query, ranked):
    cross_encoder = get_cross_encoder()
    if not cross_encoder or not ranked:
        return ranked

    limit = int(os.getenv("RAG_CROSS_ENCODER_CANDIDATES", "20"))
    weight = float(os.getenv("RAG_CROSS_ENCODER_WEIGHT", "0.35"))
    candidates = ranked[: max(1, limit)]

    try:
        pairs = [(query, item["doc"].page_content) for item in candidates]
        raw_scores = [float(score) for score in cross_encoder.predict(pairs)]
    except Exception as exc:
        logger.warning("Cross-encoder rerank failed: %s", exc)
        return ranked

    min_score = min(raw_scores)
    max_score = max(raw_scores)
    score_range = max(max_score - min_score, 1e-9)
    for item, raw_score in zip(candidates, raw_scores):
        normalized = (raw_score - min_score) / score_range
        item["cross_encoder_score"] = normalized
        item["cross_encoder_score_raw"] = raw_score
        item["score"] = ((1.0 - weight) * item["score"]) + (weight * normalized)

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def retrieve_ranked_chunks(
    vectordb: FAISS,
    query: str,
    semantic_k=30,
    keyword_k=30,
    final_k=10,
):
    semantic_results = retrieve_chunks(vectordb, query, k=semantic_k)
    semantic_by_id = {}
    candidates = {}

    for doc, distance in semantic_results:
        identity = doc_identity(doc)
        semantic_by_id[identity] = max(
            semantic_by_id.get(identity, 0.0), normalized_semantic_score(distance)
        )
        candidates[identity] = doc

    keyword_scored = []
    for doc in get_all_documents(vectordb):
        features = keyword_features(query, doc)
        keyword_scored.append((features["keyword"] + features["metadata"] + features["phrase"], doc))

    keyword_scored.sort(key=lambda item: item[0], reverse=True)
    for _score, doc in keyword_scored[:keyword_k]:
        candidates[doc_identity(doc)] = doc

    weights = {
        "semantic": float(os.getenv("RAG_RERANK_SEMANTIC_WEIGHT", "0.52")),
        "keyword": float(os.getenv("RAG_RERANK_KEYWORD_WEIGHT", "0.28")),
        "metadata": float(os.getenv("RAG_RERANK_METADATA_WEIGHT", "0.12")),
        "phrase": float(os.getenv("RAG_RERANK_PHRASE_WEIGHT", "0.08")),
    }

    ranked = []
    for identity, doc in candidates.items():
        features = keyword_features(query, doc)
        semantic = semantic_by_id.get(identity, 0.0)
        rerank_score = (
            weights["semantic"] * semantic
            + weights["keyword"] * features["keyword"]
            + weights["metadata"] * features["metadata"]
            + weights["phrase"] * features["phrase"]
        )
        ranked.append(
            {
                "doc": doc,
                "score": rerank_score,
                "semantic_score": semantic,
                "keyword_score": features["keyword"],
                "metadata_score": features["metadata"],
                "phrase_score": features["phrase"],
                "cross_encoder_score": None,
                "cross_encoder_score_raw": None,
                "matched_terms": features["matched_terms"],
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    ranked = apply_cross_encoder_rerank(query, ranked)
    return ranked[:final_k]
