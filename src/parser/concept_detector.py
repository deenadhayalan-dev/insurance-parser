"""
Concept detector - maps document labels to canonical financial concepts.
Uses vocabulary configuration (data-driven, not hardcoded).
"""

import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import yaml

from ..utils.patterns import normalize_text


class ConceptDetector:
    """
    Detects financial concepts in text using vocabulary-based matching.
    Label-agnostic: uses configuration data, not hardcoded labels.
    """
    
    def __init__(self, vocabulary_path: Optional[str] = None):
        """
        Initialize detector with vocabulary.
        
        Args:
            vocabulary_path: Path to vocabulary YAML file
        """
        if vocabulary_path is None:
            # Default to config/vocabulary.yaml relative to project root
            vocabulary_path = Path(__file__).parent.parent.parent / 'config' / 'vocabulary.yaml'
        
        self.vocabulary = self._load_vocabulary(vocabulary_path)
        self.concepts = self.vocabulary.get('financial_concepts', {})
    
    def _load_vocabulary(self, path: Path) -> dict:
        """Load vocabulary from YAML file"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load vocabulary from {path}: {e}")
    
    def detect_concept(self, text: str) -> Optional[str]:
        """
        Detect which canonical concept a text label represents.
        
        Args:
            text: Text label from document
            
        Returns:
            Canonical concept name or None
        """
        if not text:
            return None
        
        # Normalize text
        normalized = normalize_text(text)
        
        # Check each concept's labels
        for concept_name, concept_data in self.concepts.items():
            labels = concept_data.get('labels', [])
            
            for label in labels:
                label_normalized = normalize_text(label)
                
                # Exact match
                if normalized == label_normalized:
                    return concept_name
                
                # Fuzzy match: check if label is contained in text or vice versa
                if label_normalized in normalized or normalized in label_normalized:
                    # Additional check: ensure it's a meaningful match (not just substring)
                    if self._is_meaningful_match(normalized, label_normalized):
                        return concept_name
        
        return None
    
    def _is_meaningful_match(self, text: str, label: str) -> bool:
        """
        Check if a fuzzy match is meaningful (not just substring).
        Uses word boundary checks.
        """
        # Build regex with word boundaries
        # Escape special regex characters
        label_escaped = re.escape(label)
        
        # Try to find label as complete words
        pattern = r'\b' + label_escaped + r'\b'
        
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    def find_concept_candidates(self, text: str, window_size: int = 200) -> List[Tuple[str, int, str]]:
        """
        Find all potential concept mentions in text with their positions.
        Enhanced to avoid false matches and prioritize exact matches.
        
        Args:
            text: Full document text
            window_size: Character window around match
            
        Returns:
            List of (concept_name, position, matched_label) tuples, sorted by position
        """
        candidates = []
        text_lower = text.lower()
        
        for concept_name, concept_data in self.concepts.items():
            labels = concept_data.get('labels', [])
            
            for label in labels:
                label_lower = label.lower()
                
                # Find all occurrences of this label
                start = 0
                while True:
                    pos = text_lower.find(label_lower, start)
                    if pos == -1:
                        break
                    
                    # Enhanced validation: check word boundaries and context
                    if self._is_valid_label_match(text_lower, label_lower, pos, text):
                        # Additional check: verify this is in a relevant line
                        # (not in headers, footers, or unrelated sections)
                        if self._is_relevant_context(text, pos, concept_name):
                            candidates.append((concept_name, pos, label))
                    
                    start = pos + 1
        
        # Sort by position
        candidates.sort(key=lambda x: x[1])
        
        # Deduplicate: if same concept found very close (within 30 chars), keep first
        deduplicated = []
        for concept_name, pos, label in candidates:
            # Check if this concept was already found nearby
            if not any(c[0] == concept_name and abs(c[1] - pos) < 30 for c in deduplicated):
                deduplicated.append((concept_name, pos, label))
        
        return deduplicated
    
    def _is_valid_label_match(self, text_lower: str, label_lower: str, pos: int, original_text: str) -> bool:
        """
        Enhanced validation for label matches.
        Checks word boundaries and avoids false positives.
        
        Args:
            text_lower: Lowercase text
            label_lower: Lowercase label
            pos: Position of match
            original_text: Original text (with case)
            
        Returns:
            True if valid match
        """
        # Check character before (must be word boundary)
        if pos > 0:
            char_before = text_lower[pos - 1]
            if char_before.isalnum():
                return False
        
        # Check character after (must be word boundary)
        end_pos = pos + len(label_lower)
        if end_pos < len(text_lower):
            char_after = text_lower[end_pos]
            if char_after.isalnum():
                return False
        
        # Additional check: if label contains colon, must be followed by colon in text
        # Example: "Sum Insured:" should match "Sum Insured : 500000" but not "Sum Insured Member"
        if ':' in label_lower:
            # Look ahead for colon within 5 characters
            search_end = min(end_pos + 5, len(text_lower))
            has_colon = ':' in text_lower[end_pos:search_end]
            if not has_colon:
                return False
        
        return True
    
    def _is_relevant_context(self, text: str, pos: int, concept_name: str) -> bool:
        """
        Check if the label position is in a relevant context.
        Avoids matches in headers, footers, page numbers, etc.
        
        Args:
            text: Full text
            pos: Position of label
            concept_name: Concept being searched
            
        Returns:
            True if in relevant context
        """
        # Extract line containing the match
        line_start = text.rfind('\n', 0, pos) + 1
        line_end = text.find('\n', pos)
        if line_end == -1:
            line_end = len(text)
        
        line = text[line_start:line_end].lower()
        
        # Exclude lines that are clearly not financial data
        exclusion_keywords = [
            'page', 'website', 'www.', 'email', 'phone', 'address',
            'regd.', 'registered', 'corporate', 'office',
            'irdai', 'cin', 'toll free', 'customer care',
        ]
        
        # If line contains exclusion keywords and is short, likely a header/footer
        if len(line) < 100 and any(keyword in line for keyword in exclusion_keywords):
            return False
        
        # For financial concepts, the line should have some numeric or currency context
        # EXCEPT when they appear in table headers (which we need for table extraction)
        if concept_name in ['deductible_amount']:  # Only strict check for deductible
            # Line should contain numbers or currency symbols
            has_numbers = any(char.isdigit() for char in line)
            has_currency = any(symbol in line for symbol in ['₹', 'rs', 'inr', 'amount'])
            
            if not (has_numbers or has_currency):
                return False
        
        # For coverage_amount, base_premium, tax_amount, total_premium: allow table headers
        if concept_name in ['coverage_amount', 'base_premium', 'tax_amount', 'total_premium']:
            # Check if this looks like a table header (multiple column names)
            word_count = len([w for w in line.split() if len(w) > 2])
            if word_count >= 5:  # Likely a table header with multiple columns
                return True
            
            # Otherwise still need numeric/currency context
            has_numbers = any(char.isdigit() for char in line)
            has_currency = any(symbol in line for symbol in ['₹', 'rs', 'inr', 'amount'])
            
            if not (has_numbers or has_currency):
                return False
        
        return True
    
    def _is_at_word_boundary(self, text: str, label: str, pos: int) -> bool:
        """Check if match is at word boundaries"""
        # Check character before
        if pos > 0:
            char_before = text[pos - 1]
            if char_before.isalnum():
                return False
        
        # Check character after
        end_pos = pos + len(label)
        if end_pos < len(text):
            char_after = text[end_pos]
            if char_after.isalnum():
                return False
        
        return True
    
    def get_concept_value_type(self, concept_name: str) -> Optional[str]:
        """Get the expected value type for a concept"""
        concept_data = self.concepts.get(concept_name)
        if concept_data:
            return concept_data.get('value_type')
        return None
    
    def is_required_concept(self, concept_name: str) -> bool:
        """Check if a concept is required"""
        concept_data = self.concepts.get(concept_name)
        if concept_data:
            return concept_data.get('required', False)
        return False
    
    def get_all_concept_names(self) -> List[str]:
        """Get list of all canonical concept names"""
        return list(self.concepts.keys())
