"""
Fetch Complete Family Ursidae Dataset: 100% of all 8 extant bear species on Earth + outgroups.
Reference: Krause et al. (2008) BMC Evolutionary Biology 8:220 (Figure 1).
"""

import sys
import io
import urllib.request
from pathlib import Path
from Bio import SeqIO

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TAXA = {
    "Giant_panda_Ailuropoda_melanoleuca": "NC_009492.1",
    "Spectacled_bear_Tremarctos_ornatus": "NC_009969.1",
    "Sloth_bear_Melursus_ursinus": "NC_009970.1",
    "Sun_bear_Helarctos_malayanus": "NC_009968.1",
    "Asian_black_bear_Ursus_thibetanus": "NC_009971.1",
    "American_black_bear_Ursus_americanus": "NC_003426.1",
    "Brown_bear_Ursus_arctos": "NC_003427.1",
    "Polar_bear_Ursus_maritimus": "NC_003428.1",
    "Harbor_seal_Phoca_vitulina": "NC_001325.1",
    "Dog_Canis_lupus_familiaris": "NC_002008.4"
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
    out_file = DATA_DIR / "ursidae_all_8_species_full.fasta"
    print(f"Fetching complete family Ursidae (all 8 extant species on Earth)...")
    with open(out_file, "w", encoding="utf-8") as f:
        for name, acc in TAXA.items():
            seq = fetch_cds(acc)
            f.write(f">{name}\n{seq}\n")
            print(f"  ✓ {name} ({acc}): {len(seq)} bp")
    print(f"Saved complete dataset to {out_file} ({out_file.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
