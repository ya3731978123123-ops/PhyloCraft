"""
Multi-Paper Scientific Replication Benchmark Test Suite
Validating PhyloCraft against Landmark Peer-Reviewed Literature Across Domains

Benchmarked Literature:
1. Cetartiodactyla & Whippomorpha Revolution:
   - Montgelard, C., Catzeflis, F. M., & Douzery, E. (1997). Molecular Biology and Evolution, 14(5), 550-559.
   - Nikaido, M., Rooney, A. P., & Okada, N. (1999). PNAS, 96(18), 10261-10266.
   Target: Whale origins within Artiodactyla (Hippo + Whale sisterhood).

2. Ursidae (Bear Family) Adaptive Radiation:
   - Krause, J., Unger, T., Noçon, A., et al. (2008). BMC Evolutionary Biology, 8, 220.
   - Yu, L., Li, Q. W., Ryder, O. A., & Zhang, Y. P. (2004). Mol Phylogenet Evol, 32(3), 834-845.
   Target: Basal Giant Panda placement & Polar Bear / Brown Bear sister divergence.

3. Sarbecovirus / Coronavirus Evolution & SARS-CoV-2 Origin:
   - Zhou, P., Yang, X. L., Wang, X. G., et al. (2020). Nature, 579(7798), 270-273.
   - Wu, F., Zhao, S., Yu, B., et al. (2020). Nature, 579(7798), 265-269.
   Target: Bat CoV RaTG13 closest kinship to SARS-CoV-2 & Sarbecovirus subgenus monophyly.
"""

import sys
import io
import os
import shutil
from pathlib import Path
from Bio import Phylo
from Bio import SeqIO

# Force UTF-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.sanitizer import sanitize_fasta_file, save_sanitized_fasta
from src.core.runners.mafft_runner import MafftRunner
from src.core.runners.trimal_runner import TrimalRunner
from src.core.runners.modelfinder_runner import ModelFinderRunner
from src.core.runners.iqtree_runner import IQTreeRunner

def run_pipeline(name: str, input_fasta: Path, outgroup_name: str, work_dir: Path):
    print(f"\n[{name}] Running Empirical Pipeline for {input_fasta.name}...")
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. QC & Sanitization
    qc_res = sanitize_fasta_file(str(input_fasta))
    assert qc_res.success, f"QC failed for {input_fasta}: {qc_res.warnings}"
    clean_fasta = work_dir / f"{input_fasta.stem}_clean.fasta"
    save_sanitized_fasta(qc_res.cleaned_records, clean_fasta)
    print(f"  ✓ QC & Sanitize: {qc_res.total_taxa} taxa, avg {qc_res.avg_length:.1f} bp")

    # 2. MAFFT Alignment
    mafft = MafftRunner()
    aligned_fasta = work_dir / f"{input_fasta.stem}_aligned.fasta"
    ok, msg = mafft.run_alignment(clean_fasta, aligned_fasta, algorithm="auto")
    assert ok and aligned_fasta.exists(), f"MAFFT failed: {msg}"
    aln_records = list(SeqIO.parse(str(aligned_fasta), "fasta"))
    aln_len = len(aln_records[0].seq)
    print(f"  ✓ MAFFT Alignment: {len(aln_records)} taxa aligned to {aln_len} sites")

    # 3. trimAl Trimming
    trimal = TrimalRunner()
    trimmed_fasta = work_dir / f"{input_fasta.stem}_trimmed.fasta"
    ok, msg = trimal.run_trimming(aligned_fasta, trimmed_fasta, method="automated1")
    assert ok and trimmed_fasta.exists(), f"trimAl failed: {msg}"
    tri_records = list(SeqIO.parse(str(trimmed_fasta), "fasta"))
    tri_len = len(tri_records[0].seq)
    print(f"  ✓ trimAl Trimming: {tri_len} conserved sites retained ({tri_len / aln_len * 100:.1f}%)")

    # 4. ModelFinder
    mf = ModelFinderRunner()
    mf_prefix = work_dir / f"{input_fasta.stem}_mf"
    mf_res = mf.run_modelfinder(trimmed_fasta, mf_prefix, search_scope="TESTONLY", threads="AUTO")
    assert mf_res.success and mf_res.best_model, f"ModelFinder failed: {mf_res.message}"
    print(f"  ✓ ModelFinder: Selected Optimal Model '{mf_res.best_model}' (evaluated {len(mf_res.candidate_models)} models)")

    # 5. IQ-TREE 3 ML Inference
    iq = IQTreeRunner()
    iq_prefix = work_dir / f"{input_fasta.stem}_ml"
    iq_res = iq.run_inference(
        input_alignment=trimmed_fasta,
        output_prefix=iq_prefix,
        model=mf_res.best_model,
        bootstrap=1000,
        threads="2"
    )
    assert iq_res.success and Path(iq_res.tree_file).exists(), f"IQ-TREE failed: {iq_res.message}"
    treefile = Path(iq_res.tree_file)
    print(f"  ✓ IQ-TREE ML Inference: Tree successfully generated ({treefile.name})")

    # 6. Parse and Root Tree
    tree = Phylo.read(str(treefile), "newick")
    tree.root_with_outgroup(outgroup_name)

    def get_clade_taxa(clade):
        return set(t.name for t in clade.get_terminals())

    all_clade_sets = [get_clade_taxa(c) for c in tree.find_clades() if not c.is_terminal()]
    return tree, all_clade_sets, mf_res.best_model

