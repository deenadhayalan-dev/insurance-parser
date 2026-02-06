# How to Run the Insurance Document Parser

This guide provides step-by-step instructions for setting up and running the Insurance Document Parser on your system.

## Table of Contents

- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Running the Parser](#running-the-parser)
- [Usage Examples](#usage-examples)
- [Understanding the Output](#understanding-the-output)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Operating System

- Windows 10/11
- Linux (Ubuntu 20.04+, Debian, CentOS)
- macOS 10.14+

### Software Prerequisites

- **Python**: Version 3.8 or higher
- **pip**: Python package installer (usually included with Python)
- **Tesseract OCR**: Required for processing scanned PDF documents

### Hardware Recommendations

- **Minimum**: 2GB RAM, 500MB free disk space
- **Recommended**: 4GB RAM, 1GB free disk space for better performance

---

## Installation

### Step 1: Verify Python Installation

Open a terminal/command prompt and verify Python is installed:

```bash
python --version
```

Expected output: `Python 3.8.x` or higher

If Python is not installed, download it from [python.org](https://www.python.org/downloads/)

### Step 2: Navigate to Project Directory

```bash
cd path/to/insurance-parser
```

Replace `path/to/insurance-parser` with the actual location where you extracted/cloned the project.

### Step 3: Create Virtual Environment (Recommended)

Creating a virtual environment isolates the project dependencies from your system Python installation.

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

You should see `(.venv)` prefix in your terminal prompt, indicating the virtual environment is active.

### Step 4: Install Python Dependencies

With the virtual environment activated, install required packages:

```bash
pip install -r requirements.txt
```

This will install:
- pdfplumber (PDF text extraction)
- ocrmypdf (OCR processing)
- pydantic (data validation)
- python-dateutil (date parsing)
- PyYAML (configuration files)
- pytest (testing framework)

### Step 5: Install Tesseract OCR

Tesseract is required for processing scanned PDF documents.

**Windows:**

1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (`tesseract-ocr-w64-setup-5.x.x.exe`)
3. Install to default location: `C:\Program Files\Tesseract-OCR\`
4. Add to PATH:
   - Open System Environment Variables
   - Edit the PATH variable
   - Add: `C:\Program Files\Tesseract-OCR\`
5. Restart your terminal/command prompt

**Linux (Ubuntu/Debian):**

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**

```bash
brew install tesseract
```

### Step 6: Verify Installation

Confirm all components are properly installed:

```bash
# Verify pdfplumber
python -c "import pdfplumber; print('✓ pdfplumber installed')"

# Verify ocrmypdf
python -c "import ocrmypdf; print('✓ ocrmypdf installed')"

# Verify Tesseract
tesseract --version
```

If all commands execute without errors, you're ready to use the parser.

---

## Running the Parser

### Basic Command Structure

```bash
python cli.py <path-to-pdf-file> [options]
```

### Command-Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `<pdf_file>` | Path to insurance PDF (required) | `policy.pdf` |
| `-o, --output <file>` | Save results to JSON file | `--output results.json` |
| `-s, --simple` | Output simplified format (values only) | `--simple` |
| `-v, --verbose` | Show detailed extraction information | `--verbose` |
| `--vocab <file>` | Use custom vocabulary file | `--vocab custom.yaml` |

---

## Usage Examples

### Example 1: Basic Parsing

Parse a PDF and display results in the terminal:

```bash
python cli.py documents/sample_policy.pdf
```

**Expected Output:**
```
Parsing document: documents/sample_policy.pdf
Please wait...

============================================================
INSURANCE DOCUMENT PARSING RESULTS
============================================================

Document Type: unknown
Source File: sample_policy.pdf
OCR Processed: No

--- PRIMARY FINANCIAL FIELDS ---

✓ Coverage Amount    : 500000 (high)
✓ Base Premium       : 8500 (high)
✓ Tax Amount         : 1530 (high)
✓ Total Premium      : 10030 (high)
✓ Policy Start Date  : 2024-01-15 (high)
✓ Policy End Date    : 2025-01-14 (high)
✓ Policy Term        : 1 year (high)

--- SECONDARY FINANCIAL FIELDS ---

✗ Deductible Amount  : Not found
✗ Co-pay Percentage  : Not found

============================================================
```

### Example 2: Save Results to JSON

Parse a PDF and save the extracted data to a JSON file:

```bash
python cli.py documents/policy.pdf --output results.json
```

This creates a `results.json` file with structured extraction data and metadata.

### Example 3: Simple Output Format

Get just the extracted values without metadata:

```bash
python cli.py documents/policy.pdf --simple
```

**Example Output:**
```json
{
  "coverage_amount": "500000",
  "base_premium": "8500",
  "tax_amount": "1530",
  "total_premium": "10030",
  "policy_start_date": "2024-01-15",
  "policy_end_date": "2025-01-14",
  "policy_term": "1 year",
  "deductible_amount": null,
  "co_pay_percentage": null
}
```

### Example 4: Verbose Mode

Get detailed extraction information for debugging:

```bash
python cli.py documents/policy.pdf --verbose
```

This shows the extraction summary plus the complete JSON output with confidence scores and source labels.

### Example 5: Custom Vocabulary

Use a custom vocabulary configuration for specialized terminology:

```bash
python cli.py documents/policy.pdf --vocab config/custom_vocabulary.yaml
```

### Example 6: Batch Processing with PowerShell/Bash

Process multiple PDF files:

**Windows PowerShell:**
```powershell
Get-ChildItem documents\*.pdf | ForEach-Object {
    python cli.py $_.FullName --output "results\$($_.BaseName).json"
}
```

**Linux/macOS Bash:**
```bash
for pdf in documents/*.pdf; do
    filename=$(basename "$pdf" .pdf)
    python cli.py "$pdf" --output "results/${filename}.json"
done
```

---

## Understanding the Output

### Confidence Levels

Each extracted field includes a confidence score:

- **high**: Exact match with strong proximity to concept label (>90% confident)
- **medium**: Fuzzy match or moderate proximity (60-90% confident)
- **low**: Weak match or poor proximity (30-60% confident)
- **none**: Field not found in document

### Field Descriptions

| Field | What It Represents | Common Sources |
|-------|-------------------|----------------|
| `coverage_amount` | Total insured amount | Sum Assured, IDV, Coverage Limit |
| `base_premium` | Premium before taxes | Net Premium, OD Premium |
| `tax_amount` | Total tax (CGST+SGST+IGST) | GST, Service Tax |
| `total_premium` | Final payable amount | Gross Premium, Total Amount |
| `policy_start_date` | When coverage begins | Start Date, Inception Date |
| `policy_end_date` | When coverage expires | End Date, Expiry Date |
| `policy_term` | Duration of coverage | Tenure, Policy Period |
| `deductible_amount` | Out-of-pocket amount | Excess, Deductible |
| `co_pay_percentage` | Patient's payment share | Co-payment, Cost Sharing |

### Validation Errors vs. Warnings

- **Validation Errors**: Critical issues that prevent reliable extraction (e.g., corrupted PDF)
- **Warnings**: Non-critical issues noted during parsing (e.g., unexpected value format)

---

## Common Workflows

### Workflow 1: Single Document Analysis

1. Place your PDF in the project directory or note its path
2. Run: `python cli.py path/to/policy.pdf`
3. Review the output in the terminal
4. If needed, save to JSON: `python cli.py path/to/policy.pdf --output results.json`

### Workflow 2: Integration with Existing System

```python
# integration_script.py
from src import InsuranceDocumentParser
import json

def process_policy(pdf_path):
    """Process insurance policy and return extracted data"""
    parser = InsuranceDocumentParser()
    result = parser.parse_document(pdf_path)
    
    # Get simple dictionary
    data = result.to_simple_dict()
    
    # Add custom business logic
    if data['total_premium']:
        data['monthly_premium'] = float(data['total_premium']) / 12
    
    return data

# Usage
policy_data = process_policy('new_policy.pdf')
print(json.dumps(policy_data, indent=2))
```

### Workflow 3: Quality Assurance Check

Review extraction quality before downstream processing:

```bash
# Parse with verbose output
python cli.py policy.pdf --verbose > extraction_log.txt

# Review the log
cat extraction_log.txt  # Linux/macOS
type extraction_log.txt  # Windows
```

Check for:
- All required fields have `high` confidence
- No validation errors
- Warnings are acceptable
- Values make business sense

### Workflow 4: Adding Support for New Insurer

If the parser doesn't recognize labels from a new insurance company:

1. Parse the document: `python cli.py new_company_policy.pdf --verbose`
2. Note which fields show `confidence: "none"`
3. Open `config/vocabulary.yaml`
4. Add the new labels under the appropriate concept:

```yaml
financial_concepts:
  coverage_amount:
    labels:
      - "sum insured"
      # Add new label found in document
      - "coverage value"  # Example new label
```

5. Re-run the parser to verify improved extraction

---

## Troubleshooting

### Issue: "No module named 'src'"

**Cause:** Running commands from wrong directory.

**Solution:**
```bash
# Navigate to project root
cd path/to/insurance-parser

# Verify you're in the right location
ls  # Should show cli.py, src/, config/, etc.

# Run parser
python cli.py documents/policy.pdf
```

### Issue: "File not found" error

**Cause:** Incorrect PDF path.

**Solution:**
```bash
# Use absolute path
python cli.py C:\Users\YourName\Documents\policy.pdf

# Or relative path from project root
python cli.py documents\policy.pdf  # Windows
python cli.py documents/policy.pdf  # Linux/macOS
```

### Issue: "Tesseract is not installed"

**Cause:** Tesseract OCR not in system PATH.

**Solution for Windows:**
1. Open System Properties > Environment Variables
2. Edit PATH variable
3. Add: `C:\Program Files\Tesseract-OCR\`
4. Restart terminal
5. Verify: `tesseract --version`

**Solution for Linux/macOS:**
```bash
# Install Tesseract
sudo apt-get install tesseract-ocr  # Ubuntu/Debian
brew install tesseract              # macOS
```

### Issue: All fields show "Not found"

**Possible Causes:**

1. **PDF is encrypted**: Decrypt the PDF first
2. **Scanned image without OCR**: Parser should auto-detect, but verify Tesseract is installed
3. **Unusual terminology**: Add labels to `config/vocabulary.yaml`

**Debugging Steps:**
```bash
# Run with verbose mode
python cli.py policy.pdf --verbose

# Check if text was extracted
# Look for "is_ocr_processed": true/false in output
```

### Issue: Low confidence scores

**Cause:** Document uses non-standard terminology.

**Solution:** Update vocabulary configuration:

1. Run parser with verbose mode to see what was found
2. Open `config/vocabulary.yaml`
3. Add the actual labels from your document to the appropriate concept
4. Re-run parser

### Issue: Incorrect values extracted

**Cause:** Multiple values in document, wrong one selected.

**Investigation:**
```bash
# Enable verbose mode to see all candidates
python cli.py policy.pdf --verbose

# Review the proximity and confidence scores
# Field strategies may need adjustment in code
```

### Issue: Virtual environment not activating

**Windows:**
```bash
# If execution policy error
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then activate
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
# Ensure activation script has execute permissions
chmod +x .venv/bin/activate
source .venv/bin/activate
```

### Issue: Performance is slow

**Normal Processing Times:**
- Digital PDFs: < 1 second
- Scanned PDFs: 2-5 seconds (OCR overhead)

**If slower:**
1. Check file size (very large PDFs take longer)
2. Verify sufficient RAM available
3. For scanned PDFs, OCR is resource-intensive (expected)

---

## Getting Help

### Check the Documentation

- **README.md**: Complete architecture and API documentation
- **QUICKSTART.md**: Quick reference guide
- **config/vocabulary.yaml**: See all supported field labels

### Verify Your Setup

```bash
# Check Python version
python --version

# Check installed packages
pip list

# Verify Tesseract
tesseract --version

# Test with verbose mode
python cli.py your_policy.pdf --verbose
```

### Review Output Carefully

The parser provides detailed feedback:
- Confidence scores indicate extraction quality
- Warnings highlight potential issues
- Validation errors show critical problems

---

## Next Steps

After successfully running the parser:

1. **Integrate with your workflow**: Use the Python API in your application
2. **Customize vocabulary**: Add labels specific to your insurance providers
3. **Automate processing**: Create batch scripts for multiple documents
4. **Monitor accuracy**: Review confidence scores and validate extracted data
5. **Extend functionality**: Add new fields or customize extraction logic

For advanced usage and API integration, refer to the README.md file.
