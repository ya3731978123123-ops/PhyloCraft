"""
Unit & Stress Test for Clade Multi-Species Expansion & Primates P53 / TP53 Resolution.
Verifies that searching higher taxonomic groups (e.g. 靈長目, 靈長類, Primates, 節肢動物, 哺乳動物)
with common aliases (P53, TP53, etc.) automatically samples and expands to multi-species datasets,
preventing the single-species monopolization bug.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.gene_extractor import GeneExtractor

def test_primates_p53_resolution():
    print("\n--- 1. Testing '靈長目' + 'P53' Resolution ---")
    res1 = GeneExtractor.resolve_taxa_to_accessions("靈長目", "P53")
    print(f"Result count: {len(res1)}")
    for r in res1:
        print(" ", r[2])
    assert len(res1) >= 8, f"Expected at least 8 species, got {len(res1)}"
    species_names = [r[1] for r in res1]
    assert "Homo sapiens" in species_names, "Expected Homo sapiens in primates"
    # Ensure there are non-human primates as well!
    non_human = [sp for sp in species_names if sp != "Homo sapiens"]
    assert len(non_human) >= 7, f"Expected at least 7 non-human primates, got {len(non_human)}"
    print("✓ '靈長目' + 'P53' correctly expanded to multi-species primate dataset!")

def test_primates_tp53_resolution():
    print("\n--- 2. Testing 'Primates' + 'TP53' Resolution ---")
    res2 = GeneExtractor.resolve_taxa_to_accessions("Primates", "TP53")
    print(f"Result count: {len(res2)}")
    assert len(res2) >= 8, f"Expected at least 8 species, got {len(res2)}"
    print("✓ 'Primates' + 'TP53' verified!")

def test_arthropoda_p53_resolution():
    print("\n--- 3. Testing '節肢動物' + 'P53' Resolution ---")
    res3 = GeneExtractor.resolve_taxa_to_accessions("節肢動物", "P53")
    print(f"Result count: {len(res3)}")
    assert len(res3) >= 8, f"Expected at least 8 species, got {len(res3)}"
    print("✓ '節肢動物' + 'P53' verified!")

def test_mammalia_ins_resolution():
    print("\n--- 4. Testing '哺乳動物' + 'INS' Resolution ---")
    res4 = GeneExtractor.resolve_taxa_to_accessions("哺乳動物", "INS")
    print(f"Result count: {len(res4)}")
    assert len(res4) >= 8, f"Expected at least 8 species, got {len(res4)}"
    print("✓ '哺乳動物' + 'INS' verified!")

def test_gene_extraction_pipeline():
    print("\n--- 5. Testing Full Pipeline Extraction for Primates P53 ---")
    res = GeneExtractor.resolve_taxa_to_accessions("靈長目", "P53")
    # Take top 3 accessions and test extracting target gene P53
    sample_accs = [r[0] for r in res[:3]]
    out_fasta = PROJECT_ROOT / "tests" / "test_primates_extracted.fasta"
    result = GeneExtractor().extract_target_genes(
        targets=sample_accs,
        target_gene="P53",
        output_fasta=out_fasta
    )
    print(f"Extracted: {result.total_extracted}/{result.total_requested}")
    assert result.total_extracted == len(sample_accs), f"Expected {len(sample_accs)}, got {result.total_extracted}"
    for rec in result.records:
        print(f"  {rec.organism} | {rec.gene_symbol} | len={rec.seq_length} | CDS={rec.coordinates_str} | SHA={rec.sha256_hash[:8]}...")
    if out_fasta.exists():
        out_fasta.unlink()
    csv_f = out_fasta.with_suffix(".provenance.csv")
    md_f = out_fasta.with_suffix(".provenance.md")
    if csv_f.exists(): csv_f.unlink()
    if md_f.exists(): md_f.unlink()
    print("✓ Full extraction pipeline for Primates P53 succeeded!")

if __name__ == "__main__":
    test_primates_p53_resolution()
    test_primates_tp53_resolution()
    test_arthropoda_p53_resolution()
    test_mammalia_ins_resolution()
    test_gene_extraction_pipeline()
    print("\n🎉 ALL PRIMATES & CLADE EXPANSION TESTS PASSED!")
