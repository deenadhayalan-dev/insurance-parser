"""
Value extractors for different data types (currency, dates, percentages, durations).
These are deterministic, pattern-based extractors with enhanced accuracy.
"""

import re
from typing import Optional, List, Tuple
from datetime import datetime
from decimal import Decimal
from dateutil import parser as date_parser

from ..utils.patterns import (
    CURRENCY_REGEX,
    DATE_REGEX,
    PERCENTAGE_REGEX,
    DURATION_REGEX,
    clean_currency_value
)


class CurrencyExtractor:
    """Extract currency values from text with enhanced context awareness"""
    
    @staticmethod
    def extract(text: str, context_window: int = 100) -> Optional[Decimal]:
        """
        Extract currency value from text with improved accuracy.
        Filters out policy numbers and unreasonable values.
        
        Args:
            text: Text to extract from
            context_window: Characters around match to consider
            
        Returns:
            Decimal value or None
        """
        if not text:
            return None
        
        # Priority 1: Try patterns with explicit currency symbols first
        currency_symbol_patterns = [
            r'₹\s*(\d+(?:,\d+)*(?:\.\d+)?)',  # ₹1,23,456.78
            r'`\s*(\d+(?:,\d+)*(?:\.\d+)?)',  # ` 500 (old Indian format using backtick as rupee symbol)
            r'Rs\.?\s*(\d+(?:,\d+)*(?:\.\d+)?)',  # Rs. 1,23,456
            r'INR\s*(\d+(?:,\d+)*(?:\.\d+)?)',  # INR 123456
            r'USD\s*(\d+(?:,\d+)*(?:\.\d+)?)',  # USD 100
            r'US\$\s*(\d+(?:,\d+)*(?:\.\d+)?)',  # US$ 100
        ]
        
        for pattern in currency_symbol_patterns:
            regex = re.compile(pattern, re.IGNORECASE)
            matches = regex.finditer(text)
            
            for match in matches:
                try:
                    value_str = match.group(1) if match.groups() else match.group(0)
                    cleaned = clean_currency_value(value_str)
                    value = Decimal(cleaned)
                    
                    # Enhanced validation
                    if CurrencyExtractor._is_valid_currency_value(value, text, match.start()):
                        return value
                except (ValueError, IndexError):
                    continue
        
        # Priority 2: Numbers with Indian formatting (commas)
        # But must be preceded/followed by currency context words
        indian_format_with_context = r'(?:rs|inr|amount|premium|rupees|total|sum)[\s:]*(\d+(?:,\d+)+(?:\.\d{2})?)'
        regex = re.compile(indian_format_with_context, re.IGNORECASE)
        matches = regex.finditer(text)
        
        for match in matches:
            try:
                value_str = match.group(1)
                cleaned = clean_currency_value(value_str)
                value = Decimal(cleaned)
                
                if CurrencyExtractor._is_valid_currency_value(value, text, match.start()):
                    return value
            except (ValueError, IndexError):
                continue
        
        # Priority 3: Plain numbers with commas (fallback, less reliable)
        comma_pattern = r'(\d+(?:,\d+)+(?:\.\d{2})?)'
        regex = re.compile(comma_pattern)
        matches = list(regex.finditer(text))
        
        # If multiple comma-formatted numbers, prefer the first one
        for match in matches[:1]:  # Only try first match
            try:
                value_str = match.group(1)
                cleaned = clean_currency_value(value_str)
                value = Decimal(cleaned)
                
                if CurrencyExtractor._is_valid_currency_value(value, text, match.start()):
                    return value
            except (ValueError, IndexError):
                continue
        
        # Priority 4: Plain numbers without commas (for table data without formatting)
        # Match 4-7 digit numbers that are likely currency amounts, not dates/IDs
        plain_number_pattern = r'\b(\d{4,7})(?:\.\d{1,2})?\b'
        regex = re.compile(plain_number_pattern)
        matches = list(regex.finditer(text))
        
        for match in matches:
            try:
                value_str = match.group(1)
                value = Decimal(value_str)
                
                # Stricter validation for plain numbers to avoid dates/IDs
                if CurrencyExtractor._is_valid_currency_value(value, text, match.start()):
                    # Additional check: not part of a date pattern
                    context_start = max(0, match.start() - 10)
                    context_end = min(len(text), match.end() + 10)
                    surrounding = text[context_start:context_end]
                    
                    # Skip if looks like date (nearby slashes or dashes)
                    if re.search(r'\d+[/-]\d+[/-]', surrounding):
                        continue
                    
                    # Skip if very close to other digits (might be part of longer ID)
                    if re.match(r'\d', text[match.start()-1:match.start()]) if match.start() > 0 else False:
                        continue
                    if re.match(r'\d', text[match.end():match.end()+1]) if match.end() < len(text) else False:
                        continue
                    
                    return value
            except (ValueError, IndexError):
                continue
        
        return None
    
    @staticmethod
    def _is_valid_currency_value(value: Decimal, text: str, position: int) -> bool:
        """
        Enhanced validation to filter out policy numbers, years, and invalid values.
        
        Args:
            value: Extracted value
            text: Full text context
            position: Position where value was found
            
        Returns:
            True if value is likely a currency amount, not a policy number/year
        """
        # Rule 1: Basic range check
        if not (100 <= value <= 1_00_00_00_000):
            return False
        
        # Rule 2: Stricter year filtering for 4-digit numbers
        # Years 1900-2099 are NOT currency values
        if len(str(int(value))) == 4:
            if 1900 <= value <= 2099:
                return False
        
        # Calculate document position for smart filtering
        doc_position_pct = (position / len(text)) * 100 if len(text) > 0 else 0
        
        # Look backwards for good policy detail labels (within 200 chars)
        # These indicate legitimate policy values, not comparison table values
        lookback_start = max(0, position - 200)
        lookback_text = text[lookback_start:position].lower()
        
        good_labels = [
            'basic premium', 'net premium', 'sum insured', 'sum assured',
            'premium details', 'coverage amount', 'insured amount',
            'policy premium', 'insurance premium', 'premium amount'
        ]
        
        has_good_label = any(label in lookback_text for label in good_labels)
        
        # Get context for checking (wider window for comparison detection)
        context_start = max(0, position - 150)
        context_end = min(len(text), position + 150)
        context = text[context_start:context_end].lower()
        
        # Rule 3: UNIVERSAL EXCLUSION - Policy/Certificate/ID numbers
        # Use smaller window (50 chars) as these are usually close-by
        id_context_start = max(0, position - 50)
        id_context_end = min(len(text), position + 50)
        id_context = text[id_context_start:id_context_end].lower()
        
        id_keywords = ['policy no', 'certificate no', 'policy number', 'cert no', 
                       'certificate number', 'proposal no', 'proposal number',
                       'policy :', 'certificate :', 'phone', 'mobile', 'contact']
        if any(keyword in id_context for keyword in id_keywords):
            return False
        
        # Rule 4: SMART COMPARISON TABLE FILTERING
        # If value has good label nearby, ALWAYS accept (even if late in document)
        if has_good_label:
            return True  # Good label = legitimate policy value
        
        # If no good label AND late in document (>60%), check for comparison keywords
        if doc_position_pct > 60:
            comparison_keywords = [
                'for all members',
                'all members of',
                'total premium for all members',
                'floater basis',
                'discount if any',
                'when each is',
                'the family is ₹',
                'the family is rs',
                'members\nof family',
                'of family\n',
            ]
            
            if any(keyword in context for keyword in comparison_keywords):
                return False  # Late position + comparison keyword = comparison table
        
        # Rule 2: Check if explicitly near policy number keywords
        # This is the PRIMARY filter for policy numbers
        # Use word boundaries to avoid false positives (e.g., "ID Card No" shouldn't trigger)
        exclusion_patterns = [
            r'\bpolicy\s+number\b',
            r'\bpolicy\s+no\b',
            r'\bcertificate\s+no\b',
            r'\bdocument\s+no\b',
            r'\bproposal\s+no\b',
            r'\bcertificate\s+number\b',
            r'\bserial\s+no\b',
            r'\bpolicy\s+id\b',        # Specific: policy ID only
            r'\bdocument\s+id\b',      # Specific: document ID only  
            r'\bcertificate\s+id\b',   # Specific: certificate ID only
        ]
        
        for pattern in exclusion_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return False  # Explicitly marked as policy/document number
        
        # Rule 3: For very large numbers (>50M), be more careful
        # But don't reject coverage amounts which can be 10L-1Cr
        if value > 50_000_000:
            # Check digit count - policy numbers usually have 12+ CONSECUTIVE digits without commas
            value_str = str(int(value))
            if len(value_str) >= 13:  # 13+ digits in a row = likely policy number
                # Must have STRONG currency indicators to accept
                currency_indicators = ['₹', 'rs', 'inr', 'premium', 'amount', 'sum insured', 'idv']
                has_strong_currency = any(ind in context for ind in currency_indicators)
                
                if not has_strong_currency:
                    return False
        
        # Rule 4: Numbers with 15+ digits are almost always policy/doc numbers
        value_str_full = str(int(value))
        if len(value_str_full) >= 15:
            return False
        
        # Rule 5: Check for decimal precision
        # Currency values often have .00 or .XX, policy numbers don't
        value_str_with_decimal = str(value)
        if '.' in value_str_with_decimal:
            # Has decimal - more likely to be currency
            return True
        
        # If we got here, it's probably valid
        return True
    
    @staticmethod
    def extract_all(text: str) -> List[Tuple[Decimal, int]]:
        """
        Extract all currency values with their positions.
        Improved to avoid false positives.
        
        Returns:
            List of (value, position) tuples
        """
        results = []
        
        # Pattern 1: With currency symbols (highest confidence)
        symbol_patterns = [
            r'₹\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            r'Rs\.?\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            r'INR\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
        ]
        
        for pattern_str in symbol_patterns:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            matches = pattern.finditer(text)
            
            for match in matches:
                try:
                    value_str = match.group(1) if match.groups() else match.group(0)
                    cleaned = clean_currency_value(value_str)
                    value = Decimal(cleaned)
                    
                    # Apply validation including comparison table filtering
                    if CurrencyExtractor._is_valid_currency_value(value, text, match.start()):
                        results.append((value, match.start()))
                except (ValueError, IndexError):
                    continue
        
        # Pattern 2: Indian comma format with context words
        context_pattern = r'(?:rs|inr|amount|premium|rupees|total|sum|gst|cgst|sgst|tax|idv)[\s:]+(\d+(?:,\d+)+(?:\.\d{2})?)'
        pattern = re.compile(context_pattern, re.IGNORECASE)
        matches = pattern.finditer(text)
        
        for match in matches:
            try:
                value_str = match.group(1)
                cleaned = clean_currency_value(value_str)
                value = Decimal(cleaned)
                
                # Apply validation including comparison table filtering
                if CurrencyExtractor._is_valid_currency_value(value, text, match.start()):
                    # Check if not already added
                    if not any(abs(v - value) < 1 and abs(p - match.start()) < 50 for v, p in results):
                        results.append((value, match.start()))
            except (ValueError, IndexError):
                continue
        
        # Pattern 3: Comma-separated numbers (only if has context nearby)
        # This is most error-prone, so be very conservative
        lines = text.split('\n')
        for line in lines:
            # Only extract from lines that look financial (have currency keywords)
            if any(keyword in line.lower() for keyword in ['premium', 'amount', 'total', 'sum', 'gst', 'tax', 'rs', 'inr', '₹']):
                comma_pattern = r'(\d+(?:,\d+)+(?:\.\d{2})?)'
                pattern = re.compile(comma_pattern)
                matches = pattern.finditer(line)
                
                for match in matches:
                    try:
                        value_str = match.group(1)
                        cleaned = clean_currency_value(value_str)
                        value = Decimal(cleaned)
                        
                        # Find position in original text
                        pos = text.find(line) + match.start()
                        
                        # Apply validation including comparison table filtering
                        if CurrencyExtractor._is_valid_currency_value(value, text, pos):
                            # Avoid duplicates
                            if not any(abs(v - value) < 1 and abs(p - pos) < 50 for v, p in results):
                                results.append((value, pos))
                    except (ValueError, IndexError):
                        continue
        
        # Sort by position and remove duplicates
        results.sort(key=lambda x: x[1])
        
        # Deduplicate: if same value appears within 20 chars, keep first
        deduplicated = []
        for value, pos in results:
            if not any(abs(v - value) < 1 and abs(p - pos) < 20 for v, p in deduplicated):
                deduplicated.append((value, pos))
        
        return deduplicated


