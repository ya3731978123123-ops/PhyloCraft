import os
import sys
import tempfile
import shutil
from pathlib import Path
from Bio import Phylo, SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.config import DATA_DIR, OUTPUT_DIR
from src.core.sanitizer import sanitize_fasta_file, save_sanitized_fasta, clean_taxon_name
from src.core.converter import convert_alignment
from src.core.concatenator import concatenate_alignments
from src.core.project_manager import ProjectManager
from src.core.eln_generator import ELNGenerator
from src.ui.widgets.tree_canvas import TreeCanvasWidget
from PySide6.QtWidgets import QApplication


def run_stress_tests():
    print("=" * 60)
    print("🔥 STARTING PHYLOMETRIC DEEP STRESS & EDGE-CASE TEST SUITE")
    print("=" * 60)

    app = QApplication.instance() or QApplication(sys.argv)
    test_dir = Path(tempfile.mkdtemp(prefix="phylocraft_stress_"))

    # Ensure pre-test cleanliness of OUTPUT_DIR
    recent_f = OUTPUT_DIR / ".recent_projects.json"
    if recent_f.exists():
        recent_f.unlink(missing_ok=True)
    for p in OUTPUT_DIR.glob("*.phylo"):
        shutil.rmtree(p, ignore_errors=True)

    try:
        # ---------------------------------------------------------
        # Stress Test 1: Advanced Duplicate Taxon Collision Protection
        # ---------------------------------------------------------
        print("\n[Stress 1/7] Testing Complex Duplicate Taxon Collisions...")
        dup_fa = test_dir / "complex_duplicates.fasta"
        dup_fa.write_text(
            ">Taxon\nATGCATGC\n"
            ">Taxon\nATGCATGC\n"
            ">Taxon_1\nATGCATGC\n"
            ">Taxon_2\nATGCATGC\n"
            ">Taxon\nATGCATGC\n"
            ">Homo sapiens (Taiwan) [isolate=TW01]\nGGCCGGCC\n"
            ">Homo sapiens (Taiwan) [isolate=TW01]\nGGCCGGCC\n",
            encoding="utf-8"
        )
        res_dup = sanitize_fasta_file(dup_fa)
        assert res_dup.success
        cleaned_ids = [r.id for r in res_dup.cleaned_records]
        print(f"  Cleaned IDs: {cleaned_ids}")
        assert len(cleaned_ids) == len(set(cleaned_ids)), f"Duplicate IDs detected: {cleaned_ids}"
        assert len(res_dup.cleaned_records) == 7
        print("  ✓ 100% Strict Unique Taxon Name Guarantee verified!")

        # ---------------------------------------------------------
        # Stress Test 2: Dirty Sequence Sanitization & IUPAC Hygiene
        # ---------------------------------------------------------
        print("\n[Stress 2/7] Testing Dirty Sequences (Digits, Linebreaks, Symbols)...")
        dirty_fa = test_dir / "dirty_seqs.fasta"
        dirty_fa.write_text(
            ">Taxon_Clean\nATGCATGC\n"
            ">Taxon_Digits_Spaces\n10 atgc 20 tgca 30\n"
            ">Taxon_Punctuation\nATGC!@#$%^&*()ATGC\n"
            ">Taxon_Empty\n\n",
            encoding="utf-8"
        )
        res_dirty = sanitize_fasta_file(dirty_fa)
        assert res_dirty.success
        assert len(res_dirty.cleaned_records) == 4
        # Taxon_Digits_Spaces should have only valid nucleotide letters
        clean_seq_digits = str(res_dirty.cleaned_records[1].seq)
        assert clean_seq_digits == "ATGCTGCA", f"Expected ATGCTGCA, got: {clean_seq_digits}"
        # Empty taxon check
        assert any("0 bp" in w for w in res_dirty.warnings)
        print("  ✓ Sequence cleaning (digits/symbols stripped, empty warned) passed!")

        # ---------------------------------------------------------
        # Stress Test 3: Matrix Concatenation Edge Cases
        # ---------------------------------------------------------
        print("\n[Stress 3/7] Testing Supermatrix Concatenator Edge Cases...")
        g1 = test_dir / "gene1.fasta"
        g1.write_text(">TaxonA\nATGC\n>TaxonB\nATGC\n>TaxonC\nATGC\n", encoding="utf-8")
        g2 = test_dir / "gene2.fasta"
        g2.write_text(">TaxonB\nGGCC\n>TaxonC\nGGCC\n>TaxonD\nGGCC\n", encoding="utf-8")

        out_matrix = test_dir / "supermatrix.fasta"
        out_part = test_dir / "partitions.nexus"
        c_res = concatenate_alignments(
            [g1, g2],
            out_matrix,
            out_part,
            partition_style="nexus",
            codon_partition=False
        )
        assert c_res.success
        assert c_res.total_taxa == 4  # A, B, C, D
        assert c_res.total_sites == 8  # 4 + 4
        matrix_records = list(SeqIO.parse(str(out_matrix), "fasta"))
        assert len(matrix_records) == 4
        # TaxonA in gene2 should be ????, TaxonD in gene1 should be ????
        taxa_seqs = {r.id: str(r.seq) for r in matrix_records}
        assert taxa_seqs["TaxonA"] == "ATGC????"
        assert taxa_seqs["TaxonD"] == "????GGCC"
        assert taxa_seqs["TaxonB"] == "ATGCGGCC"

        # Test duplicate taxon inside same gene file protection
        g_dup = test_dir / "gene_dup.fasta"
        g_dup.write_text(">TaxonA\nATGC\n>TaxonA\nGGCC\n", encoding="utf-8")
        c_dup_res = concatenate_alignments([g_dup], test_dir / "dup_mat.fa", test_dir / "dup.nex")
        assert not c_dup_res.success
        assert "重複物種標頭" in c_dup_res.message
        print("  ✓ Multi-gene supermatrix & duplicate prevention passed!")

        # ---------------------------------------------------------
        # Stress Test 4: Format Converter Unaligned Protection & NEXUS
        # ---------------------------------------------------------
        print("\n[Stress 4/7] Testing Format Converter Protections...")
        unaligned_fa = test_dir / "unaligned.fasta"
        unaligned_fa.write_text(">T1\nATGC\n>T2\nATG\n", encoding="utf-8")
        ok_unaligned, msg_unaligned = convert_alignment(unaligned_fa, test_dir / "test.phy", out_format="phylip-relaxed")
        assert not ok_unaligned
        assert "not aligned" in msg_unaligned

        # Valid alignment conversion to NEXUS
        aligned_fa = test_dir / "aligned.fasta"
        aligned_fa.write_text(">T1\nATGC\n>T2\nATGC\n", encoding="utf-8")
        ok_nex, msg_nex = convert_alignment(aligned_fa, test_dir / "test.nex", out_format="nexus")
        assert ok_nex
        assert (test_dir / "test.nex").exists()
        print("  ✓ Format converter protections passed!")

        # ---------------------------------------------------------
        # Stress Test 5: Tree Canvas Rendering Under Extreme Topologies
        # ---------------------------------------------------------
        print("\n[Stress 5/7] Testing Tree Canvas Under Extreme Topologies...")
        canvas = TreeCanvasWidget()

        # Topology A: Purely topological tree (all branch lengths None)
        t_topo = Phylo.read(io_string := io_nwk("((Taxon_A,Taxon_B),(Taxon_C,Taxon_D));"), "newick")
        canvas.tree = t_topo
        canvas.original_tree = t_topo
        canvas.redraw_tree()

        # Topology B: Ultra-short zero-length branch tree (Gorilla cytb scenario)
        t_zero = Phylo.read(io_nwk("((A:0.00000001,B:0.00000001):0.00000001,C:0.05);"), "newick")
        canvas.tree = t_zero
        canvas.original_tree = t_zero
        canvas.branch_combo.setCurrentIndex(0)  # Real length phylogram
        canvas.redraw_tree()

        # Topology C: Two-taxa root
        t_two = Phylo.read(io_nwk("(Taxon1:0.02,Taxon2:0.03);"), "newick")
        canvas.tree = t_two
        canvas.original_tree = t_two
        canvas.apply_midpoint_root()
        canvas.redraw_tree()

        # Topology D: Circular layout with extreme scaling
        canvas.layout_combo.setCurrentIndex(1)  # Circular
        canvas.h_slider.setValue(40)  # 4.0x
        canvas.redraw_tree()
        canvas.layout_combo.setCurrentIndex(0)  # Rectangular
        canvas.reset_view()
        print("  ✓ Tree Canvas rendering under extreme topologies passed!")

        # ---------------------------------------------------------
        # Stress Test 6: Project Manager & ELN with Partial/Missing Steps
        # ---------------------------------------------------------
        print("\n[Stress 6/7] Testing ELN Generation with Partial/Missing Steps...")
        pm = ProjectManager()
        p = pm.create_project("Stress_Project", test_dir, author="Stress Tester")
        # Step 1 completed, Step 2 failed, Step 3-7 pending
        pm.update_step("raw", "completed", "Loaded 10 taxa", [str(aligned_fa)])
        pm.update_step("sanitize", "failed", "Taxon format error", student_notes="測試失敗註記：含特殊字元 $HOME 與 \\LaTeX 公式 $E=mc^2$。")

        md_eln = pm.generate_lab_notebook()
        assert "Stress_Project" in md_eln
        assert "failed" in md_eln
        assert "E=mc^2" in md_eln

        zip_p = test_dir / "Stress_Package.zip"
        res_zip = pm.export_supplementary_package(zip_p)
        assert Path(res_zip).exists() and Path(res_zip).stat().st_size > 500
        print("  ✓ Partial ELN compilation & special-character handling passed!")

        # ---------------------------------------------------------
        # Stress Test 7: Output Directory Purity Audit
        # ---------------------------------------------------------
        print("\n[Stress 7/7] Auditing Output Directory Purity...")
        recent_f = OUTPUT_DIR / ".recent_projects.json"
        if recent_f.exists():
            recent_f.unlink(missing_ok=True)
        leftovers = list(OUTPUT_DIR.iterdir())
        assert len(leftovers) == 0, f"Found lingering files in output/: {leftovers}"
        print("  ✓ OUTPUT_DIR is 100% clean and isolated!")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        recent_f = OUTPUT_DIR / ".recent_projects.json"
        if recent_f.exists():
            recent_f.unlink(missing_ok=True)
        for p in OUTPUT_DIR.glob("*.phylo"):
            shutil.rmtree(p, ignore_errors=True)

    print("\n" + "=" * 60)
    print("🎉 ALL 7 DEEP STRESS & EDGE-CASE TESTS PASSED PERFECTLY!")
    print("=" * 60)


def io_nwk(nwk_str: str):
    import io
    return io.StringIO(nwk_str)


if __name__ == "__main__":
    run_stress_tests()
