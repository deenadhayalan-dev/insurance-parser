"""
Canonical data models for parsed insurance documents.
These schemas represent the normalized output regardless of document format.
"""

from typing import Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class InsuranceType(str, Enum):
    """Supported insurance categories"""
    LIFE = "life"
    HEALTH = "health"
    MOTOR = "motor"
    TRAVEL = "travel"
    UNKNOWN = "unknown"


class ExtractionConfidence(str, Enum):
    """Confidence level of extracted value"""
    HIGH = "high"       # Single clear match with strong context
    MEDIUM = "medium"   # Multiple candidates, best picked by heuristics
    LOW = "low"         # Weak signals, uncertain extraction
    NONE = "none"       # Field not found


class FieldExtraction(BaseModel):
    """Individual field extraction result with metadata"""
    value: Optional[Any] = None
    raw_text: Optional[str] = None  # Original text from document
    confidence: ExtractionConfidence = ExtractionConfidence.NONE
    source_label: Optional[str] = None  # Actual label found in document
    
    class Config:
        use_enum_values = True


class CurrencyValue(BaseModel):
    """Structured currency value"""
    amount: Optional[Decimal] = None
    currency: str = "INR"  # Default to Indian Rupee
    
    @field_validator('amount', mode='before')
    @classmethod
    def validate_amount(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            # Remove currency symbols and commas
            cleaned = v.replace(',', '').replace('₹', '').replace('Rs', '').strip()
            try:
                return Decimal(cleaned)
            except:
                return None
        return v


class PercentageValue(BaseModel):
    """Structured percentage value"""
    value: Optional[Decimal] = None
    
    @field_validator('value', mode='before')
    @classmethod
    def validate_percentage(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            cleaned = v.replace('%', '').strip()
            try:
                return Decimal(cleaned)
            except:
                return None
        return v


class DurationValue(BaseModel):
    """Structured duration value"""
    value: Optional[int] = None
    unit: str = "years"  # years, months, days


class ParsedInsuranceDocument(BaseModel):
    """
    Canonical output schema for insurance document parsing.
    Contains only financially meaningful fields.
    """
    
    # Metadata
    document_type: InsuranceType = InsuranceType.UNKNOWN
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_file: Optional[str] = None
    is_ocr_processed: bool = False
    
    # PRIMARY FINANCIAL PILLARS
    
    coverage_amount: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="Sum Insured / Sum Assured / IDV"
    )
    
    base_premium: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="Premium before tax"
    )
    
    tax_amount: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="GST / Service Tax"
    )
    
    total_premium: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="Total amount payable"
    )
    
    policy_start_date: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="Coverage start date"
    )
    
    policy_end_date: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="Coverage end date"
    )
    
    policy_term: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="Policy duration"
    )
    
    # SECONDARY FINANCIAL PILLARS
    
    deductible_amount: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="Deductible / Excess"
    )
    
    co_pay_percentage: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="Co-payment percentage"
    )
    
    # Validation Summary
    validation_errors: list[str] = Field(default_factory=list)
    parsing_warnings: list[str] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
    
    def to_simple_dict(self) -> Dict[str, Any]:
        """
        Convert to simplified dictionary with just values (no metadata).
        Useful for downstream systems that need clean data.
        """
        return {
            "document_type": self.document_type,
            "coverage_amount": self.coverage_amount.value,
            "base_premium": self.base_premium.value,
            "tax_amount": self.tax_amount.value,
            "total_premium": self.total_premium.value,
            "policy_start_date": self.policy_start_date.value,
            "policy_end_date": self.policy_end_date.value,
            "policy_term": self.policy_term.value,
            "deductible_amount": self.deductible_amount.value,
            "co_pay_percentage": self.co_pay_percentage.value
        }
    
    def get_extraction_summary(self) -> Dict[str, str]:
        """Return summary of extraction confidence for all fields"""
        fields = [
            "coverage_amount", "base_premium", "tax_amount", "total_premium",
            "policy_start_date", "policy_end_date", "policy_term",
            "deductible_amount", "co_pay_percentage"
        ]
        return {
            field: getattr(self, field).confidence 
            for field in fields
        }
