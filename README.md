# Insurance Document Parser

A production-grade, deterministic parser for extracting structured financial data from insurance policy documents. Supports Life, Health, Motor, and Travel insurance policies across multiple insurers with varying document formats.

## Overview

This parser uses a semantic, vocabulary-driven approach to extract financial fields from insurance PDFs without relying on document structure, specific layouts, or large language models. It achieves high accuracy through pattern matching, proximity-based validation, and configurable business rules.

**Key Features:**

- **Label-Agnostic**: Works with varied terminology across different insurance providers
- **Layout-Agnostic**: No dependency on page numbers, line positions, or table layouts
- **Extensible**: Add new insurance types and labels via YAML configuration
- **Deterministic**: Consistent, reproducible results without AI/LLM randomness
- **Fast**: Processes digital PDFs in under 1 second, scanned PDFs in 2-5 seconds

## Architecture

### System Design

The parser implements a multi-stage pipeline that separates concerns and enables independent testing of each component:

```
PDF Document
    ↓
Document Processor (Format Detection)
    ↓
Text Extractor (pdfplumber / OCRmyPDF)
    ↓
Text Normalizer (Cleanup, standardization)
    ↓
Concept Detector (Vocabulary-based label mapping)
    ↓
Value Extractors (Currency, Date, Percentage, Duration)
    ↓
Context Validator (Proximity + Business rules)
    ↓
Field Strategies (Aggregation, disambiguation)
    ↓
Canonical Schema Output (JSON with confidence scores)
```

### Core Components

#### 1. Document Processor (`src/document_processor.py`)

- Detects whether PDF contains digital text or requires OCR
- Routes to appropriate extraction method
- Handles malformed or encrypted PDFs gracefully

#### 2. Text Extractor (`src/text_extractor.py`)

- **Digital extraction**: Uses pdfplumber for native text extraction
- **OCR extraction**: Uses ocrmypdf with Tesseract for scanned documents
- Preserves spatial information for proximity validation

#### 3. Text Normalizer (`src/parser/normalizer.py`)

- Removes excessive whitespace and special characters
- Standardizes currency symbols and number formats
- Corrects common OCR errors
- Normalizes date representations

#### 4. Concept Detector (`src/parser/concept_detector.py`)

- Maps document-specific labels to canonical field names using `config/vocabulary.yaml`
- Example: "Sum Assured", "Sum Insured", "Coverage Limit" → `coverage_amount`
- Uses fuzzy matching with word boundary checks to avoid false positives
- Returns all concept mentions with character positions for proximity validation

#### 5. Value Extractors (`src/parser/extractors.py`)

- **CurrencyExtractor**: Handles Indian Rupee formats (₹, Rs., Lakhs, Crores)
- **DateExtractor**: Parses various date formats (DD/MM/YYYY, DD-MMM-YYYY, etc.)
- **PercentageExtractor**: Extracts percentage values with validation
- **DurationExtractor**: Parses policy terms (years, months)

#### 6. Context Validator (`src/parser/validator.py`)

- Uses proximity-based filtering to select correct values near concept labels
- Applies business rules (e.g., premium ranges, date logic)
- Validates cross-field relationships (base_premium + tax_amount ≈ total_premium)

#### 7. Field Strategies (`src/parser/field_strategies.py`)

- **TaxAggregator**: Sums multiple tax components (CGST + SGST + IGST)
- **FieldDisambiguator**: Resolves conflicts when multiple values match
- **DeductibleValidator**: Validates deductible amounts against coverage

#### 8. Parsing Pipeline (`src/parser/pipeline.py`)

- Orchestrates the complete extraction workflow
- Coordinates all components in the correct sequence
- Generates confidence scores for each extracted field
- Produces standardized output with metadata

### Vocabulary System

The `config/vocabulary.yaml` file is the core configuration that defines:

- Canonical field names (`coverage_amount`, `base_premium`, etc.)
- Alternative labels for each field across different insurers
- Field types (currency, date, percentage, duration)
- Required vs. optional fields

This data-driven approach allows adding new terminology without code changes.

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Tesseract OCR (for scanned PDF support)

### Setup Instructions

1. **Clone or download the repository:**

```bash
cd insurance-parser
```

2. **Create and activate a virtual environment (recommended):**

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate
```

3. **Install Python dependencies:**

```bash
pip install -r requirements.txt
```

4. **Install Tesseract OCR (for scanned PDF support):**

**Windows:**
- Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
- Install to default location: `C:\Program Files\Tesseract-OCR\`
- Add to system PATH environment variable

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

5. **Verify installation:**

```bash
python -c "import pdfplumber; print('pdfplumber installed successfully')"
python -c "import ocrmypdf; print('ocrmypdf installed successfully')"
tesseract --version
```

## Usage

### Command Line Interface

The parser provides a CLI for quick document processing:

```bash
# Basic usage - parse a PDF and display results
python cli.py path/to/policy.pdf

