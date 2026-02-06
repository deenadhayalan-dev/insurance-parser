"""
Regular expression patterns for value extraction.
Patterns are designed to be flexible and handle various formats.
"""

import re

# CURRENCY PATTERNS
# Handles Indian Rupee formats with various separators and symbols

CURRENCY_PATTERNS = [
    # ₹1,23,456.78 or ₹123456.78
    r'₹\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
    # Rs. 1,23,456.78 or Rs 123456
    r'Rs\.?\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
    # INR 123456.78
    r'INR\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
    # 1,23,456.78 (plain number with commas)
    r'(\d+(?:,\d+)+(?:\.\d{2})?)',
    # 123456.78 or 123456
    r'(\d+(?:\.\d{2})?)',
    # 1,23,456/- format
    r'(\d+(?:,\d+)+)/-',
]

CURRENCY_REGEX = [re.compile(pattern, re.IGNORECASE) for pattern in CURRENCY_PATTERNS]


# DATE PATTERNS
# Handles various date formats common in Indian documents

DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY
    r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',
    # DD.MM.YYYY
    r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b',
    # YYYY-MM-DD (ISO format)
    r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',
    # DD MMM YYYY (e.g., 15 Jan 2024)
    r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})\b',
    # DD Month YYYY (e.g., 15 January 2024)
    r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b',
]

DATE_REGEX = [re.compile(pattern, re.IGNORECASE) for pattern in DATE_PATTERNS]


# PERCENTAGE PATTERNS

PERCENTAGE_PATTERNS = [
    # 10% or 10 %
    r'(\d+(?:\.\d+)?)\s*%',
    # 10 percent
    r'(\d+(?:\.\d+)?)\s+percent',
    # 10 percentage
    r'(\d+(?:\.\d+)?)\s+percentage',
]

PERCENTAGE_REGEX = [re.compile(pattern, re.IGNORECASE) for pattern in PERCENTAGE_PATTERNS]


# DURATION PATTERNS

DURATION_PATTERNS = [
    # 1 year, 2 years
    r'(\d+)\s+years?',
    # 12 months, 1 month
    r'(\d+)\s+months?',
    # 365 days
    r'(\d+)\s+days?',
]

DURATION_REGEX = [re.compile(pattern, re.IGNORECASE) for pattern in DURATION_PATTERNS]


# NOISE WORDS TO FILTER (common non-financial terms)

NOISE_WORDS = {
    'page', 'annexure', 'schedule', 'note', 'notes', 'terms', 'conditions',
    'exclusions', 'inclusions', 'clauses', 'definitions', 'disclaimer',
    'signature', 'authorized', 'signatory', 'stamp', 'seal',
    'customer', 'insured', 'policyholder', 'beneficiary', 'nominee',
    'address', 'contact', 'phone', 'email', 'mobile',
}


# TABLE DETECTION PATTERNS
# Help identify tabular structures

TABLE_INDICATORS = [
    r'\|',  # Pipe separator
    r'\t{2,}',  # Multiple tabs
    r'\s{4,}',  # Multiple spaces (likely columns)
]

TABLE_INDICATOR_REGEX = [re.compile(pattern) for pattern in TABLE_INDICATORS]


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent processing.
    - Lowercase
    - Standardize separators
    - Preserve whitespace structure for table extraction
    """
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Standardize common separators (add spaces around them for consistent matching)
    text = text.replace(':', ' : ')
    text = text.replace('-', ' - ')
    
    # Clean up excessive spaces (more than 10 consecutive) but preserve table structure
    # This removes page-width separators while keeping column gaps
    text = re.sub(r' {10,}', '    ', text)  # Replace 10+ spaces with exactly 4 (table column gap)
    
    # Strip trailing spaces from each line
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    
    return text


def clean_currency_value(value_str: str) -> str:
    """Remove currency symbols and formatting for parsing"""
    if not value_str:
        return "0"
    
    # Remove common currency symbols and text
    value_str = value_str.replace('₹', '')
    value_str = value_str.replace('Rs.', '')
    value_str = value_str.replace('Rs', '')
    value_str = value_str.replace('INR', '')
    value_str = value_str.replace('/-', '')
    
    # Remove whitespace
    value_str = value_str.strip()
    
    # Remove commas (Indian numbering system uses them)
    value_str = value_str.replace(',', '')
    
    return value_str


def is_likely_table_row(text: str) -> bool:
    """Detect if text line is likely part of a table"""
    return any(regex.search(text) for regex in TABLE_INDICATOR_REGEX)
