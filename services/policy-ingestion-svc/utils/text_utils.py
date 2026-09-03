import re
import string
from typing import List, Optional
import hashlib

def clean_text(text: str) -> str:
    """Clean and normalize text"""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters but keep structure
    text = re.sub(r'[^\w\s\.\,\;\!\?\-\"\']', ' ', text)
    
    # Normalize line breaks
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract keywords from text"""
    
    # Remove punctuation and convert to lowercase
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Split into words
    words = text.split()
    
    # Remove common stop words (simplified)
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
    
    words = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Count word frequencies
    word_count = {}
    for word in words:
        word_count[word] = word_count.get(word, 0) + 1
    
    # Sort by frequency and return top keywords
    sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:max_keywords]]

def generate_content_hash(content: str) -> str:
    """Generate hash for content"""
    
    return hashlib.sha256(content.encode()).hexdigest()

def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate simple similarity between two texts"""
    
    # Simple Jaccard similarity
    set1 = set(text1.lower().split())
    set2 = set(text2.lower().split())
    
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)
