"""
Table-aware extraction for handling columnar data in insurance documents.
Priority 1 fix for Iteration 2.
"""

import re
from typing import Optional, List, Tuple, Dict
from decimal import Decimal


class TableExtractor:
    """
    Detects and extracts values from table structures.
    Handles common insurance document table formats.
    """
    
    @staticmethod
    def detect_table_row(line: str) -> bool:
        """
        Detect if a line is part of a table structure.
        
        Tables typically have:
        - Multiple whitespace gaps (columns)
        - Multiple numeric values
        - Aligned formatting
        
        Args:
            line: Text line
            
        Returns:
            True if likely a table row
        """
        # Check for multiple large whitespace gaps
        gaps = re.findall(r'\s{3,}', line)
        if len(gaps) >= 2:
            return True
        
        # Check for multiple tab characters
        if line.count('\t') >= 2:
            return True
        
        # Check for pipe separators
        if '|' in line and line.count('|') >= 2:
            return True
        
        return False
    
    @staticmethod
    def extract_table_columns(line: str) -> List[str]:
        """
        Split a table row into columns.
        
        Args:
            line: Table row text
            
        Returns:
            List of column values
        """
        # Try pipe-separated first
        if '|' in line:
            columns = [col.strip() for col in line.split('|')]
            return [col for col in columns if col]
        
        # Try tab-separated
        if '\t' in line:
            columns = [col.strip() for col in line.split('\t')]
            return [col for col in columns if col]
        
        # Try multiple-space separated (most common)
        # Split on 3+ spaces
        columns = re.split(r'\s{3,}', line)
        return [col.strip() for col in columns if col.strip()]
    
    @staticmethod
    def find_value_in_table(
        text: str,
        label: str,
        label_position: int,
        value_type: str = 'currency'
    ) -> Optional[Decimal]:
        """
        Extract value from table when label is found in table structure.
        ROBUST: Re-finds label around reported position to handle offset errors.
        
        Args:
            text: Full document text
            label: Label to search for  
            label_position: APPROXIMATE position where label was found
            value_type: Type of value to extract
            
        Returns:
            Extracted value or None
        """
        # ROBUST APPROACH: Search for label near reported position
        # Don't search too widely - stay within reasonable proximity
        import re
        import sys
        
        # Search in a moderate window (positions can shift due to normalization)
        search_start = max(0, label_position - 100)
        search_end = min(len(text), label_position + 200)
        search_region = text[search_start:search_end]
        
        # Find all matches of the label in this region
        all_matches = list(re.finditer(re.escape(label), search_region, re.IGNORECASE))
        
        if not all_matches:
            return None  # Label not found in expected region
        
        # Prioritize matches closest to the reported position
        all_matches.sort(key=lambda m: abs(search_start + m.start() - label_position))
        
        # Try each match (closest first) until we find one in a table that gives a valid value
        for match in all_matches:
            actual_label_pos = search_start + match.start()
            
            # Get the line containing THIS match
            line_start = text.rfind('\n', 0, actual_label_pos) + 1
            line_end = text.find('\n', actual_label_pos)
            if line_end == -1:
                line_end = len(text)
            
            label_line = text[line_start:line_end]
            
            # Check if this looks like a table header line
            is_header = TableExtractor._is_table_header(label_line)
            
            if is_header:
                # Try to extract value from this table
                value = TableExtractor._extract_from_table_column(
                    text, label, label_line, line_end, value_type
                )
                if value:  # Success!
                    return value
                # Otherwise continue to next match
            
            # Also try as a DATA ROW (label might be in data, not header)
            elif TableExtractor.detect_table_row(label_line):
                columns = TableExtractor.extract_table_columns(label_line)
                if columns:
                    label_lower = label.lower()
                    for idx, col in enumerate(columns):
                        if label_lower in col.lower():
                            # Try this column and next
                            for col_idx in [idx, idx + 1]:
                                if col_idx < len(columns):
                                    if value_type == 'currency':
                                        value = TableExtractor._extract_currency_from_text(columns[col_idx])
                                        if value:
                                            return value
                            break
        
        # None of the matches worked
        return None
    
    @staticmethod
    def _is_table_header(line: str) -> bool:
        """
        Detect if a line is a table header.
        Headers have multiple text labels, fewer numeric values.
        Be conservative - prefer treating ambiguous lines as data.
        
        Args:
            line: Text line
            
        Returns:
            True if likely a header
        """
        # Count words vs numbers
        words = len(re.findall(r'[a-zA-Z]{3,}', line))
        numbers = len(re.findall(r'\b\d{4,}\b', line))  # Count significant numbers (4+ digits)
        
        # If has significant numbers (like 2000000), probably data row not header
        if numbers >= 1:
            return False
        
        # Headers typically have more words than numbers
        if words >= 3:
            return True
        
        # Check for common header keywords
        header_keywords = ['name', 'date', 'amount', 'no', 'number', 'type', 
                          'description', 'premium', 'coverage', 'sum', 'total',
                          'insured', 'assured', 'period', 'value']
        
        line_lower = line.lower()
        keyword_count = sum(1 for kw in header_keywords if kw in line_lower)
        
        if keyword_count >= 2:
            return True
        
        return False
    
    @staticmethod
    def _extract_from_table_column(
        text: str,
        label: str,
        header_line: str,
        header_end_pos: int,
        value_type: str
    ) -> Optional[Decimal]:
        """
        Extract value from a table column by finding the label in the header.
        Uses column-based alignment when possible, falls back to context extraction.
        
        Args:
            text: Full document text
            label: Column header label
            header_line: The header line text
            header_end_pos: Position where header line ends
            value_type: Type of value to extract
            
        Returns:
            Extracted value from first data row
        """
        # Try column-based extraction first
        header_columns = TableExtractor.extract_table_columns(header_line)
        
        # Column splitting only works for properly formatted tables with whitespace gaps
        # If we got <= 2 columns from a line with many words, column splitting failed
        # (linearized tables have single spaces between columns, can't be split reliably)
        word_count = len([w for w in header_line.split() if len(w) > 2])
        
        if header_columns and len(header_columns) >= 3 and len(header_columns) >= word_count * 0.5:
            # Find which column contains the label
            label_lower = label.lower()
            label_col_idx = None
            
            for idx, col in enumerate(header_columns):
                if label_lower in col.lower():
                    label_col_idx = idx
                    break
            
            if label_col_idx is not None:
                # Look for data rows
                current_pos = header_end_pos + 1
                for _ in range(5):
                    next_line_end = text.find('\n', current_pos)
                    if next_line_end == -1:
                        next_line_end = len(text)
                    
                    data_line = text[current_pos:next_line_end]
                    
                    if not data_line.strip() or TableExtractor._is_table_header(data_line):
                        current_pos = next_line_end + 1
                        continue
                    
                    # Extract columns from data line
                    data_columns = TableExtractor.extract_table_columns(data_line)
                    
                    if data_columns and label_col_idx < len(data_columns):
                        column_value = data_columns[label_col_idx]
                        
                        if value_type == 'currency':
                            value = TableExtractor._extract_currency_from_text(column_value)
                            if value:  # Let field-specific validators handle minimum thresholds
                                return value
                    
                    current_pos = next_line_end + 1
        
        # FALLBACK: Column splitting didn't work
        # For single-space-separated tables, column-based extraction is unreliable
        # Return None and let pipeline's other extraction methods handle it
        # (same-line extraction, next-line extraction, or context window)
        return None
    
    @ staticmethod
    @staticmethod
    def _extract_first_significant_currency(text: str) -> Optional[Decimal]:
        """
        Extract the FIRST significant currency value from text.
        In table columns, the relevant value is usually first, not necessarily largest.
        Handles real-world variations where values can be anywhere in the region.
        """
        import re
        
        # Find all numbers (unformatted digits only)
        pattern = r'\b(\d{4,})\b'  # 4+ consecutive digits
        matches = re.findall(pattern, text)
        
        for match in matches:
            try:
                value = Decimal(match)
                num_digits = len(match)
                
                # Skip very long numbers (8+ = likely IDs/document numbers)
                if num_digits > 7:
                    continue
                
                # Skip years (4 digits starting with 19/20)
                if num_digits == 4 and (match.startswith('19') or match.startswith('20')):
                    continue
                    
                # Reasonable currency range - lowered to 1000 to catch smaller amounts
                if 1000 <= value <= 1_00_00_00_000:
                    return value  # Return FIRST valid value
            except:
                continue
        
        return None
    
    @staticmethod
    def extract_table_values(
        text: str,
        header_keywords: List[str]
    ) -> Dict[str, Decimal]:
        """
        Extract all values from a table with given headers.
        
        Example:
        Table:
            Basic Premium   IGST %   Total Tax   Total Premium
               416.5         18       74.97          491
        
        Args:
            text: Document text
            header_keywords: List of header keywords to find
            
        Returns:
            Dictionary mapping keywords to extracted values
        """
        lines = text.split('\n')
        results = {}
        
        # Find header row
        header_row_idx = None
        for idx, line in enumerate(lines):
            line_lower = line.lower()
            # If line contains multiple header keywords, it's likely the header
            matches = sum(1 for keyword in header_keywords if keyword.lower() in line_lower)
            if matches >= 2 and TableExtractor.detect_table_row(line):
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            return results
        
        # Get columns from header
        header_line = lines[header_row_idx]
        header_columns = TableExtractor.extract_table_columns(header_line)
        
        # Get values from next row (data row)
        if header_row_idx + 1 < len(lines):
            data_line = lines[header_row_idx + 1]
            data_columns = TableExtractor.extract_table_columns(data_line)
            
            # Map headers to values
            for h_idx, header in enumerate(header_columns):
                if h_idx < len(data_columns):
                    value = TableExtractor._extract_currency_from_text(data_columns[h_idx])
                    if value:
                        # Find matching keyword
                        for keyword in header_keywords:
                            if keyword.lower() in header.lower():
                                results[keyword] = value
                                break
        
        return results
    
    @staticmethod
    def _extract_currency_from_text(text: str) -> Optional[Decimal]:
        """Extract currency value from text using CurrencyExtractor for consistency"""
        from .extractors import CurrencyExtractor
        
        # Use the main CurrencyExtractor which has proper validation
        # Note: validation won't have full document context here, but will still
        # filter out years, policy numbers, etc.
        return CurrencyExtractor.extract(text)
