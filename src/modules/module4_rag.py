"""
Module 4 - RAG / Oracle

Provides RAGEngine for indexing folders into a per-user ChromaDB and
running semantic search + answer generation via LocalBrain.

This module is optional: if chromadb/sentence-transformers are not installed
the code will raise ImportError with a friendly message.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Optional
import os
import hashlib


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class RAGEngine:
    """A small RAG engine using chromadb + sentence-transformers.

    Usage:
        rag = RAGEngine(user_root_path)
        rag.index_folder(folder_path)
        answer = rag.query(question)
    """

    def __init__(self, user_root: Optional[Path] = None):
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except Exception as e:  # pragma: no cover - import-time check
            raise ImportError(
                "RAG dependencies not available. Install chromadb, sentence-transformers and langchain-text-splitters"
            ) from e

        self.chromadb = chromadb
        self.EmbedModel = SentenceTransformer
        self.TextSplitter = RecursiveCharacterTextSplitter

        self.embedding_model_name = os.getenv('RAG_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        self.top_k = int(os.getenv('RAG_SEARCH_TOP_K', '5'))

        # user_root is the downloads/{userfolder}
        self.user_root = Path(user_root) if user_root else None

        # client will be lazily created
        self._client = None
        self._collection = None
        self._embedder = None

    def _init_client(self):
        if self._client is None:
            # ensure user_root exists
            if not self.user_root:
                raise ValueError("user_root must be provided to initialize RAGEngine")

            vector_path = self.user_root / 'vector_db'
            vector_path.mkdir(parents=True, exist_ok=True)

            # Persistent client pointing to per-user folder
            self._client = self.chromadb.PersistentClient(path=str(vector_path))
            # single collection for all user docs
            self._collection = self._client.get_or_create_collection(name='secbrain')

        if self._embedder is None:
            # load sentence-transformers model (CPU)
            self._embedder = self.EmbedModel(self.embedding_model_name)

    def index_folder(self, folder: Path) -> int:
        """Index files from a folder into the user's ChromaDB.

        Returns number of chunks indexed (added or upserted).
        """
        folder = Path(folder)
        # discover user_root if not provided: look for ancestor named like 'digits_'
        if self.user_root is None:
            for p in folder.parents:
                if p.name and (p.parent.name == 'downloads' or '_' in p.name):
                    # choose the first ancestor under downloads or containing '_'
                    self.user_root = p
                    break
            if self.user_root is None:
                # fallback to folder.parent
                self.user_root = folder.parent

        self._init_client()

        texts: List[str] = []
        metadatas: List[Dict] = []
        ids: List[str] = []

        # Prioritise files: Knowledge.md, description.md, transcript.md
        priority_files = ["Knowledge.md", "description.md", "transcript.md"]

        for fname in priority_files:
            fpath = folder / fname
            if fpath.exists() and fpath.is_file():
                content = fpath.read_text(encoding='utf-8')
                source_type = 'unknown'
                if fname == 'Knowledge.md':
                    source_type = 'summary'
                elif fname == 'description.md':
                    source_type = 'description'
                elif fname == 'transcript.md':
                    source_type = 'transcript'

                # Split into chunks
                splitter = self.TextSplitter(chunk_size=1000, chunk_overlap=150)
                chunks = splitter.split_text(content)
                for idx, chunk in enumerate(chunks):
                    chunk_id = _hash_text(f"{fname}:{idx}:{chunk[:64]}")
                    texts.append(chunk)
                    metadatas.append({
                        'folder_name': folder.name,
                        'file_path': str(fpath),
                        'source_type': source_type,
                    })
                    ids.append(chunk_id)

        if not texts:
            return 0

        # compute embeddings
        self._init_client()
        embeddings = self._embedder.encode(texts, show_progress_bar=False)

        # Upsert into collection (use add/upsert depending on API)
        try:
            # prefer upsert if available
            if hasattr(self._collection, 'upsert'):
                self._collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
            else:
                self._collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
        except Exception:
            # best-effort add
            self._collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)

        return len(texts)

    def query(self, question: str) -> Dict:
        """Run semantic search and generate an answer using LocalBrain.

        Returns a dict: {'answer': str, 'sources': [folder_names], 'chunks': [texts]}
        """
        if self.user_root is None:
            raise ValueError("user_root must be set for query()")

        self._init_client()
        # embed query
        q_emb = self._embedder.encode([question])[0]

        # query collection
        try:
            results = self._collection.query(query_embeddings=[q_emb], n_results=self.top_k, include=['documents', 'metadatas'])
        except TypeError:
            # fallback to text query
            results = self._collection.query(query_texts=[question], n_results=self.top_k, include=['documents', 'metadatas'])

        # results structure varies; normalize
        docs = []
        metadatas = []
        try:
            docs = results['documents'][0]
            metadatas = results['metadatas'][0]
        except Exception:
            # try older structure
            docs = results.get('documents', [])
            metadatas = results.get('metadatas', [])

        # Build context for LLM
        chunks = []
        folders = []
        for d, m in zip(docs, metadatas):
            chunks.append(d)
            fn = m.get('folder_name') if isinstance(m, dict) else None
            if fn and fn not in folders:
                folders.append(fn)

        # Ask LocalBrain for a grounded answer
        try:
            from src.modules.local_brain import LocalBrain
            lb = LocalBrain()
            # system prompt per spec
            system = """
Ты — умный помощник. Отвечай на вопрос ТОЛЬКО на основе приведенного ниже контекста.
Если в контексте нет ответа, скажи "Я не нашел информации в вашей базе".
Не выдумывай факты.
"""

            # Build user prompt
            context_text = "\n\n".join(chunks[: self.top_k])
            user_prompt = f"КОНТЕКСТ:\n{context_text}\n\nВОПРОС: {question}"

            # Use LocalBrain to call LLM (it expects to return JSON in some cases), but here we just ask for plain text
            # We'll directly call ollama via LocalBrain.client to keep behavior consistent with project
            lb.initialize()
            response = lb.client.chat(
                model=lb.model,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user_prompt}
                ],
                options={'temperature': 0.0}
            )

            answer = response['message']['content']
        except Exception as e:
            answer = f"Ошибка при генерации ответа: {e}"

        return {
            'answer': answer,
            'sources': folders,
            'chunks': chunks,
        }
