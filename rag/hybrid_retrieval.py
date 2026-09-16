"""Shared CPU retrieval core used by the application and the benchmark.

No LLM calls. RRF scores are ranking scores, never confidence probabilities.
"""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import re
import numpy as np


def tokenize(text):
    words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text.lower())
    output = []
    for word in words:
        if '\u4e00' <= word[0] <= '\u9fff':
            output.extend(word)
            output.extend(word[i:i+2] for i in range(len(word)-1))
        else:
            output.append(word)
    return output


def normalize(vectors):
    x = np.asarray(vectors, dtype=np.float32)
    if x.ndim != 2 or not np.isfinite(x).all():
        raise ValueError('embeddings must be a finite 2D matrix')
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)


class BM25:
    def __init__(self, texts, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.postings = defaultdict(list)
        counts = [Counter(tokenize(text)) for text in texts]
        self.lengths = np.array([sum(c.values()) for c in counts], dtype=np.float32)
        self.avg = max(float(self.lengths.mean()), 1.0)
        self.n = len(texts)
        for i, count in enumerate(counts):
            for token, freq in count.items():
                self.postings[token].append((i, freq))

    def scores(self, query):
        result = np.zeros(self.n, dtype=np.float32)
        for token in sorted(set(tokenize(query))):
            posting = self.postings.get(token, [])
            if not posting:
                continue
            ids, tf = np.array(posting).T
            idf = np.log1p((self.n-len(ids)+0.5)/(len(ids)+0.5))
            result[ids] += idf * tf*(self.k1+1)/(tf+self.k1*(1-self.b+self.b*self.lengths[ids]/self.avg))
        return result


def rank_scores(scores, k, allowed=None, positive_only=False):
    if k <= 0:
        raise ValueError('k must be positive')
    ids = np.arange(len(scores)) if allowed is None else np.asarray(allowed, dtype=int)
    if positive_only:
        ids = ids[scores[ids] > 0]
    # Stable corpus order makes ties reproducible.
    return ids[np.argsort(-scores[ids], kind='stable')[:k]].tolist()


def rrf(dense_ids, sparse_ids, weight=0.5, constant=60):
    if not 0 <= weight <= 1 or constant <= 0:
        raise ValueError('invalid fusion parameters')
    scores = defaultdict(float)
    for ids, w in [(dense_ids, weight), (sparse_ids, 1-weight)]:
        if w == 0:
            continue
        for rank, i in enumerate(dict.fromkeys(ids), 1):
            scores[i] += w/(constant+rank)
    return sorted(scores, key=lambda i: (-scores[i], i)), dict(scores)


class FastEncoder:
    """English CPU model; use a multilingual model for Chinese evaluation."""
    def __init__(self, model_name='sentence-transformers/all-MiniLM-L6-v2', cache_dir=None, threads=4, model_dir=None):
        from fastembed import TextEmbedding
        self.model_name = model_name
        self.model = TextEmbedding(model_name=model_name, cache_dir=cache_dir, threads=threads, specific_model_path=model_dir)

    def encode(self, texts, query=False):
        method = self.model.query_embed if query else self.model.passage_embed
        return normalize(list(method(texts, batch_size=32)))

    def embed_documents(self, texts):
        return self.encode(texts)

    def embed_query(self, text):
        return self.encode([text], query=True)[0]


def cached_encode(encoder, texts, folder, query=False):
    payload = json.dumps({'model':encoder.model_name, 'query':query, 'texts':texts}, ensure_ascii=False).encode()
    key = hashlib.sha256(payload).hexdigest()
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    path = folder / (key+'.npy')
    if path.exists():
        vectors = np.load(path, allow_pickle=False)
        if len(vectors) != len(texts):
            raise ValueError('invalid embedding cache')
        return normalize(vectors)
    vectors = encoder.encode(texts, query=query)
    np.save(path, vectors, allow_pickle=False)
    return vectors


class HybridIndex:
    def __init__(self, records, vectors=None, encoder=None):
        if not records or len({r['id'] for r in records}) != len(records):
            raise ValueError('records must be nonempty and have unique ids')
        self.records = records
        self.encoder = encoder
        self.bm25 = BM25([r['text'] for r in records])
        self.vectors = normalize(vectors) if vectors is not None else None
        if self.vectors is not None and len(self.vectors) != len(records):
            raise ValueError('vector count does not match records')

    def search(self, query, k=20, mode='hybrid', pool=100, weight=0.5, source=None, query_vector=None):
        if k <= 0 or pool < k:
            raise ValueError('require pool >= k > 0')
        if mode not in {'bm25', 'dense', 'hybrid'}:
            raise ValueError('unknown retrieval mode')
        if not query.strip():
            return []
        allowed = [i for i,r in enumerate(self.records) if source is None or r.get('source')==source]
        if not allowed:
            return []
        sparse_scores = self.bm25.scores(query)
        sparse = rank_scores(sparse_scores, pool, allowed, positive_only=True)
        dense, dense_scores = [], np.zeros(len(self.records), dtype=np.float32)
        if mode != 'bm25':
            if self.vectors is None:
                raise RuntimeError('dense index is unavailable')
            if query_vector is None:
                if self.encoder is None:
                    raise RuntimeError('query encoder is unavailable')
                query_vector = self.encoder.embed_query(query)
            q = normalize(np.asarray(query_vector).reshape(1,-1))[0]
            dense_scores = self.vectors @ q
            dense = rank_scores(dense_scores, pool, allowed)
        if mode == 'bm25':
            ranked, scores = sparse, dict(enumerate(sparse_scores))
        elif mode == 'dense':
            ranked, scores = dense, dict(enumerate(dense_scores))
        else:
            ranked, scores = rrf(dense, sparse, weight)
        dr, sr = {i:r for r,i in enumerate(dense,1)}, {i:r for r,i in enumerate(sparse,1)}
        return [{**self.records[i], 'score':float(scores[i]), 'dense_score':float(dense_scores[i]),
                 'bm25_score':float(sparse_scores[i]), 'dense_rank':dr.get(i), 'bm25_rank':sr.get(i)} for i in ranked[:k]]

    def save(self, directory):
        directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
        (directory/'records.json').write_text(json.dumps(self.records, ensure_ascii=False), encoding='utf-8')
        # JSON + NumPy with allow_pickle=False, never unpickle uploaded indexes.
        if self.vectors is not None:
            np.save(directory/'vectors.npy', self.vectors, allow_pickle=False)
        elif (directory/'vectors.npy').exists():
            (directory/'vectors.npy').unlink()

    @classmethod
    def load(cls, directory, encoder=None):
        directory = Path(directory)
        records = json.loads((directory/'records.json').read_text(encoding='utf-8'))
        vectors = np.load(directory/'vectors.npy', allow_pickle=False) if (directory/'vectors.npy').exists() else None
        return cls(records, vectors, encoder)
