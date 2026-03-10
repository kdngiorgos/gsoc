"""One-shot script to create truncated test PDFs from the full source PDFs.

Run from etl/:
    python scripts/make_test_pdfs.py
"""
from pathlib import Path
from pypdf import PdfReader, PdfWriter

PAIRS = [
    ("../../budget_past/1_1.pdf", "technical_acharne.pdf",    5,   0),  # pages 1-5
    ("../../budget_plan/2_1.pdf", "budget_palaio_faliro.pdf", 5, 102),  # pages 103-107
    ("../../budget_plan/2_2.pdf", "budget_rodos.pdf",         5,   0),  # pages 1-5
]

out_dir = Path("../../test_pdfs")
out_dir.mkdir(exist_ok=True)

for src, dst, n_pages, start in PAIRS:
    src_path = Path(src)
    if not src_path.exists():
        print(f"SKIP {src} — file not found")
        continue
    reader = PdfReader(str(src_path))
    writer = PdfWriter()
    pages_to_copy = min(n_pages, len(reader.pages) - start)
    for i in range(start, start + pages_to_copy):
        writer.add_page(reader.pages[i])
    out_path = out_dir / dst
    with open(out_path, "wb") as f:
        writer.write(f)
    print(f"Created {out_path} ({pages_to_copy} pages from {src_path.name}, starting page {start + 1})")
