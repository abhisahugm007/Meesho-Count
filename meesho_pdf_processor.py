
import re
import pandas as pd
from collections import defaultdict
import PyPDF2
import fitz  # PyMuPDF
import sys
import os

def extract_sku_size_bulletproof(text):
    """
    Bulletproof extraction that handles the exact Meesho shipping label format
    """
    sku_size_data = []

    # Split by TAX INVOICE to get individual shipping labels
    labels = text.split("TAX INVOICE")

    for label_text in labels:
        if "Product Details" not in label_text:
            continue

        # Split into lines
        lines = [line.strip() for line in label_text.split('\n')]

        # Find Product Details section
        product_details_idx = -1
        for i, line in enumerate(lines):
            if "Product Details" in line:
                product_details_idx = i
                break

        if product_details_idx == -1:
            continue

        # Extract the section after Product Details
        section_lines = lines[product_details_idx:]

        # Check exact pattern match
        try:
            if (len(section_lines) >= 11 and 
                section_lines[1] == "SKU" and 
                section_lines[2] == "Size" and 
                section_lines[3] == "Qty" and 
                section_lines[4] == "Color" and 
                section_lines[5] == "Order No."):

                sku_value = section_lines[6]
                size_value = section_lines[7]
                qty_value = section_lines[8]

                # Validate that qty is "1" and values exist
                if qty_value == "1" and sku_value and size_value:
                    sku_size_data.append((sku_value, size_value))

        except (IndexError, KeyError):
            # If exact structure doesn't match, try flexible approach
            for i in range(len(section_lines)-10):
                if (section_lines[i] == "SKU" and 
                    section_lines[i+1] == "Size" and 
                    section_lines[i+2] == "Qty" and
                    i+7 < len(section_lines)):

                    sku_val = section_lines[i+5]  # SKU value
                    size_val = section_lines[i+6]  # Size value
                    qty_val = section_lines[i+7]   # Should be "1"

                    if qty_val == "1" and sku_val and size_val:
                        sku_size_data.append((sku_val, size_val))
                        break

    return sku_size_data

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file using multiple methods"""
    text = ""
    page_count = 0

    try:
        # Try PyMuPDF first (better accuracy)
        pdf_document = fitz.open(pdf_path)
        page_count = len(pdf_document)

        print(f"Processing {page_count} pages...")

        for page_num in range(page_count):
            if page_num % 50 == 0:  # Progress update every 50 pages
                print(f"  Processed {page_num}/{page_count} pages...")

            page = pdf_document[page_num]
            text += page.get_text()

        pdf_document.close()

    except Exception as e:
        print(f"PyMuPDF failed: {e}")
        print("Trying PyPDF2...")

        # Fallback to PyPDF2
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                page_count = len(pdf_reader.pages)

                for page_num, page in enumerate(pdf_reader.pages):
                    if page_num % 50 == 0:
                        print(f"  Processed {page_num}/{page_count} pages...")
                    text += page.extract_text()

        except Exception as e2:
            print(f"PyPDF2 also failed: {e2}")
            return "", 0

    return text, page_count

def process_pdf_file(pdf_path):
    """Process a single PDF file"""
    filename = os.path.basename(pdf_path)
    print(f"\n📄 Processing: {filename}")

    # Extract text
    text, page_count = extract_text_from_pdf(pdf_path)

    if not text:
        print(f"❌ Failed to extract text from {filename}")
        return None

    # Extract SKU-size pairs
    sku_size_pairs = extract_sku_size_bulletproof(text)

    # Count occurrences
    sku_size_counts = defaultdict(lambda: defaultdict(int))

    for sku, size in sku_size_pairs:
        sku_size_counts[sku][size] += 1

    # Calculate statistics
    total_items = len(sku_size_pairs)
    expected_labels = text.count("TAX INVOICE")
    accuracy = (total_items / expected_labels * 100) if expected_labels > 0 else 0

    print(f"📊 Results for {filename}:")
    print(f"  Total pages: {page_count}")
    print(f"  Expected labels (TAX INVOICE count): {expected_labels}")
    print(f"  Extracted SKU-size pairs: {total_items}")
    print(f"  Accuracy: {accuracy:.1f}%")

    if accuracy < 98:
        print(f"  ⚠️  WARNING: Accuracy is below 98%!")
    else:
        print(f"  ✅ Excellent accuracy!")

    return {
        'filename': filename,
        'page_count': page_count,
        'sku_size_counts': dict(sku_size_counts),
        'total_items': total_items,
        'expected_labels': expected_labels,
        'accuracy': accuracy,
        'raw_pairs': sku_size_pairs
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python meesho_processor.py <pdf_file_or_directory>")
        print("Example: python meesho_processor.py my_file.pdf")
        print("Example: python meesho_processor.py /path/to/pdf/directory/")
        return

    input_path = sys.argv[1]

    # Get list of PDF files to process
    pdf_files = []
    if os.path.isfile(input_path) and input_path.lower().endswith('.pdf'):
        pdf_files = [input_path]
    elif os.path.isdir(input_path):
        pdf_files = [os.path.join(input_path, f) for f in os.listdir(input_path) 
                     if f.lower().endswith('.pdf')]
    else:
        print(f"❌ Invalid path: {input_path}")
        return

    if not pdf_files:
        print("❌ No PDF files found!")
        return

    print(f"🔍 Found {len(pdf_files)} PDF file(s) to process")

    # Process all files
    all_results = []
    for pdf_file in pdf_files:
        result = process_pdf_file(pdf_file)
        if result:
            all_results.append(result)

    # Create summary
    print(f"\n📈 OVERALL SUMMARY:")
    print(f"Files processed: {len(all_results)}")

    total_pages = sum(r['page_count'] for r in all_results)
    total_items = sum(r['total_items'] for r in all_results)
    total_expected = sum(r['expected_labels'] for r in all_results)
    overall_accuracy = (total_items / total_expected * 100) if total_expected > 0 else 0

    print(f"Total pages: {total_pages}")
    print(f"Total expected labels: {total_expected}")
    print(f"Total extracted items: {total_items}")
    print(f"Overall accuracy: {overall_accuracy:.1f}%")

    # Create detailed CSV report
    rows = []
    for result in all_results:
        for sku, sizes in result['sku_size_counts'].items():
            for size, count in sizes.items():
                rows.append({
                    'File': result['filename'],
                    'SKU': sku,
                    'Size': size,
                    'Count': count
                })

    if rows:
        df = pd.DataFrame(rows)
        output_file = "meesho_sku_size_report.csv"
        df.to_csv(output_file, index=False)
        print(f"\n💾 Detailed report saved to: {output_file}")

        # Show summary by SKU
        print(f"\n📋 SKU Summary:")
        sku_summary = df.groupby('SKU')['Count'].sum().sort_values(ascending=False)
        for sku, total_count in sku_summary.items():
            print(f"  {sku}: {total_count} items")
            # Show size breakdown
            sku_sizes = df[df['SKU'] == sku].groupby('Size')['Count'].sum()
            for size, count in sku_sizes.items():
                print(f"    Size {size}: {count}")

    if overall_accuracy >= 98:
        print(f"\n✅ SUCCESS: Achieved {overall_accuracy:.1f}% accuracy!")
    else:
        print(f"\n⚠️  WARNING: Accuracy is {overall_accuracy:.1f}%, below 98% target")

if __name__ == "__main__":
    main()
