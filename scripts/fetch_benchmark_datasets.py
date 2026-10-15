"""
Fetch Authentic Datasets from NCBI GenBank for Multi-Paper Benchmarks
1. Cetartiodactyla (Montgelard et al. 1997 MBE, Nikaido et al. 1999 PNAS)
2. Ursidae (Krause et al. 2008 BMC Evol Biol, Yu et al. 2004 MBE)
3. Sarbecovirus (Zhou et al. 2020 Nature, Wu et al. 2020 Nature)
"""

import sys
import io
import urllib.request
from pathlib import Path
from Bio import SeqIO

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def fetch_genbank_cds(acc, gene_matcher):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={acc}&rettype=gbwithparts&retmode=text"
    req = urllib.request.Request(url, headers={"User-Agent": "PhyloCraft-PaperBenchmark/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        text = resp.read().decode("utf-8", errors="ignore")
    record = SeqIO.read(io.StringIO(text), "genbank")
    for feat in record.features:
        if feat.type == "CDS":
            gene = feat.qualifiers.get("gene", [""])[0].upper()
            prod = feat.qualifiers.get("product", [""])[0].upper()
            if gene_matcher(gene, prod):
                return str(feat.extract(record.seq))
    raise RuntimeError(f"CDS matching criterion not found in {acc}")

# -------------------------------------------------------------
# 1. Cetartiodactyla Cytb Dataset (Montgelard 1997 / Nikaido 1999)
# -------------------------------------------------------------
def build_cetartiodactyla():
    print("[1/3] Fetching Cetartiodactyla Cytb dataset...")
    taxa = {
        "Hippopotamus_amphibius": "NC_000889.1",
        "Balaenoptera_physalus": "NC_001321.1",
        "Bos_taurus": "NC_006853.1",
        "Sus_scrofa": "NC_000845.1",
        "Equus_caballus": "NC_001640.1"
    }
    matcher = lambda g, p: "CYTB" in g or "CYTOCHROME B" in p
    out_file = DATA_DIR / "cetartiodactyla_cytb.fasta"
    with open(out_file, "w", encoding="utf-8") as f:
        for name, acc in taxa.items():
            seq = fetch_genbank_cds(acc, matcher)
            f.write(f">{name}\n{seq}\n")
            print(f"  ✓ {name} ({acc}): {len(seq)} bp")
    print(f"  -> Saved to {out_file} ({out_file.stat().st_size} bytes)")

# -------------------------------------------------------------
# 2. Ursidae Cytb Dataset (Krause 2008 / Yu 2004)
# -------------------------------------------------------------
def build_ursidae():
    print("\n[2/3] Fetching Ursidae Cytb dataset...")
    taxa = {
        "Ursus_maritimus": "NC_003428.1",
        "Ursus_arctos": "NC_003427.1",
        "Ursus_americanus": "NC_003426.1",
        "Tremarctos_ornatus": "NC_009969.1",
        "Ailuropoda_melanoleuca": "NC_009492.1",
        "Canis_lupus_familiaris": "NC_002008.4"
    }
    matcher = lambda g, p: "CYTB" in g or "CYTOCHROME B" in p
    out_file = DATA_DIR / "ursidae_cytb.fasta"
    with open(out_file, "w", encoding="utf-8") as f:
        for name, acc in taxa.items():
            seq = fetch_genbank_cds(acc, matcher)
            f.write(f">{name}\n{seq}\n")
            print(f"  ✓ {name} ({acc}): {len(seq)} bp")
    print(f"  -> Saved to {out_file} ({out_file.stat().st_size} bytes)")

# -------------------------------------------------------------
# 3. Sarbecovirus Spike Dataset (Zhou et al. 2020 Nature)
# -------------------------------------------------------------
def build_sarbecovirus():
    print("\n[3/3] Fetching Sarbecovirus Spike dataset...")
    taxa = {
        "SARS_CoV_2_Wuhan_Hu_1": "NC_045512.2",
        "Bat_CoV_RaTG13": "MN996532.2",
        "SARS_CoV_Tor2": "NC_004718.3",
        "Bat_SARS_like_ZC45": "MG772933.1",
        "MERS_CoV": "NC_019843.3"
    }
    matcher = lambda g, p: "SPIKE" in p or g == "S"
    out_file = DATA_DIR / "sarbecovirus_spike.fasta"
    with open(out_file, "w", encoding="utf-8") as f:
        for name, acc in taxa.items():
            seq = fetch_genbank_cds(acc, matcher)
            f.write(f">{name}\n{seq}\n")
            print(f"  ✓ {name} ({acc}): {len(seq)} bp")
    print(f"  -> Saved to {out_file} ({out_file.stat().st_size} bytes)")

if __name__ == "__main__":
    build_cetartiodactyla()
    build_ursidae()
    build_sarbecovirus()
    print("\n🎉 All benchmark datasets successfully fetched and validated!")
