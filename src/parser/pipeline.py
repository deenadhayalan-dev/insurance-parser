"""
Main parsing pipeline - orchestrates the complete extraction process.
This is the core deterministic, semantic parsing system.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from decimal import Decimal

from ..models.schemas import (
    ParsedInsuranceDocument,
    FieldExtraction,
    ExtractionConfidence,
    InsuranceType
)
from .concept_detector import ConceptDetector
from .extractors import (
    CurrencyExtractor,
    DateExtractor,
    PercentageExtractor,
    DurationExtractor
)
from .normalizer import TextNormalizer
from .validator import ContextValidator
from .field_strategies import TaxAggregator, DeductibleValidator, FieldDisambiguator
from .table_extractor import TableExtractor


class ParsingPipeline:
    """
    Multi-stage semantic parsing pipeline for insurance documents.
    
    Pipeline stages:
    1. Text normalization
    2. Concept detection (find financial concept mentions)
    3. Candidate value extraction (extract all possible values)
    4. Context validation (filter using proximity and business rules)
    5. Confidence scoring
    6. Canonical output generation
    """
    
    def __init__(self, vocabulary_path: Optional[str] = None):
        """
        Initialize pipeline with components.
        
        Args:
            vocabulary_path: Optional custom vocabulary path
        """
        self.concept_detector = ConceptDetector(vocabulary_path)
        self.normalizer = TextNormalizer()
        self.validator = ContextValidator()
        
        self.currency_extractor = CurrencyExtractor()
        self.date_extractor = DateExtractor()
        self.percentage_extractor = PercentageExtractor()
        self.duration_extractor = DurationExtractor()
    
    def parse(self, text: str, source_file: Optional[str] = None, is_ocr: bool = False) -> ParsedInsuranceDocument:
        """
        Execute complete parsing pipeline.
        
        Args:
            text: Extracted document text
            source_file: Source filename
            is_ocr: Whether text was OCR-extracted
            
        Returns:
            ParsedInsuranceDocument with extracted fields
        """
        # Initialize output document
        result = ParsedInsuranceDocument(
            source_file=source_file,
            is_ocr_processed=is_ocr
        )
        
        # Stage 1: Normalize text
        normalized_text = self.normalizer.normalize(text)
        
        if not normalized_text:
            result.parsing_warnings.append("No text to parse")
            return result
        
        # Stage 2: Detect all concept mentions in document
        concept_candidates = self.concept_detector.find_concept_candidates(normalized_text)
        
        # Stage 3: For each financial concept, extract values
        concept_map = self._group_candidates_by_concept(concept_candidates)
        
        for concept_name in self.concept_detector.get_all_concept_names():
            # Get positions where this concept was mentioned
            mention_positions = concept_map.get(concept_name, [])
            
            # Extract field based on type
            field_extraction = self._extract_field(
                concept_name,
                normalized_text,
                mention_positions
            )
            
            # Set field in result
            setattr(result, concept_name, field_extraction)
        
        # Stage 4: Post-processing validations
        self._validate_cross_field_constraints(result)
        
        # Stage 5: Infer document type
        result.document_type = self._infer_document_type(result)
        
        return result
    
    def _group_candidates_by_concept(
        self,
        candidates: List[Tuple[str, int, str]]
    ) -> Dict[str, List[Tuple[int, str]]]:
        """Group concept candidates by concept name"""
        grouped = {}
        
        for concept_name, position, matched_label in candidates:
            if concept_name not in grouped:
                grouped[concept_name] = []
            grouped[concept_name].append((position, matched_label))
        
        return grouped
    
    def _extract_field(
        self,
        concept_name: str,
        text: str,
        mention_positions: List[Tuple[int, str]]
    ) -> FieldExtraction:
        """
        Extract field value for a specific concept with field-specific strategies.
        
        Args:
            concept_name: Canonical concept name
            text: Full document text
            mention_positions: List of (position, label) where concept was mentioned
            
        Returns:
            FieldExtraction with value and metadata
        """
        value_type = self.concept_detector.get_concept_value_type(concept_name)
        
        if not value_type:
            return FieldExtraction(confidence=ExtractionConfidence.NONE)
        
        # Special handling for tax_amount: try aggregation first
        if concept_name == 'tax_amount':
            aggregated_tax = TaxAggregator.aggregate_tax_components(text, self.currency_extractor)
            if aggregated_tax:
                return FieldExtraction(
                    value=aggregated_tax,
                    raw_text=f"Aggregated from CGST+SGST/IGST: {aggregated_tax}",
                    confidence=ExtractionConfidence.HIGH,
                    source_label="cgst+sgst/igst"
                )
        
        # Extract based on value type
        if value_type == 'currency':
            return self._extract_currency_field(concept_name, text, mention_positions)
        elif value_type == 'date':
            return self._extract_date_field(concept_name, text, mention_positions)
        elif value_type == 'percentage':
            return self._extract_percentage_field(concept_name, text, mention_positions)
        elif value_type == 'duration':
            return self._extract_duration_field(concept_name, text, mention_positions)
        else:
            return FieldExtraction(confidence=ExtractionConfidence.NONE)
    
    def _extract_currency_field(
        self,
        concept_name: str,
        text: str,
        mention_positions: List[Tuple[int, str]]
    ) -> FieldExtraction:
        """Extract currency value field with table-aware and line-aware matching"""
        
        if not mention_positions:
            # No explicit label found - extract all currency values and use heuristics
            all_values = self.currency_extractor.extract_all(text)
            
            if not all_values:
                return FieldExtraction(confidence=ExtractionConfidence.NONE)
            
            # Use concept-specific heuristics to pick best value
            value = self.validator.select_best_candidate(
                all_values,
                concept_name,
                []
            )
            
            if value:
                is_valid, reason = self.validator.validate_currency_value(value, concept_name)
                
                if is_valid:
                    return FieldExtraction(
                        value=value,
                        raw_text=str(value),
                        confidence=ExtractionConfidence.LOW,
                        source_label=None
                    )
        
        else:
            # Label found - use table-aware + line-aware extraction
            candidates = []
            
            for position, label in mention_positions:
                # Get the line containing this label to decide extraction strategy
                line_start = text.rfind('\n', 0, position) + 1
                line_end = text.find('\n', position)
                if line_end == -1:
                    line_end = len(text)
                same_line = text[line_start:line_end]
                
                # PRIORITY 1: Check if value is on same line (most common: "Premium: ₹21500")
                label_pos_in_line = position - line_start
                after_label = same_line[label_pos_in_line:]
                value_on_line = self.currency_extractor.extract(after_label)
                
                if value_on_line:
                    is_valid, _ = self.validator.validate_currency_value(value_on_line, concept_name)
                    if is_valid:
                        # Same line match - high priority
                        candidates.append({
                            'value': value_on_line,
                            'score': 1000,
                            'label': label,
                            'raw_text': same_line,
                            'reason': 'same_line',
                            'position': position  # Track position for contextu scoring
                        })
                        continue  # Don't try table extraction for this label if same-line worked
                
                # PRIORITY 2: Only try table extraction if NO value on same line
                table_value = TableExtractor.find_value_in_table(
                    text, label, position, 'currency'
                )
                
                if table_value:
                    is_valid, _ = self.validator.validate_currency_value(table_value, concept_name)
                    if is_valid:
                        candidates.append({
                            'value': table_value,
                            'score': 900,  # Lower than same-line (1000) but higher than next-line (500)
                            'label': label,
                            'raw_text': f"Table: {table_value}",
                            'reason': 'table_extraction',
                            'position': position  # Track position for contextual scoring
                        })
                        continue  # Skip other extraction methods if table worked
                
                # PRIORITY 3: Check next few lines (handles sub-headers, empty lines)
                # Common in tables where label is in header, value is in data row
                current_pos = line_end + 1
                for line_offset in range(5):  # Check up to 5 lines after the label
                    next_line_end = text.find('\n', current_pos)
                    if next_line_end == -1:
                        next_line_end = len(text)
                    
                    if current_pos < len(text):
                        next_line = text[current_pos:next_line_end]
                        
                        # Skip empty lines
                        if next_line.strip():
                            value_next_line = self.currency_extractor.extract(next_line)
                            
                            if value_next_line:
                                is_valid, _ = self.validator.validate_currency_value(value_next_line, concept_name)
                                if is_valid:
                                    # Score decreases with distance: 500, 480, 460, 440, 420
                                    score = 500 - (line_offset * 20)
                                    candidates.append({
                                        'value': value_next_line,
                                        'score': score,
                                        'label': label,
                                        'raw_text': next_line,
                                        'reason': f'next_line+{line_offset}',
                                        'position': position  # Track position for contextual scoring
                                    })
                                    break  # Found valid value, stop checking further lines
                    
                    current_pos = next_line_end + 1
                    if current_pos >= len(text):
                        break
                
                # PRIORITY 4: Fallback to context window
                window_start = max(0, position - 20)
                window_end = min(len(text), position + 300)
                context = text[window_start:window_end]
                
                # Extract all values in context
                all_context_values = self.currency_extractor.extract_all(context)
                
                for val, val_pos in all_context_values:
                    # Calculate actual position in context
                        actual_pos = window_start + val_pos
                        
                        # Prefer values AFTER the label
                        if actual_pos >= position:
                            distance = actual_pos - position
                            score = 100 - min(distance / 10, 90)
                            
                            is_valid, _ = self.validator.validate_currency_value(val, concept_name)
                            if is_valid:
                                candidates.append({
                                    'value': val,
                                    'score': score,
                                    'label': label,
                                    'raw_text': context[val_pos:val_pos+50],
                                    'reason': f'context_after_dist_{distance}',
                                    'position': actual_pos  # Track actual position for contextual scoring
                                })
            
            # Select best candidate by score
            if candidates:
                # Apply contextual adjustments ONLY when there are multiple candidates
                # This helps disambiguation without interfering with extraction priority tiers
                if len(candidates) > 1:
                    for candidate in candidates:
                        raw_lower = candidate.get('raw_text', '').lower()
                        
                        # UNIVERSAL PENALTY: Reduce score if in comparison/example section
                        # This is the most important universal filter - comparison tables have wrong values
                        comparison_keywords = ['compare', 'comparison', 'option', 'example', 'illustration', 'vs', 'or', 'plan']
                        if any(kw in raw_lower for kw in comparison_keywords):
                            candidate['score'] -= 300  # Large penalty for comparison sections
                        
                        # SMALL BOOST: Prefer values with strong financial keyword density
                        # Only apply small boost to avoid disrupting priority tiers (same-line=1000, table=900, next-line=500)
                        financial_keywords = ['premium', 'tax', 'gst', 'policy', 'details']
                        keyword_count = sum(1 for kw in financial_keywords if kw in raw_lower)
                        if keyword_count >= 3:
                            candidate['score'] += 20  # Small boost - won't overcome priority differences
                
                best = max(candidates, key=lambda x: x['score'])
                confidence = ExtractionConfidence.HIGH if best['score'] >= 1000 else (
                    ExtractionConfidence.MEDIUM if best['score'] >= 500 else ExtractionConfidence.LOW
                )
                return FieldExtraction(
                    value=best['value'],
                    raw_text=best['raw_text'][:100],
                    confidence=confidence,
                    source_label=best['label']
                )
        
        return FieldExtraction(confidence=ExtractionConfidence.NONE)
    
    def _extract_date_field(
        self,
        concept_name: str,
        text: str,
        mention_positions: List[Tuple[int, str]]
    ) -> FieldExtraction:
        """Extract date value field with improved line-aware matching"""
        
        if not mention_positions:
            # No label - try to extract dates and use ordering
            all_dates = self.date_extractor.extract_all(text)
            
            if not all_dates:
                return FieldExtraction(confidence=ExtractionConfidence.NONE)
            
            # Use concept heuristics
            if 'start' in concept_name or 'from' in concept_name:
                # Pick earliest date
                value = min(all_dates, key=lambda x: x[0])[0]
            elif 'end' in concept_name or 'to' in concept_name:
                # Pick latest date
                value = max(all_dates, key=lambda x: x[0])[0]
            else:
                value = all_dates[0][0]
            
            if value:
                is_valid, _ = self.validator.validate_date_value(value, concept_name)
                
                if is_valid:
                    return FieldExtraction(
                        value=value.date(),
                        raw_text=value.strftime('%Y-%m-%d'),
                        confidence=ExtractionConfidence.LOW,
                        source_label=None
                    )
        
        else:
            # Label found - use line-aware extraction
            candidates = []
            
            # Define label priority bonuses (higher = better)
            label_priority = {
                # Highest priority - very specific labels
                'period of insurance from': 500,
                'period of insurance to': 500,
                'policy period from': 400,
                'policy period to': 400,
                'coverage from': 300,
                'coverage to': 300,
                # Medium priority - specific labels
                'policy start date': 250,
                'policy end date': 250,
                'commencement of membership': 250,
                'inception date': 200,
                'commencement date': 200,
                'expiration date': 150,
                'termination date': 100,
                # Low priority - generic labels that might match wrong contexts
                'expiry date': 50,  # Can match "Cover expiry date" (long-term)
                'maturity date': 50,
                'from': 10,  # Very generic
                'to': 10,  # Very generic
            }
            
            for position, label in mention_positions:
                # Extract the line containing the label
                line_start = text.rfind('\n', 0, position) + 1
                line_end = text.find('\n', position)
                if line_end == -1:
                    line_end = len(text)
                
                same_line = text[line_start:line_end]
                label_pos_in_line = position - line_start
                
                # Calculate base score based on label specificity
                label_bonus = label_priority.get(label.lower(), 0)
                
                # Look for date on SAME LINE first (after the label)
                after_label = same_line[label_pos_in_line:]
                date_on_line = self.date_extractor.extract(after_label)
                
                if date_on_line:
                    is_valid, _ = self.validator.validate_date_value(date_on_line, concept_name)
                    if is_valid:
                        # Additional validation: filter unreasonable future dates
                        from datetime import datetime
                        current_year = datetime.now().year
                        date_year = date_on_line.year
                        
                        # For policy dates, reject dates more than 2 years in future
                        # (allows for issued-but-not-yet-active policies)
                        is_reasonable = True
                        if date_year > current_year + 2:
                            is_reasonable = False
                        
                        # Penalty for dates in current year (often document metadata)
                        # unless it's a very specific label
                        year_penalty = 0
                        if date_year == current_year and label_bonus < 200:
                            year_penalty = -500  # Strong penalty for current-year dates with generic labels
                        elif date_year == current_year + 1 and label_bonus < 100:
                            year_penalty = -300  # Penalty for next-year dates with very generic labels
                        
                        if is_reasonable:
                            candidates.append({
                                'value': date_on_line,
                                'score': 1000 + label_bonus + year_penalty,  # Label priority + position bonus
                                'label': label,
                                'reason': 'same_line'
                            })
                        candidates.append({
                            'value': date_on_line,
                            'score': 1000,  # Highest priority
                            'label': label,
                            'reason': 'same_line'
                        })
                
                # Check next line if not found on same line
                next_line_start = line_end + 1
                next_line_end = text.find('\n', next_line_start)
                if next_line_end == -1:
                    next_line_end = len(text)
                
                if next_line_start < len(text):
                    next_line = text[next_line_start:next_line_end]
                    date_next_line = self.date_extractor.extract(next_line)
                    
                    if date_next_line:
                        is_valid, _ = self.validator.validate_date_value(date_next_line, concept_name)
                        if is_valid:
                            # Apply same future date filtering
                            from datetime import datetime
                            current_year = datetime.now().year
                            date_year = date_next_line.year
                            
                            is_reasonable = date_year <= current_year + 2
                            
                            year_penalty = 0
                            if date_year == current_year and label_bonus < 200:
                                year_penalty = -500  # Strong penalty for current-year dates
                            elif date_year == current_year + 1 and label_bonus < 100:
                                year_penalty = -300  # Penalty for next-year dates
                            
                            if is_reasonable:
                                candidates.append({
                                    'value': date_next_line,
                                    'score': 500 + label_bonus + year_penalty,  # Lower base than same_line
                                    'label': label,
                                    'reason': 'next_line'
                                })
                
                # Fallback to context window
                window_start = max(0, position - 20)
                window_end = min(len(text), position + 100)
                context = text[window_start:window_end]
                
                value = self.date_extractor.extract(context)
                
                if value:
                    is_valid, _ = self.validator.validate_date_value(value, concept_name, context)
                    
                    if is_valid:
                        # Apply same future date filtering
                        from datetime import datetime
                        current_year = datetime.now().year
                        date_year = value.year
                        
                        is_reasonable = date_year <= current_year + 2
                        
                        year_penalty = 0
                        if date_year == current_year and label_bonus < 200:
                            year_penalty = -500  # Strong penalty for current-year dates
                        elif date_year == current_year + 1 and label_bonus < 100:
                            year_penalty = -300  # Penalty for next-year dates
                        
                        if is_reasonable:
                            candidates.append({
                                'value': value,
                                'score': 100 + label_bonus + year_penalty,  # Lowest base score
                                'label': label,
                                'reason': 'context'
                            })
            
            if candidates:
                best = max(candidates, key=lambda x: x['score'])
                return FieldExtraction(
                    value=best['value'].date(),
                    raw_text=best['value'].strftime('%Y-%m-%d'),
                    confidence=ExtractionConfidence.HIGH if best['score'] >= 500 else ExtractionConfidence.MEDIUM,
                    source_label=best['label']
                )
        
        return FieldExtraction(confidence=ExtractionConfidence.NONE)
    
    def _extract_percentage_field(
        self,
        concept_name: str,
        text: str,
        mention_positions: List[Tuple[int, str]]
    ) -> FieldExtraction:
        """Extract percentage value field"""
        
        if mention_positions:
            for position, label in mention_positions:
                window_start = max(0, position - 20)
                window_end = min(len(text), position + 100)
                context = text[window_start:window_end]
                
                value = self.percentage_extractor.extract(context)
                
                if value:
                    is_valid, _ = self.validator.validate_percentage(value, concept_name)
                    
                    if is_valid:
                        return FieldExtraction(
                            value=value,
                            raw_text=f"{value}%",
                            confidence=ExtractionConfidence.HIGH,
                            source_label=label
                        )
        
        return FieldExtraction(confidence=ExtractionConfidence.NONE)
    
    def _extract_duration_field(
        self,
        concept_name: str,
        text: str,
        mention_positions: List[Tuple[int, str]]
    ) -> FieldExtraction:
        """Extract duration value field"""
        
        if mention_positions:
            for position, label in mention_positions:
                window_start = max(0, position - 20)
                window_end = min(len(text), position + 100)
                context = text[window_start:window_end]
                
                result = self.duration_extractor.extract(context)
                
                if result:
                    value, unit = result
                    return FieldExtraction(
                        value={"value": value, "unit": unit},
                        raw_text=f"{value} {unit}",
                        confidence=ExtractionConfidence.HIGH,
                        source_label=label
                    )
        
        return FieldExtraction(confidence=ExtractionConfidence.NONE)
    
    def _validate_cross_field_constraints(self, result: ParsedInsuranceDocument):
        """Validate relationships between fields and apply field-specific strategies"""
        
        # Step 1: Validate deductible
        if result.deductible_amount.value:
            other_amounts = {
                'coverage_amount': result.coverage_amount.value,
                'base_premium': result.base_premium.value,
                'tax_amount': result.tax_amount.value,
                'total_premium': result.total_premium.value
            }
            
            is_valid = DeductibleValidator.is_valid_deductible(
                result.deductible_amount.value,
                result.deductible_amount.raw_text or "",
                other_amounts
            )
            
            if not is_valid:
                # Invalidate deductible - it's likely a false positive
                result.deductible_amount = FieldExtraction(confidence=ExtractionConfidence.NONE)
                result.parsing_warnings.append("Deductible validation failed - likely false positive")
        
        # Step 2: Disambiguate currency fields that extracted same value
        currency_fields = {
            'total_premium': result.total_premium.value,
            'coverage_amount': result.coverage_amount.value,
            'base_premium': result.base_premium.value
        }
        
        # If total_premium == coverage_amount, one is wrong
        if (result.total_premium.value and result.coverage_amount.value and
            abs(result.total_premium.value - result.coverage_amount.value) < 100):
            
            value = result.total_premium.value
            # Coverage amounts are typically much larger than premiums
            if value > 100000:
                # More likely to be coverage
                result.coverage_amount.value = value
                result.total_premium = FieldExtraction(confidence=ExtractionConfidence.NONE)
                result.parsing_warnings.append("Disambiguated: Large value assigned to coverage_amount")
            else:
                # More likely to be premium
                result.total_premium.value = value
                result.coverage_amount = FieldExtraction(confidence=ExtractionConfidence.NONE)
                result.parsing_warnings.append("Disambiguated: Smaller value assigned to total_premium")
        
        # Step 3: Validate date pair AND calculate policy_term from dates if needed
        if result.policy_start_date.value and result.policy_end_date.value:
            is_valid, reason = self.validator.validate_date_pair(
                result.policy_start_date.value,
                result.policy_end_date.value
            )
            if not is_valid:
                result.validation_errors.append(f"Date validation: {reason}")
            else:
                # Calculate term from dates as fallback or verification
                # +1 for inclusive counting (both start and end days count)
                # This is standard for insurance: Nov 23 to Nov 30 = 8 days, not 7
                days_diff = (result.policy_end_date.value - result.policy_start_date.value).days + 1
                
                # Determine appropriate unit
                if days_diff < 0:
                    # Dates might be swapped - don't override
                    pass
                elif days_diff <= 31:
                    calculated_term = f"{days_diff} days"
                    calculated_unit = "days"
                elif days_diff <= 180:
                    # 1-6 months
                    months = round(days_diff / 30)
                    calculated_term = f"{months} months"
                    calculated_unit = "months"
                else:
                    # 6+ months → years
                    # 364-366 days = 1 year (account for leap years)
                    if 364 <= days_diff <= 366:
                        years = 1
                    else:
                        years = round(days_diff / 365.25)  # More accurate for multi-year policies
                    calculated_term = f"{years} years"
                    calculated_unit = "years"
                
                # Use calculated term if:
                # 1. No policy_term extracted, OR
                # 2. Extracted term is clearly wrong (e.g., "15 days" for an 8-day policy), OR
                # 3. Dates have high confidence but extracted term is medium/low
                should_use_calculated = False
                
                if not result.policy_term.value:
                    should_use_calculated = True
                elif result.policy_term.raw_text:
                    # Check if extracted term doesn't match date-based calculation
                    extracted = result.policy_term.raw_text.lower()
                    extracted_value = result.policy_term.value
                    
                    # Extract numeric value from extracted term
                    if isinstance(extracted_value, dict) and 'value' in extracted_value:
                        extracted_num = extracted_value['value']
                        extracted_unit = extracted_value.get('unit', '')
                        
                        # Check if calculation and extraction are in same unit but different values
                        if extracted_unit == calculated_unit:
                            calculated_num = int(calculated_term.split()[0])
                            # If difference is significant (>50% or >3 units), prefer calculation
                            if abs(extracted_num - calculated_num) > max(3, calculated_num * 0.5):
                                should_use_calculated = True
                                result.parsing_warnings.append(
                                    f"Overriding policy_term '{extracted}' with calculated '{calculated_term}' (dates more reliable)"
                                )
                        # If dates span > 180 days but term says "days", it's likely wrong  
                        elif days_diff > 180 and "days" in extracted and "years" not in extracted:
                            should_use_calculated = True
                            result.parsing_warnings.append(
                                f"Overriding policy_term '{extracted}' with calculated '{calculated_term}'"
                            )
                    
                    # Also override if dates are high confidence but term is not
                    elif (result.policy_start_date.confidence == ExtractionConfidence.HIGH and
                          result.policy_end_date.confidence == ExtractionConfidence.HIGH and
                          result.policy_term.confidence != ExtractionConfidence.HIGH):
                        should_use_calculated = True
                        result.parsing_warnings.append(
                            f"Using calculated term '{calculated_term}' (high-confidence dates)"
                        )
                
                if should_use_calculated and days_diff > 0:
                    # Store in the calculated unit (years/months/days), not always days
                    result.policy_term = FieldExtraction(
                        value={"value": int(calculated_term.split()[0]), "unit": calculated_unit},
                        raw_text=calculated_term,
                        confidence=ExtractionConfidence.MEDIUM,
                        source_label="calculated from dates"
                    )
        
        # Step 4: Validate and calculate premium components
        base = result.base_premium.value
        tax = result.tax_amount.value
        total = result.total_premium.value
        
        # Calculate total_premium from base + tax if missing
        if base and tax and not total:
            calculated_total = base + tax
            result.total_premium = FieldExtraction(
                value=calculated_total,
                raw_text=str(calculated_total),
                confidence=ExtractionConfidence.HIGH,
                source_label="calculated from base + tax"
            )
            total = calculated_total
            result.parsing_warnings.append(f"Calculated total_premium: {base} + {tax} = {calculated_total}")
        
        # Disambiguate premium component swaps
        if base or tax or total:
            # Check for common swapping issues
            tolerance = Decimal('50')  # Allow small differences for rounding
            
            # Issue 1: base_premium == total_premium (extracted same value)
            if base and total and abs(base - total) < tolerance:
                # They're equal - one must be wrong
                # If we have tax, we can deduce the correct values
                if tax:
                    # Common case 1: base is correct, total is duplicate, tax is actually the real total
                    if tax > base:
                        # tax (5813) > base (5055), and base == total (5055)
                        # Likely: tax is the real total, need to find real tax
                        real_total = tax
                        real_tax = real_total - base
                        if real_tax > 0:
                            result.total_premium = FieldExtraction(
                                value=real_total,
                                raw_text=str(real_total),
                                confidence=ExtractionConfidence.MEDIUM,
                                source_label="swapped from tax field"
                            )
                            result.tax_amount = FieldExtraction(
                                value=real_tax,
                                raw_text=str(real_tax),
                                confidence=ExtractionConfidence.LOW,
                                source_label="calculated from total - base"
                            )
                            result.parsing_warnings.append(f"Disambiguated: tax_amount ({tax}) was actually total, calculated real tax = {real_tax}")
                            tax = real_tax
                            total = real_total
                    else:
                        # Common case 2: base extracted total value, need real base
                        # Check if base + tax makes sense as total
                        if abs((base + tax) - base) > tolerance:
                            # base is probably the total, need to find real base
                            # Real base = total - tax
                            real_base = base - tax
                            if real_base > 0:
                                result.base_premium = FieldExtraction(
                                    value=real_base,
                                    raw_text=str(real_base),
                                    confidence=ExtractionConfidence.MEDIUM,
                                    source_label="calculated from total - tax"
                                )
                                result.parsing_warnings.append(f"Disambiguated base_premium: {base} (total) - {tax} (tax) = {real_base}")
                                base = real_base
            
            # Issue 2: tax_amount == total_premium or tax_amount == base_premium
            if tax and total and abs(tax - total) < tolerance:
                # Tax extracted total value - clear tax, will recalculate
                result.parsing_warnings.append(f"Clearing tax_amount ({tax}) - same as total ({total})")
                result.tax_amount = FieldExtraction(confidence=ExtractionConfidence.NONE)
                tax = None
            elif tax and base and abs(tax - base) < tolerance and total:
                # Tax extracted base value
                result.parsing_warnings.append(f"Clearing tax_amount ({tax}) - same as base ({base})")
                result.tax_amount = FieldExtraction(confidence=ExtractionConfidence.NONE)
                tax = None
            
            # Issue 3: total_premium == base_premium (swapped values)
            # If base + tax != total, but total + tax == higher_value, they're swapped
            if base and tax and total:
                expected_total = base + tax
                diff_from_expected = abs(total - expected_total)
                
                # If the math doesn't work out, check for swap
                if diff_from_expected > tolerance:
                    # Try swapping base and total
                    if abs(total + tax - base) < tolerance:
                        # Swap detected: current total is actually base, current base is actually total
                        result.parsing_warnings.append(f"Swapping base_premium and total_premium ({base} <-> {total})")
                        result.base_premium.value = total
                        result.total_premium.value = base
                        base, total = total, base
        
        # Re-validate after disambiguation
        base = result.base_premium.value
        tax = result.tax_amount.value
        total = result.total_premium.value
        
        if base or tax or total:
            is_valid, reason = self.validator.validate_premium_components(base, tax, total)
            if not is_valid:
                result.parsing_warnings.append(f"Premium validation: {reason}")
    
    def _infer_document_type(self, result: ParsedInsuranceDocument) -> InsuranceType:
        """Infer insurance type from extracted fields (optional enhancement)"""
        # Simple heuristic: could be enhanced with more sophisticated logic
        # For now, return UNKNOWN and let external systems classify if needed
        return InsuranceType.UNKNOWN
