"""
Text extraction from PDF documents.
Handles both digital (text-based) and scanned (image-based) PDFs.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import pdfplumber


class TextExtractor:
    """
    Extracts text from PDFs with automatic detection of digital vs scanned documents.
    Uses pdfplumber for digital PDFs and OCRmyPDF for scanned documents.
    """
    
    # Threshold to determine if a PDF is scanned (text density)
    MIN_TEXT_THRESHOLD = 100  # Minimum characters expected per page
    
    def __init__(self, pdf_path: str):
        """
        Initialize extractor with PDF path.
        
        Args:
            pdf_path: Path to the PDF file
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.is_scanned = False
        self.extracted_text = ""
    
    def extract(self) -> Tuple[str, bool]:
        """
        Extract text from PDF with automatic format detection.
        
        Returns:
            Tuple of (extracted_text, is_ocr_processed)
        """
        # First, try extracting as digital PDF
        text = self._extract_digital()
        
        # Check if extraction yielded meaningful text
        if self._is_sufficient_text(text):
            self.extracted_text = text
            self.is_scanned = False
            return text, False
        
        # If insufficient text, treat as scanned and apply OCR
        print(f"Insufficient text extracted ({len(text)} chars). Applying OCR...")
        text = self._extract_with_ocr()
        self.extracted_text = text
        self.is_scanned = True
        return text, True
    
    def _extract_digital(self) -> str:
        """
        Extract text from digital PDF using pdfplumber.
        
        Returns:
            Extracted text
        """
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                text_parts = []
                
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract text from page
                    page_text = page.extract_text()
                    
                    if page_text:
                        text_parts.append(f"--- Page {page_num} ---\n")
                        text_parts.append(page_text)
                        text_parts.append("\n\n")
                
                return "".join(text_parts)
        
        except Exception as e:
            print(f"Error extracting digital PDF: {e}")
            return ""
    
    def _extract_with_ocr(self) -> str:
        """
        Extract text from scanned PDF using OCRmyPDF.
        
        Returns:
            OCR extracted text
        """
        try:
            import ocrmypdf
            
            # Create temporary file for OCR output
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            try:
                # Run OCR
                ocrmypdf.ocr(
                    self.pdf_path,
                    tmp_path,
                    redo_ocr=True,  # Remove existing text and redo OCR
                    language=['eng'],  # Can add 'hin' for Hindi if needed
                    optimize=0,  # Don't optimize, just OCR
                    progress_bar=False
                )
                
                # Extract text from OCRed PDF
                with pdfplumber.open(tmp_path) as pdf:
                    text_parts = []
                    
                    for page_num, page in enumerate(pdf.pages, 1):
                        page_text = page.extract_text()
                        
                        if page_text:
                            text_parts.append(f"--- Page {page_num} ---\n")
                            text_parts.append(page_text)
                            text_parts.append("\n\n")
                    
                    return "".join(text_parts)
            
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        
        except ImportError:
            print("OCRmyPDF not installed. Install with: pip install ocrmypdf")
            return ""
        
        except Exception as e:
            print(f"Error during OCR processing: {e}")
            return ""
    
    def _is_sufficient_text(self, text: str) -> bool:
        """
        Check if extracted text is sufficient (not a scanned image).
        
        Args:
            text: Extracted text
            
        Returns:
            True if text is sufficient, False otherwise
        """
        if not text:
            return False
        
        # Remove whitespace and count actual characters
        stripped = text.replace(' ', '').replace('\n', '').replace('\t', '')
        char_count = len(stripped)
        
        # Check against threshold
        return char_count >= self.MIN_TEXT_THRESHOLD
    
    def get_page_count(self) -> int:
        """Get number of pages in PDF"""
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                return len(pdf.pages)
        except:
            return 0