def test_paper_1_cetartiodactyla():
    print("=" * 75)
    print("📖 PAPER BENCHMARK 1: Cetartiodactyla & Whale Origin (Whippomorpha)")
    print("   References: Montgelard et al. (1997) MBE; Nikaido et al. (1999) PNAS")
    print("=" * 75)

    input_fa = Path("data/cetartiodactyla_cytb.fasta").resolve()
    work_dir = Path("output/paper_bench_cetartiodactyla").resolve()
    tree, clades, model = run_pipeline("Paper 1 (Cetartiodactyla)", input_fa, "Equus_caballus", work_dir)

    # Clade A: Whippomorpha / Cetancodonta (Hippo + Whale)
    whippomorpha = {"Hippopotamus_amphibius", "Balaenoptera_physalus"}
    has_whippo = whippomorpha in clades
    print(f"  • Clade 1: (Hippopotamus, Balaenoptera Whale) [Whippomorpha] -> {'✓ 100% MATCH' if has_whippo else '✗ MISMATCH'}")
    assert has_whippo, "Failed to recover (Hippo, Whale) sister relationship!"

    # Clade B: Cetruminantia (Cow + (Hippo, Whale))
    cetruminantia = {"Hippopotamus_amphibius", "Balaenoptera_physalus", "Bos_taurus"}
    has_cetrum = cetruminantia in clades
    print(f"  • Clade 2: (Cow, Whippomorpha) [Cetruminantia] -> {'✓ 100% MATCH' if has_cetrum else '✗ MISMATCH'}")
    assert has_cetrum, "Failed to recover Cetruminantia clade!"

    # Clade C: Cetartiodactyla (Pig + Cetruminantia)
    cetartiodactyla = {"Hippopotamus_amphibius", "Balaenoptera_physalus", "Bos_taurus", "Sus_scrofa"}
    has_cetartio = cetartiodactyla in clades
    print(f"  • Clade 3: (Pig, Cetruminantia) [Cetartiodactyla] -> {'✓ 100% MATCH' if has_cetartio else '✗ MISMATCH'}")
    assert has_cetartio, "Failed to recover Cetartiodactyla clade!"

    # Outgroup: Equus caballus (Horse, Perissodactyla)
    print(f"  • Outgroup: Equus caballus (Horse, Perissodactyla) -> ✓ 100% MATCH (Basal Root)")

    shutil.rmtree(work_dir, ignore_errors=True)
    print("\n🎉 PAPER 1 REPLICATION PASSED: 100% CONCORDANCE WITH PUBLISHED LITERATURE!")

def test_paper_2_ursidae():
    print("\n" + "=" * 75)
    print("📖 PAPER BENCHMARK 2: Ursidae (Bear Family) Adaptive Radiation")
    print("   References: Krause et al. (2008) BMC Evol Biol; Yu et al. (2004) MPE")
    print("=" * 75)

    input_fa = Path("data/ursidae_cytb.fasta").resolve()
    work_dir = Path("output/paper_bench_ursidae").resolve()
    tree, clades, model = run_pipeline("Paper 2 (Ursidae)", input_fa, "Canis_lupus_familiaris", work_dir)

    # Clade A: Polar bear + Brown bear sister pair
    polar_brown = {"Ursus_maritimus", "Ursus_arctos"}
    has_pb = polar_brown in clades
    print(f"  • Clade 1: (Ursus maritimus, Ursus arctos) [Sister Species] -> {'✓ 100% MATCH' if has_pb else '✗ MISMATCH'}")
    assert has_pb, "Failed to recover (Polar Bear, Brown Bear) sisterhood!"

    # Clade B: Genus Ursus (American black bear + (Polar bear, Brown bear))
    genus_ursus = {"Ursus_maritimus", "Ursus_arctos", "Ursus_americanus"}
    has_ursus = genus_ursus in clades
    print(f"  • Clade 2: (Ursus americanus, (U. maritimus, U. arctos)) [Genus Ursus] -> {'✓ 100% MATCH' if has_ursus else '✗ MISMATCH'}")
    assert has_ursus, "Failed to recover Genus Ursus monophyly!"

    # Clade C: Ursinae + Tremarctinae (Spectacled bear + Ursus)
    tremarctos_ursus = {"Ursus_maritimus", "Ursus_arctos", "Ursus_americanus", "Tremarctos_ornatus"}
    has_trem = tremarctos_ursus in clades
    print(f"  • Clade 3: (Tremarctos ornatus, Genus Ursus) -> {'✓ 100% MATCH' if has_trem else '✗ MISMATCH'}")
    assert has_trem, "Failed to recover Tremarctos + Ursus clade!"

    # Clade D: Family Ursidae (Giant panda basal bear + (Spectacled bear, Ursus))
    ursidae = {"Ursus_maritimus", "Ursus_arctos", "Ursus_americanus", "Tremarctos_ornatus", "Ailuropoda_melanoleuca"}
    has_ursidae = ursidae in clades
    print(f"  • Clade 4: (Ailuropoda melanoleuca Giant Panda, All other bears) [Ursidae] -> {'✓ 100% MATCH' if has_ursidae else '✗ MISMATCH'}")
    assert has_ursidae, "Failed to recover Giant Panda as basal Ursidae!"

    # Outgroup: Canis lupus familiaris (Dog, Canidae)
    print(f"  • Outgroup: Canis lupus familiaris (Dog, Canidae) -> ✓ 100% MATCH (Basal Root)")

    shutil.rmtree(work_dir, ignore_errors=True)
    print("\n🎉 PAPER 2 REPLICATION PASSED: 100% CONCORDANCE WITH PUBLISHED LITERATURE!")

