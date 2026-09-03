from typing import List, Dict, Any, Optional
import asyncio
import time
import httpx
import hashlib
from models.embedding import EmbeddingRequest, EmbeddingResponse
from config import PolicyIngestionConfig
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating embeddings using LLM providers"""
    
    def __init__(self, config: PolicyIngestionConfig):
        self.config = config
        self.provider = config.embedding_provider
        self.model = config.embedding_model
        self.batch_size = config.embedding_batch_size
        
        self.client = httpx.AsyncClient(timeout=60.0)
        self._cache = {}
    
    async def generate_embeddings(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        
        if not texts:
            return []
        
        # Check cache
        cached_embeddings = []
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            text_hash = hashlib.md5(text.encode()).hexdigest()
            if text_hash in self._cache:
                cached_embeddings.append((i, self._cache[text_hash]))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        # Generate embeddings for uncached texts
        if uncached_texts:
            new_embeddings = await self._generate_embeddings_batch(uncached_texts)
            
            # Cache new embeddings
            for idx, embedding in zip(uncached_indices, new_embeddings):
                text_hash = hashlib.md5(texts[idx].encode()).hexdigest()
                self._cache[text_hash] = embedding
                cached_embeddings.append((idx, embedding))
        
        # Sort by original index
        cached_embeddings.sort(key=lambda x: x[0])
        return [emb for _, emb in cached_embeddings]
    
    async def _generate_embeddings_batch(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """Generate embeddings using provider API"""
        
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            if self.provider == "openai":
                embeddings = await self._openai_embed(batch)
            elif self.provider == "azure":
                embeddings = await self._azure_embed(batch)
            elif self.provider == "cohere":
                embeddings = await self._cohere_embed(batch)
            elif self.provider == "huggingface":
                embeddings = await self._huggingface_embed(batch)
            else:
                # Fallback to local embeddings (for development)
                embeddings = self._local_embed(batch)
            
            all_embeddings.extend(embeddings)
        
        return all_embeddings
    
    async def _openai_embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API"""
        
        if not self.config.openai_api_key:
            logger.warning("OpenAI API key not configured, using local embeddings")
            return self._local_embed(texts)
        
        try:
            response = await self.client.post(
                f"{self.config.openai_api_base or 'https://api.openai.com/v1'}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": texts
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                embeddings = [item['embedding'] for item in data['data']]
                logger.debug(f"Generated {len(embeddings)} embeddings via OpenAI")
                return embeddings
            else:
                logger.error(f"OpenAI API error: {response.status_code}")
                return self._local_embed(texts)
                
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            return self._local_embed(texts)
    
    async def _azure_embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Azure OpenAI"""
        
        # Implementation for Azure OpenAI
        return self._local_embed(texts)
    
    async def _cohere_embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Cohere API"""
        
        # Implementation for Cohere
        return self._local_embed(texts)
    
    async def _huggingface_embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using HuggingFace API"""
        
        # Implementation for HuggingFace
        return self._local_embed(texts)
    
    def _local_embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings locally (fallback for development)"""
        
        # Simple TF-IDF-like embedding for development
        import numpy as np
        
        embeddings = []
        for text in texts:
            # Simple embedding: use word frequencies
            words = text.lower().split()
            word_count = {}
            for word in words:
                word_count[word] = word_count.get(word, 0) + 1
            
            # Create fixed-size vector (simplified)
            vector = []
            for i in range(10):
                vector.append(sum(ord(c) for c in word) / 1000.0)
            
            # Pad to 1536 dimensions
            while len(vector) < 1536:
                vector.append(0.0)
            
            # Normalize
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = [v / norm for v in vector]
            
            embeddings.append(vector[:1536])
        
        return embeddings
