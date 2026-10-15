"""
Build Paper Benchmark Artifacts & Publication Figures
Saves treefiles to data/paper_benchmarks/ and exports high-res figures to artifact screens.
"""

import sys
import io
import os
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication
from Bio import Phylo

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.sanitizer import sanitize_fasta_file, save_sanitized_fasta
from src.core.runners.mafft_runner import MafftRunner
from src.core.runners.trimal_runner import TrimalRunner
from src.core.runners.modelfinder_runner import ModelFinderRunner
from src.core.runners.iqtree_runner import IQTreeRunner
from src.ui.widgets.tree_canvas import TreeCanvasWidget

ARTIFACT_DIR = Path(r"C:\Users\Alan\.gemini\antigravity\brain\b252e923-3bcb-4e1f-b6b5-41ade74e0f9b\screens\paper_trees")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
BENCHMARK_DIR = Path("data/paper_benchmarks").resolve()
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

PAPERS = [
    {
        "id": "primates",
        "title": "Primate Mitochondrial Phylogeny (Hayasaka et al. 1988 MBE)",
        "fasta": "data/primates_cytb_authentic.fasta",
        "outgroup": "Lemur_catta",
        "model": "TPM2u+F+G4"
    },
    {
        "id": "cetartiodactyla",
        "title": "Cetartiodactyla & Whale Origin (Montgelard et al. 1997 MBE)",
        "fasta": "data/cetartiodactyla_cytb.fasta",
        "outgroup": "Equus_caballus",
        "model": "GTR+F+G4"
    },
    {
        "id": "ursidae",
        "title": "Ursidae Radiation & Giant Panda (Krause et al. 2008 BMC Evol Biol)",
        "fasta": "data/ursidae_cytb.fasta",
        "outgroup": "Canis_lupus_familiaris",
        "model": "HKY+F+G4"
    },
    {
        "id": "sarbecovirus",
        "title": "Sarbecovirus Evolution & SARS-CoV-2 (Zhou et al. 2020 Nature)",
        "fasta": "data/sarbecovirus_spike.fasta",
        "outgroup": "MERS_CoV",
        "model": "TIM2+F+G4"
    }
]

def generate_benchmarks():
    app = QApplication.instance() or QApplication(sys.argv)
    mafft = MafftRunner()
    trimal = TrimalRunner()
    iqtree = IQTreeRunner()
    tmp_dir = Path("output/tmp_paper_build").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for item in PAPERS:
        print(f"\nProcessing {item['title']}...")
        fa_path = Path(item["fasta"]).resolve()
        assert fa_path.exists(), f"Missing {fa_path}"

        # 1. QC & Align
        clean_fa = tmp_dir / f"{item['id']}_clean.fasta"
        qc = sanitize_fasta_file(str(fa_path))
        save_sanitized_fasta(qc.cleaned_records, clean_fa)

        aln_fa = tmp_dir / f"{item['id']}_aln.fasta"
        mafft.run_alignment(clean_fa, aln_fa)

        trim_fa = tmp_dir / f"{item['id']}_trim.fasta"
        trimal.run_trimming(aln_fa, trim_fa, method="automated1")

        # 2. IQ-TREE Inference with 1,000 UFBoot
        out_prefix = BENCHMARK_DIR / f"{item['id']}_ml"
        iq_res = iqtree.run_inference(
            input_alignment=trim_fa,
            output_prefix=out_prefix,
            model=item["model"],
            bootstrap=1000,
            threads="2"
        )
        assert iq_res.success, f"IQ-TREE failed: {iq_res.message}"
        tree_file = Path(iq_res.tree_file)
        print(f"  ✓ Tree inferred: {tree_file.name}")

        # 3. Root tree with specified outgroup
        tree = Phylo.read(str(tree_file), "newick")
        tree.root_with_outgroup(item["outgroup"])
        rooted_treefile = BENCHMARK_DIR / f"{item['id']}_rooted.treefile"
        Phylo.write(tree, str(rooted_treefile), "newick")

        # 4. Render with TreeCanvasWidget & Export 300 DPI publication image
        widget = TreeCanvasWidget()
        widget.load_tree_file(rooted_treefile)
        widget.resize(1000, 650)
        img_dest = ARTIFACT_DIR / f"{item['id']}_publication_tree.png"
        widget.export_image(file_path=img_dest, dpi=300, show_alert=False)
        assert img_dest.exists(), f"Image export failed: {img_dest}"
        print(f"  ✓ High-DPI Publication Figure generated: {img_dest.name} ({img_dest.stat().st_size} bytes)")

    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n🎉 All 4 Paper Benchmark Treefiles & Publication Figures Generated!")

if __name__ == "__main__":
    generate_benchmarks()