# Save results to JSON file
python cli.py path/to/policy.pdf --output results.json

# Simple output format (values only, no metadata)
python cli.py path/to/policy.pdf --simple

# Verbose mode with full extraction details
python cli.py path/to/policy.pdf --verbose

# Use custom vocabulary file
python cli.py path/to/policy.pdf --vocab custom_vocabulary.yaml
```

**CLI Options:**

- `pdf_file` (required): Path to the insurance PDF document
- `-o, --output`: Save results to specified JSON file
- `-s, --simple`: Output simplified format with values only
- `-v, --verbose`: Display detailed extraction information
- `--vocab`: Path to custom vocabulary YAML file

### Python API

For programmatic usage, import the parser in your Python code:

```python
from src import InsuranceDocumentParser

# Initialize parser
parser = InsuranceDocumentParser()

# Parse a document
result = parser.parse_document('policy.pdf')

# Access extracted fields
print(f"Coverage Amount: ₹{result.coverage_amount.value}")
print(f"Base Premium: ₹{result.base_premium.value}")
print(f"Tax Amount: ₹{result.tax_amount.value}")
print(f"Total Premium: ₹{result.total_premium.value}")
print(f"Policy Start: {result.policy_start_date.value}")
print(f"Policy End: {result.policy_end_date.value}")

# Check extraction confidence
print(f"Coverage confidence: {result.coverage_amount.confidence}")

# Get field extraction summary
summary = result.get_extraction_summary()
for field, info in summary.items():
    print(f"{field}: {info}")

# Export to JSON file
json_output = parser.parse_to_json('policy.pdf', 'output.json')

# Get simplified dictionary (values only)
simple_dict = parser.parse_to_simple_dict('policy.pdf')
print(simple_dict)
```

**Using Custom Vocabulary:**

```python
# Initialize with custom vocabulary
parser = InsuranceDocumentParser(vocabulary_path='custom_vocab.yaml')
result = parser.parse_document('policy.pdf')
```

## Extracted Fields

### Primary Financial Fields

| Field Name | Description | Example Labels | Value Type |
|------------|-------------|----------------|------------|
| `coverage_amount` | Total insured amount / Sum Assured | Sum Insured, IDV, Coverage Limit | Currency |
| `base_premium` | Premium before taxes | Net Premium, OD Premium, Base Premium | Currency |
| `tax_amount` | Total tax components | GST, CGST+SGST, Service Tax | Currency |
| `total_premium` | Total amount payable | Gross Premium, Total Premium | Currency |
| `policy_start_date` | Policy inception date | Start Date, Valid From | Date |
| `policy_end_date` | Policy expiry date | End Date, Valid Till | Date |
| `policy_term` | Policy duration | Tenure, Policy Period | Duration |

### Secondary Fields

| Field Name | Description | Example Labels | Value Type |
|------------|-------------|----------------|------------|
| `deductible_amount` | Deductible/Excess amount | Compulsory Excess, Deductible | Currency |
| `co_pay_percentage` | Co-payment percentage | Co-pay, Patient Share | Percentage |

## Output Format

The parser returns a structured JSON object with extraction metadata:

```json
{
  "document_type": "unknown",
  "extraction_timestamp": "2026-02-06T10:30:00",
  "source_file": "policy.pdf",
  "is_ocr_processed": false,
  
  "coverage_amount": {
    "value": "500000",
    "raw_text": "₹5,00,000",
    "confidence": "high",
    "source_label": "sum insured"
  },
  
  "base_premium": {
    "value": "8500",
    "raw_text": "₹8,500",
    "confidence": "high",
    "source_label": "net premium"
  },
  
  "tax_amount": {
    "value": "1530",
    "confidence": "high",
    "source_label": "gst"
  },
  
  "total_premium": {
    "value": "10030",
    "confidence": "high",
    "source_label": "total premium"
  },
  
  "policy_start_date": {
    "value": "2024-01-15",
    "confidence": "high",
    "source_label": "policy start date"
  },
  
  "policy_end_date": {
    "value": "2025-01-14",
    "confidence": "high",
    "source_label": "policy end date"
  },
  
  "validation_errors": [],
  "parsing_warnings": []
}
```

**Confidence Levels:**

- `high`: Exact match with strong proximity to concept label
- `medium`: Fuzzy match or moderate proximity
- `low`: Weak match or poor proximity
- `none`: Field not found

## Configuration

### Adding New Labels

To support new terminology from different insurers, edit `config/vocabulary.yaml`:

```yaml
financial_concepts:
  coverage_amount:
    description: "Total financial liability covered"
    labels:
      - "sum insured"
      - "sum assured"
      - "idv"
      - "your new label here"  # Add new label
    value_type: "currency"
    required: true
