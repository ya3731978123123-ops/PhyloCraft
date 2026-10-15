"""
Unit Tests for Target Gene Extractor (GeneExtractor)
"""

import sys
import io
from pathlib import Path
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.gene_extractor import GeneExtractor, ExtractedGeneRecord

def test_gene_extractor_feature_table():
    print("Testing GeneExtractor with annotated GenBank SeqRecord...")
    # Build a synthetic 2000 bp mitochondrial genome
    dna = "A" * 500 + "ATG" + "GCT" * 100 + "TAA" + "C" * 1000
    rec = SeqRecord(Seq(dna), id="NC_999999.1", name="TestMito")
    rec.annotations["organism"] = "Ursus testicus"

    # Add CDS feature for CYTB at [500:803]
    feat = SeqFeature(
        FeatureLocation(500, 803, strand=1),
        type="CDS",
        qualifiers={"gene": ["CYTB"], "product": ["cytochrome b"]}
    )
    rec.features.append(feat)

    # Add COX1 feature at [1000:1500]
    feat2 = SeqFeature(
        FeatureLocation(1000, 1500, strand=-1),
        type="CDS",
        qualifiers={"gene": ["COI"], "product": ["cytochrome c oxidase subunit I"]}
    )
    rec.features.append(feat2)

    # 1. Extract CYTB
    res_cytb = GeneExtractor.extract_gene_from_record(rec, "CYTB")
    assert res_cytb is not None
    assert res_cytb.gene_symbol == "CYTB"
    assert res_cytb.seq_length == 303
    assert res_cytb.start == 501
    assert res_cytb.end == 803
    assert res_cytb.header == "Ursus_testicus|NC_999999.1:501-803(+)|CYTB"
    assert res_cytb.sha256_hash != ""
    assert res_cytb.ncbi_url == "https://www.ncbi.nlm.nih.gov/nuccore/NC_999999.1"
    print(f"  ✓ CYTB extracted: length {res_cytb.seq_length} bp, coordinates [{res_cytb.start}:{res_cytb.end}]")

    # 2. Extract COX1 by alias
    res_cox = GeneExtractor.extract_gene_from_record(rec, "COX1")
    assert res_cox is not None
    assert res_cox.seq_length == 500
    assert res_cox.strand == -1
    print(f"  ✓ COX1 (COI alias) extracted on negative strand: length {res_cox.seq_length} bp")

    # 3. Extract non-existent gene
    res_none = GeneExtractor.extract_gene_from_record(rec, "RBCL")
    assert res_none is None
    print("  ✓ Non-existent gene correctly returned None")

    print("\n🎉 GeneExtractor core logic passed 100%!")

if __name__ == "__main__":
    test_gene_extractor_feature_table()
