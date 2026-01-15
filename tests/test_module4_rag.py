import sys
import types
from pathlib import Path


def _make_fake_env(monkeypatch):
    # fake sentence_transformers
    fake_st = types.SimpleNamespace()

    class FakeEmbedder:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, texts, show_progress_bar=False):
            # return a simple numeric vector per text
            return [[0.1] * 8 for _ in texts]

    monkeypatch.setitem(sys.modules, 'sentence_transformers', types.SimpleNamespace(SentenceTransformer=FakeEmbedder))

    # fake text splitter
    class FakeSplitter:
        def __init__(self, chunk_size=1000, chunk_overlap=150):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap

        def split_text(self, text):
            # naive split by chunk_size
            chunks = []
            i = 0
            while i < len(text):
                chunks.append(text[i:i+self.chunk_size])
                i += self.chunk_size - self.chunk_overlap
            return chunks

    monkeypatch.setitem(sys.modules, 'langchain_text_splitters', types.SimpleNamespace(RecursiveCharacterTextSplitter=FakeSplitter))

    # fake chromadb
    class FakeCollection:
        def __init__(self):
            self.docs = []
            self.metadatas = []
            self.ids = []

        def upsert(self, ids, documents, metadatas, embeddings=None):
            self.ids = ids
            self.docs = documents
            self.metadatas = metadatas

        def add(self, ids, documents, metadatas, embeddings=None):
            self.upsert(ids, documents, metadatas, embeddings)

        def query(self, query_embeddings=None, n_results=5, include=None, query_texts=None, n_results_per_query=None, include_metadata=None):
            # return first n_results documents
            docs = self.docs[:n_results]
            metas = self.metadatas[:n_results]
            return {'documents': [docs], 'metadatas': [metas]}

    class FakeClient:
        def __init__(self, path=None):
            self.path = path
            self._col = FakeCollection()

        def get_or_create_collection(self, name='secbrain'):
            return self._col

    monkeypatch.setitem(sys.modules, 'chromadb', types.SimpleNamespace(PersistentClient=FakeClient))

    # fake LocalBrain used in query (ollama call)
    fake_localbrain_mod = types.ModuleType('src.modules.local_brain')

    class FakeClientInner:
        def chat(self, model=None, messages=None, options=None):
            return {'message': {'content': 'Ответ (фейковый)'}}

    class FakeLocalBrain:
        def __init__(self):
            self.model = 'fake-model'
            self.client = FakeClientInner()

        def initialize(self):
            return None

    fake_localbrain_mod.LocalBrain = FakeLocalBrain
    monkeypatch.setitem(sys.modules, 'src.modules.local_brain', fake_localbrain_mod)


def test_index_and_query(monkeypatch, tmp_path):
    _make_fake_env(monkeypatch)

    # create user root and folder
    user_root = tmp_path / 'user_123'
    user_root.mkdir()
    folder = user_root / '2026-01-15_test'
    folder.mkdir()

    # create Knowledge.md with some text
    content = "\n".join(["Это тестовый документ." * 50])
    (folder / 'Knowledge.md').write_text(content, encoding='utf-8')

    from src.modules.module4_rag import RAGEngine

    rag = RAGEngine(user_root=user_root)

    indexed = rag.index_folder(folder)
    assert indexed > 0

    # Query should return dict with keys
    res = rag.query('что в документе?')
    assert isinstance(res, dict)
    assert 'answer' in res
    assert 'sources' in res
    assert 'chunks' in res
