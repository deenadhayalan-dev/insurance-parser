#!/usr/bin/env python3
"""
Command-line interface for Insurance Document Parser.

Usage:
    python cli.py <pdf_file> [--output <json_file>] [--simple] [--verbose]

Examples:
    python cli.py policy.pdf
    python cli.py policy.pdf --output results.json
    python cli.py policy.pdf --simple
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.main import InsuranceDocumentParser


def print_extraction_summary(result):
    """Print a human-readable summary of extraction results"""
    print("\n" + "="*60)
    print("INSURANCE DOCUMENT PARSING RESULTS")
    print("="*60)
    
    print(f"\nDocument Type: {result.document_type}")
    print(f"Source File: {result.source_file}")
    print(f"OCR Processed: {'Yes' if result.is_ocr_processed else 'No'}")
    
    print("\n--- PRIMARY FINANCIAL FIELDS ---\n")
    
    fields = [
        ("Coverage Amount", result.coverage_amount),
        ("Base Premium", result.base_premium),
        ("Tax Amount", result.tax_amount),
        ("Total Premium", result.total_premium),
        ("Policy Start Date", result.policy_start_date),
        ("Policy End Date", result.policy_end_date),
        ("Policy Term", result.policy_term),
    ]
    
    for label, field in fields:
        confidence = field.confidence
        value = field.value
        
        status = "✓" if confidence in ['high', 'medium'] else "✗"
        
        if value is not None:
            print(f"{status} {label:20s}: {value} ({confidence})")
        else:
            print(f"{status} {label:20s}: Not found")
    
    print("\n--- SECONDARY FINANCIAL FIELDS ---\n")
    
    secondary = [
        ("Deductible Amount", result.deductible_amount),
        ("Co-pay Percentage", result.co_pay_percentage),
    ]
    
    for label, field in secondary:
        if field.value is not None:
            print(f"✓ {label:20s}: {field.value} ({field.confidence})")
        else:
            print(f"✗ {label:20s}: Not found")
    
    # Warnings and errors
    if result.validation_errors:
        print("\n--- VALIDATION ERRORS ---\n")
        for error in result.validation_errors:
            print(f"❌ {error}")
    
    if result.parsing_warnings:
        print("\n--- WARNINGS ---\n")
        for warning in result.parsing_warnings:
            print(f"⚠️  {warning}")
    
    print("\n" + "="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Parse insurance documents and extract financial fields',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s policy.pdf
  %(prog)s policy.pdf --output results.json
  %(prog)s policy.pdf --simple
        """
    )
    
    parser.add_argument(
        'pdf_file',
        type=str,
        help='Path to the insurance PDF document'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Save results to JSON file'
    )
    
    parser.add_argument(
        '-s', '--simple',
        action='store_true',
        help='Output simplified format (values only, no metadata)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output with extraction details'
    )
    
    parser.add_argument(
        '--vocab',
        type=str,
        help='Path to custom vocabulary YAML file'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    pdf_path = Path(args.pdf_file)
    if not pdf_path.exists():
        print(f"Error: File not found: {args.pdf_file}", file=sys.stderr)
        sys.exit(1)
    
    if pdf_path.suffix.lower() != '.pdf':
        print(f"Error: File must be a PDF: {args.pdf_file}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Initialize parser
        print(f"Parsing document: {args.pdf_file}")
        print("Please wait...\n")
        
        insurance_parser = InsuranceDocumentParser(vocabulary_path=args.vocab)
        
        # Parse document
        result = insurance_parser.parse_document(str(pdf_path))
        
        # Output results
        if args.simple:
            # Simple output
            simple_dict = result.to_simple_dict()
            import json
            print(json.dumps(simple_dict, indent=2, default=str))
        
        elif args.output:
            # Save to JSON file
            json_output = insurance_parser.parse_to_json(str(pdf_path), args.output)
            print_extraction_summary(result)
        
        else:
            # Print summary
            print_extraction_summary(result)
            
            if args.verbose:
                # Also print full JSON
                print("\n--- FULL JSON OUTPUT ---\n")
                import json
                print(result.model_dump_json(indent=2))
    
    except Exception as e:
        print(f"\nError during parsing: {e}", file=sys.stderr)
        
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        sys.exit(1)


if __name__ == '__main__':
    main()
