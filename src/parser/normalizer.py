"""
Text normalizer - prepares text for semantic analysis.
"""

import re
from typing import List
from ..utils.patterns import normalize_text


class TextNormalizer:
    """
    Normalizes extracted text for consistent processing.
    Handles common OCR errors, formatting issues, and noise.
    """
    
    # Common OCR substitutions (character confusions)
    OCR_CORRECTIONS = {
        'l': '1',  # lowercase L to 1 in numeric context
        'O': '0',  # uppercase O to 0 in numeric context
        'l,': '1,',
        'O,': '0,',
    }
    
    def __init__(self):
        pass
    
    def normalize(self, text: str) -> str:
        """
        Apply normalization pipeline to text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Step 1: Basic normalization
        text = normalize_text(text)
        
        # Step 2: Fix common OCR errors in numbers
        text = self._fix_ocr_numbers(text)
        
        # Step 3: Standardize currency symbols
        text = self._standardize_currency(text)
        
        # Step 4: Standardize date separators
        text = self._standardize_dates(text)
        
        return text
    
    def _fix_ocr_numbers(self, text: str) -> str:
        """Fix common OCR errors in numeric contexts"""
        # Replace O with 0 when surrounded by digits
        text = re.sub(r'(\d)O(\d)', r'\g<1>0\g<2>', text)
        
        # Replace l with 1 when surrounded by digits or at start/end of number
        text = re.sub(r'(\d)l(\d)', r'\g<1>1\g<2>', text)
        text = re.sub(r'(\d)l\b', r'\g<1>1', text)
        text = re.sub(r'\bl(\d)', r'1\g<1>', text)
        
        return text
    
    def _standardize_currency(self, text: str) -> str:
        """Standardize currency representations"""
        # Standardize Rs, Rs., INR to ₹
        text = re.sub(r'\brs\.?\s*', r'₹', text, flags=re.IGNORECASE)
        text = re.sub(r'\binr\s*', r'₹', text, flags=re.IGNORECASE)
        
        return text
    
    def _standardize_dates(self, text: str) -> str:
        """Standardize date separators"""
        # Already handled by normalize_text and patterns
        return text
    
    def split_into_lines(self, text: str) -> List[str]:
        """Split text into lines for line-by-line analysis"""
        return [line.strip() for line in text.split('\n') if line.strip()]
    
    def extract_context_window(self, text: str, position: int, window_size: int = 200) -> str:
        """
        Extract context window around a position.
        
        Args:
            text: Full text
            position: Position of interest
            window_size: Characters before and after
            
        Returns:
            Context string
        """
        start = max(0, position - window_size)
        end = min(len(text), position + window_size)
        return text[start:end]
