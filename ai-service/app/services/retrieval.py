"""Small, deterministic TF-IDF cosine retriever over a fixed curated corpus."""
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from math import log, sqrt
from pathlib import Path
import re
from typing import Protocol

KB_ROOT = Path(__file__).resolve().parents[2] / 'knowledge_base'
DOCUMENTS = ('lifecycle', 'timeout', 'webhook', 'reconciliation', 'failure', 'refunds', 'idempotency', 'communication')
STOP = frozenset('a an the is are of to and or in for with from as be not this'.split())


def tokens(text: str) -> list[str]:
    return [w for w in re.findall(r'[a-z]+', text.lower()) if w not in STOP]


@dataclass(frozen=True)
class Chunk:
    document_id: str
    chunk_id: str
    title: str
    scenarios: tuple[str, ...]
    sources: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class Retriever(Protocol):
    def retrieve(self, query: str, *, top_k: int = 3, max_context: int = 3000, threshold: float = .12) -> list[Hit]: ...


def chunk_document(raw: str, max_chars: int = 800) -> tuple[Chunk, ...]:
    if not 100 <= max_chars <= 2000:
        raise ValueError('Invalid chunk size')
    header, body = raw.split('\n---\n', 1)
    metadata = dict(line.split(': ', 1) for line in header.splitlines())
    doc = metadata['Document-ID']
    if not re.fullmatch(r'PM-KB-[A-Z]+', doc):
        raise ValueError('Invalid document ID')
    chunks = []
    # Content hash plus index: reproducible across loads, content changes invalidate IDs.
    for i, offset in enumerate(range(0, len(body), max_chars)):
        text = body[offset:offset + max_chars].strip()
        if text:
            chunks.append(Chunk(doc, f'{doc}:{i:03d}:{sha256(text.encode()).hexdigest()[:12]}', metadata['Title'], tuple(metadata['Scenarios'].split(', ')), tuple(metadata['Sources'].split(' | ')), text))
    return tuple(chunks)


def load_documents() -> tuple[Chunk, ...]:
    chunks = []
    for name in DOCUMENTS:
        path = KB_ROOT / f'{name}.md'
        if path.is_file() and not path.is_symlink():
            if path.stat().st_size > 16384:
                raise ValueError('Curated document too large')
            chunks.extend(chunk_document(path.read_text(encoding='utf-8')))
    return tuple(chunks)


class LexicalRetriever:
    def __init__(self, chunks: tuple[Chunk, ...] | None = None):
        self.chunks = load_documents() if chunks is None else chunks
        bags = [Counter(tokens(c.title + ' ' + ' '.join(c.scenarios) + ' ' + c.text)) for c in self.chunks]
        self.idf = {t: log((1 + len(bags)) / (1 + sum(t in b for b in bags))) + 1 for b in bags for t in b}
        self.vectors = [{t: n * self.idf[t] for t, n in b.items()} for b in bags]

    def retrieve(self, query: str, *, top_k: int = 3, max_context: int = 3000, threshold: float = .12) -> list[Hit]:
        if not 1 <= top_k <= 5 or not 100 <= max_context <= 6000 or not 0 < threshold <= 1:
            raise ValueError('Invalid retrieval limits')
        q = {t: n * self.idf[t] for t, n in Counter(tokens(query[:1000])).items() if t in self.idf}
        norm = sqrt(sum(v*v for v in q.values()))
        if not norm:
            return []
        hits = []
        for c, v in zip(self.chunks, self.vectors):
            score = sum(q.get(t, 0)*w for t, w in v.items()) / (norm * sqrt(sum(w*w for w in v.values())) or 1)
            if score >= threshold:
                hits.append(Hit(c, score))
        hits.sort(key=lambda h: (-h.score, h.chunk.chunk_id))
        selected, used = [], 0
        for h in hits:
            # Bound the serialized context including metadata, not just body text.
            size = len(str(hit_data(h)))
            if used + size <= max_context:
                selected.append(h)
                used += size
            if len(selected) == top_k:
                break
        return selected


def hit_data(hit: Hit) -> dict:
    c = hit.chunk
    return dict(documentId=c.document_id, chunkId=c.chunk_id, title=c.title, sources=list(c.sources), text=c.text)


def evidence_query(evidence, result) -> str:
    # Only enums: arbitrary error messages and paymentMethod are never search instructions.
    return ' '.join([result.scenario.replace('_', ' '), evidence.payment_status.value] + [g.status for g in evidence.gateway_transactions or []])


# Chat-only extension. The original investigation corpus/order/IDs stay unchanged.
CHAT_DOCUMENTS = ('api', 'security', 'orchestration', 'routing', 'links', 'checkout', 'eligibility', 'statistics')
def load_chat_documents() -> tuple[Chunk, ...]:
    chunks = list(load_documents())
    for name in CHAT_DOCUMENTS:
        path = KB_ROOT / (name + '.md')
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
            raise ValueError('Chat knowledge unavailable')
        chunks.extend(chunk_document(path.read_text(encoding='utf-8')))
    if len({c.chunk_id for c in chunks}) != len(chunks): raise ValueError('Duplicate knowledge chunks')
    return tuple(chunks)