```

### Adding New Fields

1. Add field definition to `config/vocabulary.yaml`:

```yaml
  new_field_name:
    description: "Description of the new field"
    labels:
      - "label variant 1"
      - "label variant 2"
    value_type: "currency"  # or date, percentage, duration
    required: false
```

2. Add field to schema in `src/models/schemas.py`:

```python
class ParsedInsuranceDocument(BaseModel):
    # ... existing fields ...
    
    new_field_name: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="Description of the new field"
    )
```

No changes to parsing logic are required - the system automatically handles new fields.

## Project Structure

```
insurance-parser/
├── config/
│   └── vocabulary.yaml          # Field labels and mappings (configuration)
├── src/
│   ├── __init__.py             # Package initialization
│   ├── main.py                 # High-level parser orchestrator
│   ├── document_processor.py  # PDF format detection
│   ├── text_extractor.py      # Text extraction (digital/OCR)
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic data models
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── pipeline.py         # Main parsing pipeline
│   │   ├── concept_detector.py # Label → field mapping
│   │   ├── extractors.py       # Value extraction (currency, date, etc.)
│   │   ├── normalizer.py       # Text preprocessing
│   │   ├── validator.py        # Context and business rule validation
│   │   ├── field_strategies.py # Aggregation and disambiguation
│   │   └── table_extractor.py  # Table-based extraction
│   └── utils/
│       ├── __init__.py
│       └── patterns.py         # Regex patterns and utilities
├── cli.py                      # Command-line interface
├── requirements.txt            # Python dependencies
├── README.md                   # This file
└── QUICKSTART.md              # Quick start guide
```

## Design Rationale

### Why No LLMs?

- **Determinism**: Same input always produces same output
- **Speed**: Sub-second processing without API calls
- **Cost**: Zero runtime costs for inference
- **Privacy**: No data sent to external services
- **Testability**: Predictable behavior enables comprehensive testing
- **Auditability**: Clear extraction logic for compliance

### Why Vocabulary-Driven?

- Non-technical users can add new terminology
- Changes don't require code deployment
- A/B testing of label variations
- Version control for domain knowledge
- Easy to maintain and extend

### Why Multi-Stage Pipeline?

- Clear separation of concerns
- Each component independently testable
- Easier debugging and optimization
- Modularity enables component replacement
- Confidence attribution per stage

## Performance Characteristics

- **Digital PDFs**: < 1 second per document
- **Scanned PDFs**: 2-5 seconds (OCR processing overhead)
- **Memory Usage**: Proportional to document size (typically < 50MB)
- **Concurrency**: Thread-safe, supports parallel document processing
- **Accuracy**: ~80% field extraction accuracy across diverse documents

## Error Handling

The parser handles errors gracefully:

- **Missing fields**: Returns `null` value with `confidence: "none"`
- **Invalid values**: Skipped with warning in `parsing_warnings`
- **Malformed PDFs**: Returns error message without crashing
- **OCR failures**: Falls back to digital extraction if possible
- **Format errors**: Validation errors collected in `validation_errors`

## Dependencies

The parser requires the following Python packages:

- `pdfplumber >= 0.10.0` - PDF text extraction
- `ocrmypdf >= 15.0.0` - OCR for scanned documents
- `pydantic >= 2.0.0` - Data validation and schemas
- `python-dateutil >= 2.8.0` - Date parsing
- `PyYAML >= 6.0` - Configuration file parsing
- `pytest >= 7.4.0` - Testing framework
- `pytest-cov >= 4.1.0` - Test coverage

External dependency:

- `Tesseract OCR` - OCR engine (system-level installation)

## Contributing

To contribute or extend the parser:

1. Update `config/vocabulary.yaml` with new labels/fields
2. Add test cases with sample documents
3. Ensure backward compatibility
4. Follow existing code structure and style
5. Add documentation for new features

## License

This is a reference implementation. Adapt and modify as needed for your use case.

## Troubleshooting

**Issue**: "No module named 'src'"

**Solution**: Ensure you're running commands from the project root directory.

---

**Issue**: "Tesseract not found" error

**Solution**: Install Tesseract OCR and add to system PATH.

---

**Issue**: Low extraction accuracy

**Solution**: Check if document labels are in `vocabulary.yaml`. Add missing labels to configuration.

---

**Issue**: All fields show `confidence: "none"`

**Solution**: Verify PDF is not encrypted. Try running with `--verbose` to see detailed logs.

---

For additional questions or issues, please consult the QUICKSTART.md guide or examine the source code in the `src/` directory.
