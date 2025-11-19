# memory.py

import numpy as np
import faiss
import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Optional, Literal
from pydantic import BaseModel
from datetime import datetime

load_dotenv()

class MemoryItem(BaseModel):
    text: str
    type: Literal["preference", "tool_output", "fact", "query", "system"] = "fact"
    timestamp: Optional[str] = datetime.now().isoformat()
    tool_name: Optional[str] = None
    user_query: Optional[str] = None
    tags: List[str] = []
    session_id: Optional[str] = None


class MemoryManager:
    def __init__(self, model_name="nomic-embed-text:latest"):
        self.model_name = model_name
        self.client = OpenAI(
            base_url=f"{os.getenv('LOCAL_HOST')}api",
            api_key=os.getenv("LOCAL_OLLAMA_API_KEY")
        )
        self.index = None
        self.data: List[MemoryItem] = []
        self.embeddings: List[np.ndarray] = []

    def _get_embedding(self, text: str) -> np.ndarray:
        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=text
            )
            return np.array(response.data[0].embedding, dtype=np.float32)
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise

    def add(self, item: MemoryItem):
        emb = self._get_embedding(item.text)
        self.embeddings.append(emb)
        self.data.append(item)

        # Initialize or add to index
        if self.index is None:
            self.index = faiss.IndexFlatL2(len(emb))
        self.index.add(np.stack([emb]))

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        type_filter: Optional[str] = None,
        tag_filter: Optional[List[str]] = None,
        session_filter: Optional[str] = None
    ) -> List[MemoryItem]:
        if not self.index or len(self.data) == 0:
            return []

        query_vec = self._get_embedding(query).reshape(1, -1)
        D, I = self.index.search(query_vec, top_k * 2)  # Overfetch to allow filtering

        results = []
        for idx in I[0]:
            if idx >= len(self.data):
                continue
            item = self.data[idx]

            # Filter by type
            if type_filter and item.type != type_filter:
                continue

            # Filter by tags
            if tag_filter and not any(tag in item.tags for tag in tag_filter):
                continue

            # Filter by session
            if session_filter and item.session_id != session_filter:
                continue

            results.append(item)
            if len(results) >= top_k:
                break

        return results

    def bulk_add(self, items: List[MemoryItem]):
        for item in items:
            self.add(item)
