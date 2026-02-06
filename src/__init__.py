"""Main package initialization"""
from .main import InsuranceDocumentParser
from .models.schemas import ParsedInsuranceDocument, InsuranceType, ExtractionConfidence

__version__ = '1.0.0'

__all__ = [
    'InsuranceDocumentParser',
    'ParsedInsuranceDocument',
    'InsuranceType',
    'ExtractionConfidence'
]