class DateExtractor:
    """Extract dates from text"""
    
    # Month name to number mapping
    MONTH_MAP = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12
    }
    
    @staticmethod
    def extract(text: str) -> Optional[datetime]:
        """
        Extract date from text.
        
        Args:
            text: Text to extract from
            
        Returns:
            datetime object or None
        """
        if not text:
            return None
        
        # Try pattern-based extraction first (more reliable)
        for pattern in DATE_REGEX:
            match = pattern.search(text)
            if match:
                date_obj = DateExtractor._parse_date_match(match, pattern.pattern)
                if date_obj:
                    return date_obj
        
        # Fallback to dateutil parser (more flexible but can be wrong)
        # Only use for short text snippets to avoid extracting garbage
        # STRICT: Reject fuzzy parseif text is too ambiguous (e.g., just "to" or "from")
        if len(text) < 100:
            # Skip if text is just a generic label without actual date info
            text_lower = text.lower().strip()
            ambiguous_labels = ['to', 'from', 'date', 'period', 'term', 'for', 'on', 'of']
            
            # If text is ONLY a generic label (or very short), don't fuzzy parse
            if text_lower in ambiguous_labels or len(text_lower) < 5:
                return None
            
            # If text is just a label + number (e.g., "to 1", "from 2"), reject  
            if re.match(r'^(?:to|from|date|period)\s*\d{1,2}$', text_lower):
                return None
            
            try:
                parsed_date = date_parser.parse(text, fuzzy=True, dayfirst=True)
                # Validate year is reasonable
                if 1990 <= parsed_date.year <= 2035:
                    # Additional validation: Reject if parsed date is too close to current date
                    # (likely constructed from current date when input was ambiguous)
                    from datetime import datetime as dt
                    current_date = dt.now().date()
                    parsed_date_only = parsed_date.date()
                    
                    # If fuzzy parser returned current year/month but input didn't contain them,
                    # it's likely a false positive
                    year_in_text = str(parsed_date.year) in text
                    month_in_text = str(parsed_date.month) in text or parsed_date.strftime('%b').lower() in text_lower
                    
                    # Reject if date components weren't in the original text
                    if not year_in_text and not month_in_text:
                        return None
                        
                    return parsed_date
            except:
                pass
        
        return None
    
    @staticmethod
    def _parse_date_match(match: re.Match, pattern: str) -> Optional[datetime]:
        """Parse date from regex match based on pattern"""
        try:
            groups = match.groups()
            
            # DD/MM/YYYY or DD-MM-YYYY
            if len(groups) == 3 and groups[0].isdigit() and groups[1].isdigit():
                day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                
                # Check if it's DD/MM/YYYY or YYYY/MM/DD
                if year > 2000 and day <= 31 and month <= 12:
                    # Validate reasonable year range for insurance policies
                    if not (1990 <= year <= 2035):
                        return None
                    return datetime(year, month, day)
                elif int(groups[0]) > 2000:  # YYYY-MM-DD
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    # Validate reasonable year range
                    if not (1990 <= year <= 2035):
                        return None
                    return datetime(year, month, day)
            
            # DD Month YYYY
            elif len(groups) == 3:
                day = int(groups[0])
                month_str = groups[1].lower()
                year = int(groups[2])
                
                # Validate reasonable year range
                if not (1990 <= year <= 2035):
                    return None
                
                # Get month number
                month = DateExtractor.MONTH_MAP.get(month_str)
                if month:
                    return datetime(year, month, day)
        
        except (ValueError, IndexError):
            return None
        
        return None
    
    @staticmethod
    def extract_all(text: str) -> List[Tuple[datetime, int]]:
        """Extract all dates with their positions"""
        results = []
        
        for pattern in DATE_REGEX:
            matches = pattern.finditer(text)
            
            for match in matches:
                date_obj = DateExtractor._parse_date_match(match, pattern.pattern)
                if date_obj:
                    results.append((date_obj, match.start()))
        
        # Sort by position
        results.sort(key=lambda x: x[1])
        return results