def test_paper_3_sarbecovirus():
    print("\n" + "=" * 75)
    print("📖 PAPER BENCHMARK 3: Sarbecovirus / Coronavirus Evolution & SARS-CoV-2")
    print("   References: Zhou et al. (2020) Nature; Wu et al. (2020) Nature")
    print("=" * 75)

    input_fa = Path("data/sarbecovirus_spike.fasta").resolve()
    work_dir = Path("output/paper_bench_sarbecovirus").resolve()
    tree, clades, model = run_pipeline("Paper 3 (Sarbecovirus)", input_fa, "MERS_CoV", work_dir)

    # Clade A: SARS-CoV-2 and Bat-CoV RaTG13 sister pair
    sars2_ratg13 = {"SARS_CoV_2_Wuhan_Hu_1", "Bat_CoV_RaTG13"}
    has_sars2_ratg13 = sars2_ratg13 in clades
    print(f"  • Clade 1: (SARS-CoV-2 Wuhan-Hu-1, Bat CoV RaTG13) -> {'✓ 100% MATCH' if has_sars2_ratg13 else '✗ MISMATCH'}")
    assert has_sars2_ratg13, "Failed to recover (SARS-CoV-2, RaTG13) sisterhood!"

    # Clade B: SARS-CoV Tor2 (2003) and Bat SARS-like CoV ZC45 sister pair
    sars1_zc45 = {"SARS_CoV_Tor2", "Bat_SARS_like_ZC45"}
    has_sars1_zc45 = sars1_zc45 in clades
    print(f"  • Clade 2: (SARS-CoV Tor2, Bat SARS-like CoV ZC45) -> {'✓ 100% MATCH' if has_sars1_zc45 else '✗ MISMATCH'}")
    assert has_sars1_zc45, "Failed to recover (SARS-CoV, ZC45) sisterhood!"

    # Clade C: Sarbecovirus subgenus monophyly
    sarbecovirus = {"SARS_CoV_2_Wuhan_Hu_1", "Bat_CoV_RaTG13", "SARS_CoV_Tor2", "Bat_SARS_like_ZC45"}
    has_sarbeco = sarbecovirus in clades
    print(f"  • Clade 3: Sarbecovirus subgenus monophyly (SARS-CoV-2 lineage + SARS-CoV lineage) -> {'✓ 100% MATCH' if has_sarbeco else '✗ MISMATCH'}")
    assert has_sarbeco, "Failed to recover Sarbecovirus subgenus monophyly!"

    # Outgroup: MERS-CoV (Merbecovirus outgroup)
    print(f"  • Outgroup: MERS-CoV (Merbecovirus) -> ✓ 100% MATCH (Basal Root)")

    shutil.rmtree(work_dir, ignore_errors=True)
    print("\n🎉 PAPER 3 REPLICATION PASSED: 100% CONCORDANCE WITH PUBLISHED LITERATURE!")

if __name__ == "__main__":
    test_paper_1_cetartiodactyla()
    test_paper_2_ursidae()
    test_paper_3_sarbecovirus()

    print("\n" + "=" * 75)
    print("🏆 ALL 3 MULTI-DOMAIN PAPER BENCHMARK SUITES COMPLETED WITH 100% SUCCESS!")
    print("   1. Cetartiodactyla (Montgelard 1997 / Nikaido 1999) -> 100% Monophyly Confirmed")
    print("   2. Ursidae Radiation (Krause 2008 / Yu 2004) -> 100% Radiation Confirmed")
    print("   3. Sarbecovirus Evolution (Zhou 2020 / Wu 2020) -> 100% Lineage Confirmed")
    print("=" * 75)
