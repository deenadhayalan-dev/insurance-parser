"""
Enhanced field-specific extraction strategies.
Handles special cases like tax aggregation, deductible validation.
"""

from typing import Optional, List, Tuple
from decimal import Decimal


class TaxAggregator:
    """
    Handles tax component aggregation (CGST + SGST + IGST = Total Tax).
    Many insurance documents split GST into components.
    """
    
    @staticmethod
    def aggregate_tax_components(text: str, currency_extractor) -> Optional[Decimal]:
        """
        Find and aggregate tax components (CGST, SGST, IGST).
        
        Args:
            text: Document text
            currency_extractor: CurrencyExtractor instance
            
        Returns:
            Aggregated tax amount or None
        """
        import re
        
        tax_components = {}
        
        # Patterns for tax components - look for colon or currency symbol, then the value
        # Handles various formats:
        # - "CGST @9% :Rs 1935/-" (with Rs/₹)
        # - "cgst @9% : 2,230 / -" (without Rs/₹, with spaces)
        # - "CGST@9%:1,935" (minimal spacing)
        # - "IGST @ 18% : 74.97" (standalone IGST for inter-state)
        # - "IGST Total Tax ... 74.97" (table format without colon)
        # Pattern finds the label, skips to ":" or "₹", then captures the number
        patterns = {
            'cgst': r'cgst\b.*?[:₹]\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            'sgst': r'sgst\b.*?[:₹]\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            'utgst': r'utgst\b.*?[:₹]\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            'igst': r'igst\b.*?[:₹]\s*(\d+(?:,\d+)*(?:\.\d{2})?)',  # Standalone IGST for inter-state
        }
        
        text_lower = text.lower()
        
        for tax_type, pattern in patterns.items():
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            values = []
            
            for match in matches:
                try:
                    value_str = match.group(1)
                    cleaned = value_str.replace(',', '')
                    value = Decimal(cleaned)
                    
                    if 10 <= value <= 100000:  # Reasonable tax range
                        values.append(value)
                except:
                    continue
            
            if values:
                # If multiple values found, take the first one
                tax_components[tax_type] = values[0]
        
        # Special fallback for table-based IGST (without colon/:  ₹)
        # Format: "IGST Total Tax ... 74.97" or "IGST\n...\n74.97"
        if 'igst' not in tax_components and 'igst' in text_lower:
            # For table format: "igst total tax...\n% `\n416.5 18 74.97 491"
            # Find IGST percentage (10-20%) followed by tax amount
            # Pattern: small percentage (1-2 digits) then decimal value (tax)
            igst_table = r'igst[^\n]*\n[^\n]*\n[^\d]*\d+(?:\.\d+)?\s+(\d{1,2})\s+(\d+(?:,\d+)*(?:\.\d{2})?)'
            table_match = re.search(igst_table, text_lower, re.IGNORECASE)
            if table_match:
                try:
                    pct = int(table_match.group(1))  # Should be around 18%
                    tax_str = table_match.group(2).replace(',', '')
                    tax_value = Decimal(tax_str)
                    # Verify: percentage should be 10-20%, tax should be reasonable
                    if 10 <= pct <= 30 and 10 <= tax_value <= 100000:
                        tax_components['igst'] = tax_value
                except:
                    pass
        
        # Aggregate: CGST + SGST OR UTGST + SGST OR IGST alone
        total_tax = Decimal('0')
        
        if 'cgst' in tax_components and 'sgst' in tax_components:
            total_tax = tax_components['cgst'] + tax_components['sgst']
        elif 'utgst' in tax_components and 'sgst' in tax_components:
            total_tax = tax_components['utgst'] + tax_components['sgst']
        elif 'igst' in tax_components:
            total_tax = tax_components['igst']
        
        return total_tax if total_tax > 0 else None


class DeductibleValidator:
    """
    Validates that an extracted value is actually a deductible/excess,
    not a premium or other amount.
    """
    
    @staticmethod
    def is_valid_deductible(
        value: Decimal,
        text_context: str,
        other_amounts: dict
    ) -> bool:
        """
        Validate if a value is actually a deductible.
        
        Args:
            value: Extracted value
            text_context: Surrounding text
            other_amounts: Dictionary of other extracted amounts
            
        Returns:
            True if likely a deductible
        """
        # Rule 1: Deductible should not match premium, coverage, or tax
        if other_amounts:
            for key, amount in other_amounts.items():
                if amount and key != 'deductible_amount':
                    if abs(amount - value) < 10:  # Same value
                        return False
        
        # Rule 2: Deductible is usually smaller than premium
        # Typical range: ₹100 to ₹50,000
        if not (100 <= value <= 50000):
            return False
        
        # Rule 3: Context should contain deductible-related keywords
        context_lower = text_context.lower()
        deductible_keywords = [
            'deductible', 'excess', 'voluntary', 'compulsory',
            'deduct', 'waiver', 'own damage deductible'
        ]
        
        has_deductible_context = any(keyword in context_lower for keyword in deductible_keywords)
        
        # Rule 4: Should NOT have premium/tax context
        anti_keywords = [
            'premium', 'gst', 'tax', 'total', 'payable',
            'sum insured', 'coverage'
        ]
        
        # If context has strong anti-indicators, reject
        strong_anti_match = any(
            keyword in context_lower[:30]  # Check first 30 chars of context
            for keyword in ['premium', 'total', 'gst']
        )
        
        if strong_anti_match and not has_deductible_context:
            return False
        
        # Rule 5: Common deductible values (heuristic)
        common_deductibles = [
            500, 1000, 1500, 2000, 2500, 3000, 5000,
            7500, 10000, 15000, 20000, 25000, 50000
        ]
        
        # Exact match to common values boosts confidence
        is_common_value = any(abs(value - common) < 10 for common in common_deductibles)
        
        # Final decision: must have context OR be common value
        return has_deductible_context or is_common_value


class FieldDisambiguator:
    """
    Disambiguates between similar fields (e.g., total premium vs coverage amount).
    """
    
    @staticmethod
    def disambiguate_currency_fields(
        candidates: dict,
        text: str
    ) -> dict:
        """
        When multiple currency fields extract the same value,
        determine which field it actually belongs to.
        
        Args:
            candidates: Dict of {field_name: extracted_value}
            text: Full document text
            
        Returns:
            Corrected candidates dict
        """
        # Common issue: total_premium and coverage_amount getting same value
        if (candidates.get('total_premium') and 
            candidates.get('coverage_amount') and
            abs(candidates['total_premium'] - candidates['coverage_amount']) < 100):
            
            # They extracted the same value - figure out which is which
            # Usually coverage_amount >> total_premium in magnitude
            value = candidates['total_premium']
            
            # If value is > 100000, more likely coverage than premium
            if value > 100000:
                candidates['coverage_amount'] = value
                candidates['total_premium'] = None
            else:
                # If < 100000, more likely premium
                candidates['total_premium'] = value
                candidates['coverage_amount'] = None
        
        return candidates