class PercentageExtractor:
    """Extract percentage values from text"""
    
    @staticmethod
    def extract(text: str) -> Optional[Decimal]:
        """
        Extract percentage value from text.
        
        Args:
            text: Text to extract from
            
        Returns:
            Decimal percentage or None
        """
        if not text:
            return None
        
        for pattern in PERCENTAGE_REGEX:
            match = pattern.search(text)
            if match:
                try:
                    value_str = match.group(1)
                    value = Decimal(value_str)
                    
                    # Validate reasonable percentage (0-100)
                    if 0 <= value <= 100:
                        return value
                
                except (ValueError, IndexError):
                    continue
        
        return None
    
    @staticmethod
    def extract_all(text: str) -> List[Tuple[Decimal, int]]:
        """Extract all percentage values with positions"""
        results = []
        
        for pattern in PERCENTAGE_REGEX:
            matches = pattern.finditer(text)
            
            for match in matches:
                try:
                    value_str = match.group(1)
                    value = Decimal(value_str)
                    
                    if 0 <= value <= 100:
                        results.append((value, match.start()))
                
                except (ValueError, IndexError):
                    continue
        
        results.sort(key=lambda x: x[1])
        return results


class DurationExtractor:
    """Extract duration values from text"""
    
    @staticmethod
    def extract(text: str) -> Optional[Tuple[int, str]]:
        """
        Extract duration from text.
        
        Args:
            text: Text to extract from
            
        Returns:
            Tuple of (value, unit) or None
        """
        if not text:
            return None
        
        for pattern in DURATION_REGEX:
            match = pattern.search(text)
            if match:
                try:
                    value = int(match.group(1))
                    
                    # Determine unit from pattern
                    pattern_str = pattern.pattern
                    if 'year' in pattern_str:
                        unit = 'years'
                    elif 'month' in pattern_str:
                        unit = 'months'
                    elif 'day' in pattern_str:
                        unit = 'days'
                    else:
                        unit = 'unknown'
                    
                    return (value, unit)
                
                except (ValueError, IndexError):
                    continue
        
        return None
