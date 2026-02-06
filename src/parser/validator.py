"""
Validator - performs context-aware validation of extracted values.
"""

from typing import Optional, List, Tuple
from decimal import Decimal
from datetime import datetime


class ContextValidator:
    """
    Validates extracted values using context and business rules.
    Helps avoid false positives and ensures semantic correctness.
    """
    
    def __init__(self):
        # Financial business rules
        self.MAX_COVERAGE = Decimal('100000000')  # ₹10 crores max reasonable coverage
        self.MIN_COVERAGE = Decimal('1000')  # ₹1000 min
        self.MAX_PREMIUM = Decimal('10000000')  # ₹1 crore max reasonable premium
        self.MIN_PREMIUM = Decimal('100')  # ₹100 min
    
    def validate_currency_value(
        self, 
        value: Decimal, 
        concept: str,
        context: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a currency value for a specific concept.
        
        Args:
            value: Currency value
            concept: Concept name (e.g., 'total_premium')
            context: Surrounding text
            
        Returns:
            (is_valid, reason)
        """
        if value is None:
            return False, "Value is None"
        
        # Premium validation
        if 'premium' in concept:
            if value < self.MIN_PREMIUM:
                return False, f"Premium too low: ₹{value}"
            if value > self.MAX_PREMIUM:
                return False, f"Premium too high: ₹{value}"
        
        # Coverage validation
        if 'coverage' in concept or 'sum' in concept:
            if value < self.MIN_COVERAGE:
                return False, f"Coverage too low: ₹{value}"
            if value > self.MAX_COVERAGE:
                return False, f"Coverage too high: ₹{value}"
        
        # Deductible validation
        if 'deductible' in concept or 'excess' in concept:
            if value > Decimal('1000000'):  # Max ₹10 lakhs deductible
                return False, f"Deductible too high: ₹{value}"
        
        return True, None
    
    def validate_date_value(
        self,
        value: datetime,
        concept: str,
        context: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a date value for a specific concept.
        
        Args:
            value: Date value
            concept: Concept name
            context: Surrounding text
            
        Returns:
            (is_valid, reason)
        """
        if value is None:
            return False, "Date is None"
        
        # Check reasonable date range (2000-2050)
        if value.year < 2000 or value.year > 2050:
            return False, f"Date out of reasonable range: {value.year}"
        
        return True, None
    
    def validate_date_pair(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate policy start and end dates.
        
        Args:
            start_date: Policy start date
            end_date: Policy end date
            
        Returns:
            (is_valid, reason)
        """
        if start_date and end_date:
            if end_date <= start_date:
                return False, "End date must be after start date"
            
            # Check reasonable duration (max 100 years for life insurance)
            duration = (end_date - start_date).days
            if duration > 365 * 100:
                return False, f"Policy duration too long: {duration} days"
        
        return True, None
    
    def validate_premium_components(
        self,
        base: Optional[Decimal],
        tax: Optional[Decimal],
        total: Optional[Decimal]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate premium component relationship: base + tax = total.
        
        Args:
            base: Base premium
            tax: Tax amount
            total: Total premium
            
        Returns:
            (is_valid, reason)
        """
        if base and tax and total:
            calculated_total = base + tax
            
            # Allow small tolerance for rounding errors (₹10)
            tolerance = Decimal('10')
            difference = abs(calculated_total - total)
            
            if difference > tolerance:
                return False, f"Premium mismatch: {base} + {tax} ≠ {total}"
        
        return True, None
    
    def validate_percentage(
        self,
        value: Decimal,
        concept: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate percentage value.
        
        Args:
            value: Percentage value
            concept: Concept name
            
        Returns:
            (is_valid, reason)
        """
        if value is None:
            return False, "Percentage is None"
        
        if value < 0 or value > 100:
            return False, f"Percentage out of range: {value}%"
        
        # Co-pay specific validation
        if 'copay' in concept or 'co_pay' in concept:
            if value > 50:  # Unusual to have >50% copay
                return False, f"Co-pay unusually high: {value}%"
        
        return True, None
    
    def select_best_candidate(
        self,
        candidates: List[Tuple[Decimal, int]],
        concept: str,
        context_positions: List[int]
    ) -> Optional[Decimal]:
        """
        Select best value from multiple candidates using proximity.
        
        Args:
            candidates: List of (value, position) tuples
            concept: Concept name
            context_positions: Positions where concept was mentioned
            
        Returns:
            Best value or None
        """
        if not candidates:
            return None
        
        if len(candidates) == 1:
            return candidates[0][0]
        
        # If we have context positions, pick closest candidate
        if context_positions:
            best_candidate = None
            min_distance = float('inf')
            
            for value, value_pos in candidates:
                for context_pos in context_positions:
                    distance = abs(value_pos - context_pos)
                    if distance < min_distance:
                        min_distance = distance
                        best_candidate = value
            
            return best_candidate
        
        # No context: use heuristics based on concept
        if 'total' in concept or 'gross' in concept:
            # Pick largest value for total/gross
            return max(candidates, key=lambda x: x[0])[0]
        elif 'base' in concept or 'net' in concept:
            # Pick smaller value for base/net (before tax)
            return min(candidates, key=lambda x: x[0])[0]
        else:
            # Default: pick first occurrence
            return candidates[0][0]
