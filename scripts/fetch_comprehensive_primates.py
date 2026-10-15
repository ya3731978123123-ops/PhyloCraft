"""
Save Comprehensive Order Primates Dataset (14 Taxa spanning all major clades)
"""

import sys
import io
import urllib.request
from pathlib import Path
from Bio import SeqIO

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PRIMATES = {
    "Human_Homo_sapiens": "NC_012920.1",
    "Chimpanzee_Pan_troglodytes": "NC_001643.1",
    "Bonobo_Pan_paniscus": "NC_001644.1",
    "Gorilla_Gorilla_gorilla": "NC_001645.1",
    "Sumatran_Orangutan_Pongo_abelii": "NC_002083.1",
    "Bornean_Orangutan_Pongo_pygmaeus": "NC_001646.1",
    "Gibbon_Hylobates_lar": "NC_002082.1",
    "Rhesus_Macaca_mulatta": "NC_005943.1",
    "Baboon_Papio_hamadryas": "NC_001992.1",
    "Marmoset_Callithrix_jacchus": "NC_025586.1",
    "Squirrel_Monkey_Saimiri_sciureus": "NC_012763.1",
    "Lemur_Lemur_catta": "NC_004025.1",
    "Mouse_Lemur_Microcebus_murinus": "NC_028634.1",
    "Treeshrew_Tupaia_belangeri": "NC_002521.1"
}

def fetch_cds(acc):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={acc}&rettype=gbwithparts&retmode=text"
    req = urllib.request.Request(url, headers={"User-Agent": "PhyloCraft-Benchmark/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        text = resp.read().decode("utf-8", errors="ignore")
    rec = SeqIO.read(io.StringIO(text), "genbank")
    for feat in rec.features:
        if feat.type == "CDS":
            gene = feat.qualifiers.get("gene", [""])[0].upper()
            prod = feat.qualifiers.get("product", [""])[0].upper()
            if "CYTB" in gene or "CYTOCHROME B" in prod:
                return str(feat.extract(rec.seq))
    raise RuntimeError(f"Cytb not found in {acc}")

def main():
    out_file = DATA_DIR / "primates_comprehensive_14_taxa.fasta"
    print(f"Fetching comprehensive Order Primates (14 taxa across all clades)...")
    with open(out_file, "w", encoding="utf-8") as f:
        for name, acc in PRIMATES.items():
            seq = fetch_cds(acc)
            f.write(f">{name}\n{seq}\n")
            print(f"  ✓ {name} ({acc}): {len(seq)} bp")
    print(f"Saved comprehensive dataset to {out_file} ({out_file.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
