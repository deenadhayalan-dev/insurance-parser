"""
Main orchestrator - integrates document processing and parsing.
"""

import json
from pathlib import Path
from typing import Optional

from .document_processor import DocumentProcessor
from .parser.pipeline import ParsingPipeline
from .models.schemas import ParsedInsuranceDocument


class InsuranceDocumentParser:
    """
    High-level parser that orchestrates:
    1. Document format detection
    2. Text extraction (digital/OCR)
    3. Semantic parsing
    4. Result generation
    """
    
    def __init__(self, vocabulary_path: Optional[str] = None):
        """
        Initialize parser.
        
        Args:
            vocabulary_path: Optional path to custom vocabulary file
        """
        self.pipeline = ParsingPipeline(vocabulary_path)
    
    def parse_document(self, pdf_path: str) -> ParsedInsuranceDocument:
        """
        Parse an insurance document.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            ParsedInsuranceDocument with extracted financial fields
        """
        # Step 1: Process document (extract text)
        processor = DocumentProcessor(pdf_path)
        text, is_ocr = processor.process()
        
        # Step 2: Parse text
        file_info = processor.get_file_info()
        result = self.pipeline.parse(
            text=text,
            source_file=file_info['file_name'],
            is_ocr=is_ocr
        )
        
        return result
    
    def parse_to_json(self, pdf_path: str, output_path: Optional[str] = None) -> str:
        """
        Parse document and return/save as JSON.
        
        Args:
            pdf_path: Path to PDF file
            output_path: Optional path to save JSON output
            
        Returns:
            JSON string
        """
        result = self.parse_document(pdf_path)
        
        # Convert to JSON
        json_output = result.model_dump_json(indent=2)
        
        # Save if output path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(json_output, encoding='utf-8')
            print(f"Results saved to: {output_path}")
        
        return json_output
    
    def parse_to_simple_dict(self, pdf_path: str) -> dict:
        """
        Parse document and return simplified dictionary (values only).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with just extracted values
        """
        result = self.parse_document(pdf_path)
        return result.to_simple_dict()
