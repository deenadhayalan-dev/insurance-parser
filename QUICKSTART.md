# Quick Start Guide

## Installation (5 minutes)

### 1. Install Python Dependencies

```bash
cd insurance-parser
pip install -r requirements.txt
```

### 2. Install Tesseract OCR (for scanned PDFs)

**Windows:**
```bash
# Download installer from:
# https://github.com/UB-Mannheim/tesseract/wiki

# After installation, add to PATH:
# C:\Program Files\Tesseract-OCR\
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

### 3. Verify Installation

```bash
python -c "import pdfplumber; print('✓ pdfplumber installed')"
python -c "import ocrmypdf; print('✓ ocrmypdf installed')"
tesseract --version
```

## First Parse (2 minutes)

### Command Line

```bash
# Parse a PDF
python cli.py /path/to/policy.pdf

# Save results to JSON
python cli.py /path/to/policy.pdf --output results.json

# View examples
python examples.py
```

### Python Code

Create a file `test_parse.py`:

```python
from src import InsuranceDocumentParser

# Initialize parser
parser = InsuranceDocumentParser()

# Parse document
result = parser.parse_document('sample_policy.pdf')

# Print results
print(f"Coverage: ₹{result.coverage_amount.value}")
print(f"Premium: ₹{result.total_premium.value}")
print(f"Start: {result.policy_start_date.value}")
print(f"End: {result.policy_end_date.value}")

# Check confidence
summary = result.get_extraction_summary()
for field, confidence in summary.items():
    print(f"{field}: {confidence}")
```

Run it:
```bash
python test_parse.py
```

## Testing (1 minute)

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_extractors.py -v

# With coverage
pytest --cov=src tests/
```

## Common Use Cases

### 1. Batch Processing

```python
from pathlib import Path
from src import InsuranceDocumentParser

parser = InsuranceDocumentParser()
pdf_dir = Path('policies/')

for pdf_file in pdf_dir.glob('*.pdf'):
    try:
        result = parser.parse_document(str(pdf_file))
        print(f"✓ {pdf_file.name}: Premium = ₹{result.total_premium.value}")
    except Exception as e:
        print(f"✗ {pdf_file.name}: {e}")
```

### 2. Export to CSV

```python
import csv
from src import InsuranceDocumentParser

parser = InsuranceDocumentParser()
results = []

# Parse multiple files
for pdf in ['policy1.pdf', 'policy2.pdf', 'policy3.pdf']:
    result = parser.parse_document(pdf)
    results.append({
        'file': pdf,
        'coverage': result.coverage_amount.value,
        'premium': result.total_premium.value,
        'start': result.policy_start_date.value,
        'end': result.policy_end_date.value
    })

# Write to CSV
with open('results.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['file', 'coverage', 'premium', 'start', 'end'])
    writer.writeheader()
    writer.writerows(results)
```

### 3. Filter by Confidence

```python
from src import InsuranceDocumentParser, ExtractionConfidence

parser = InsuranceDocumentParser()
result = parser.parse_document('policy.pdf')

# Only use high-confidence extractions
if result.total_premium.confidence == ExtractionConfidence.HIGH:
    premium = float(result.total_premium.value)
    print(f"Confirmed premium: ₹{premium:,.2f}")
else:
    print("⚠ Premium extraction uncertain - manual review needed")
```

### 4. Validate Business Rules

```python
from src import InsuranceDocumentParser
from decimal import Decimal

parser = InsuranceDocumentParser()
result = parser.parse_document('policy.pdf')

# Custom validation
base = result.base_premium.value
tax = result.tax_amount.value
total = result.total_premium.value

if base and tax and total:
    calculated = base + tax
    tolerance = Decimal('10')
    
    if abs(calculated - total) <= tolerance:
        print("✓ Premium calculation verified")
    else:
        print(f"⚠ Mismatch: {base} + {tax} = {calculated} ≠ {total}")

# Date validation
if result.policy_start_date.value and result.policy_end_date.value:
    start = result.policy_start_date.value
    end = result.policy_end_date.value
    
    if end > start:
        duration = (end - start).days
        print(f"✓ Policy duration: {duration} days")
    else:
        print("⚠ Invalid date range")
```

## Customization

### Add Custom Labels

Edit `config/vocabulary.yaml`:

```yaml
financial_concepts:
  total_premium:
    labels:
      - "total premium"
      - "gross premium"
      # Add your custom label
      - "final amount payable"
      - "premium inclusive of all charges"
```

### Add Custom Field

1. Update `config/vocabulary.yaml`:

```yaml
  policy_number:
    description: "Unique policy identifier"
    labels:
      - "policy number"
      - "policy no"
      - "certificate number"
    value_type: "text"
    required: false
```

2. Update `src/models/schemas.py`:

```python
class ParsedInsuranceDocument(BaseModel):
    # ... existing fields ...
    
    policy_number: FieldExtraction = Field(
        default_factory=FieldExtraction,
        description="Policy number"
    )
```

3. No other changes needed!

## Troubleshooting

### Issue: "OCRmyPDF not found"

```bash
# Install OCRmyPDF
pip install ocrmypdf

# Verify Tesseract is installed
tesseract --version
```

### Issue: "No text extracted"

- Check if PDF is password-protected
- For scanned PDFs, ensure Tesseract is installed
- Try opening PDF manually to verify it's not corrupted

### Issue: "Field not extracted"

- Check if label exists in `config/vocabulary.yaml`
- Add the specific label variant from your document
- Verify the value is in a reasonable range (see validators)

### Issue: Low confidence scores

- Common for documents without explicit labels
- Parser falls back to heuristics (position-based)
- Consider adding document-specific labels to vocabulary

## Performance Tips

### For Large Batches

```python
from concurrent.futures import ThreadPoolExecutor
from src import InsuranceDocumentParser

def parse_file(pdf_path):
    parser = InsuranceDocumentParser()
    return parser.parse_document(pdf_path)

# Parallel processing
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(parse_file, pdf_files))
```

### For Scanned PDFs

- OCR is slow (2-5 seconds per page)
- Pre-process with OCRmyPDF in batch
- Cache OCR results if re-parsing

## Next Steps

1. **Read**: [ARCHITECTURE.md](ARCHITECTURE.md) for design details
2. **Explore**: [examples.py](examples.py) for more code samples
3. **Test**: Run `pytest tests/ -v` to see all tests
4. **Customize**: Extend vocabulary for your specific use case

## Getting Help

- Check [README.md](README.md) for full documentation
- Review test files for usage examples
- Examine `cli.py` for CLI examples

---

**You're ready to parse insurance documents! 🚀**
