"""
Document processor - orchestrates text extraction and format detection.
"""

from pathlib import Path
from typing import Tuple
from .text_extractor import TextExtractor


class DocumentProcessor:
    """
    High-level document processing coordinator.
    Handles PDF format detection and delegates to appropriate extractor.
    """
    
    def __init__(self, file_path: str):
        """
        Initialize processor with document path.
        
        Args:
            file_path: Path to document file
        """
        self.file_path = Path(file_path)
        self._validate_file()
    
    def _validate_file(self):
        """Validate file exists and is PDF"""
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")
        
        if self.file_path.suffix.lower() != '.pdf':
            raise ValueError(f"Unsupported file format: {self.file_path.suffix}. Only PDF supported.")
    
    def process(self) -> Tuple[str, bool]:
        """
        Process document and extract text.
        
        Returns:
            Tuple of (extracted_text, is_ocr_processed)
        """
        extractor = TextExtractor(str(self.file_path))
        return extractor.extract()
    
    def get_file_info(self) -> dict:
        """Get basic file information"""
        return {
            'file_name': self.file_path.name,
            'file_size': self.file_path.stat().st_size,
            'file_path': str(self.file_path.absolute())
        }
