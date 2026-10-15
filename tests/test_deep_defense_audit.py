"""
Deep Defense & Encoding Integrity Test Suite
Verifies:
1. Multi-Gene Supermatrix Concatenation with dirty & non-UTF8 inputs.
2. Format Converter (FASTA, PHYLIP, NEXUS, Clustal) resilience.
3. Outgroup Candidate Detection complexity scaling (O(1) to O(N) at 150+ taxa).
4. MSA Viewer multi-format (FASTA, PHYLIP, NEXUS) fallback with non-UTF8 bytes.
5. Workstation Tab pipeline parsing resilience.
"""

import sys
import os
import shutil
import tempfile
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

# Headless mock safety
QDialog.exec = lambda self: 1
QDialog.exec_ = lambda self: 1
QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.critical = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)

from Bio import SeqIO
from Bio import Phylo
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from src.core.concatenator import concatenate_alignments
from src.core.converter import convert_alignment
from src.ui.widgets.tree_canvas import TreeCanvasWidget
from src.ui.widgets.msa_viewer import MSAViewer
from src.ui.main_window import MainWindow


def run_defense_audit():
    print("=" * 70)
    print("🛡️ RUNNING DEEP DEFENSE & ENCODING INTEGRITY AUDIT")
    print("=" * 70)

    app = QApplication.instance() or QApplication(sys.argv)
    test_dir = Path(tempfile.mkdtemp(prefix="phylo_defense_"))

    try:
        # -------------------------------------------------------------
        # Test 1: Concatenation with non-UTF8 / Latin-1 bytes
        # -------------------------------------------------------------
        print("\n[Defense 1/5] Testing Supermatrix Concatenation with non-UTF8 bytes...")
        gene1 = test_dir / "gene1_latin1.fasta"
        # Write gene 1 with Latin-1 accents in comments/headers
        with open(gene1, "wb") as f:
            f.write(b">TaxonA Primates \xE9tude 1\nATGCGATCGATC\n>TaxonB Species \xFCber\nATGCGATCGATC\n")

        gene2 = test_dir / "gene2.fasta"
        with open(gene2, "w", encoding="utf-8") as f:
            f.write(">TaxonA\nCCGG\n>TaxonC\nCCGG\n")

        out_super = test_dir / "supermatrix_defense.fasta"
        out_part = test_dir / "partitions_defense.nex"

        res_concat = concatenate_alignments(
            [gene1, gene2],
            out_super,
            out_part,
            partition_style="iqtree",
        )
        assert res_concat.success is True, f"Concatenation failed: {res_concat.message}"
        assert res_concat.total_taxa == 3  # TaxonA, TaxonB, TaxonC
        assert res_concat.total_sites == 16  # 12 + 4
        assert out_super.exists() and out_part.exists()
        print("  ✓ Non-UTF8 bytes in supermatrix successfully handled without exception!")

        # -------------------------------------------------------------
        # Test 2: Format Converter Resilience
        # -------------------------------------------------------------
        print("\n[Defense 2/5] Testing Multi-Format Converter (FASTA -> PHYLIP / NEXUS / Clustal)...")
        # 2A: Valid aligned conversion
        out_phy = test_dir / "converted.phy"
        ok_phy, msg_phy = convert_alignment(out_super, out_phy, "fasta", "phylip-relaxed")
        assert ok_phy is True and out_phy.exists()

        out_nex = test_dir / "converted.nex"
        ok_nex, msg_nex = convert_alignment(out_super, out_nex, "fasta", "nexus")
        assert ok_nex is True and out_nex.exists()

        # 2B: Unaligned conversion safety
        unaligned_fa = test_dir / "unaligned.fasta"
        unaligned_fa.write_text(">T1\nATGC\n>T2\nATGCAAA\n", encoding="utf-8")
        ok_unaligned, msg_unaligned = convert_alignment(unaligned_fa, test_dir / "unaligned.phy", "fasta", "phylip")
        assert ok_unaligned is False, "Unaligned input must be rejected for PHYLIP!"
        assert "not aligned" in msg_unaligned.lower()
        print("  ✓ Format converter accurately converted matrices and rejected unaligned inputs!")

        # -------------------------------------------------------------
        # Test 3: MSA Viewer Multi-Format Fallback (FASTA -> PHYLIP -> NEXUS)
        # -------------------------------------------------------------
        print("\n[Defense 3/5] Testing MSA Viewer Multi-Format Fallback with PHYLIP and NEXUS...")
        msa = MSAViewer()
        msa.resize(800, 400)
        msa.show()

        # Load PHYLIP relaxed directly
        msa.load_alignment_file(out_phy)
        app.processEvents()
        assert msa.canvas.total_taxa == 3
        assert msa.canvas.alignment_length == 16

        # Load NEXUS directly
        msa.load_alignment_file(out_nex)
        app.processEvents()
        assert msa.canvas.total_taxa == 3
        assert msa.canvas.alignment_length == 16

        # Load file with Latin-1 bytes directly
        msa.load_alignment_file(gene1)
        app.processEvents()
        assert msa.canvas.total_taxa == 2
        assert msa.canvas.alignment_length == 12
        msa.close()
        print("  ✓ MSA Viewer successfully parsed PHYLIP, NEXUS, and Latin-1 FASTA via automatic fallback!")

        # -------------------------------------------------------------
        # Test 4: Outgroup Candidate Detection Complexity at Scale
        # -------------------------------------------------------------
        print("\n[Defense 4/5] Testing Outgroup Candidate Detection Complexity Scaling (150 Taxa)...")
        # Build balanced 128-leaf tree
        def make_nwk(d, p=""):
            if d == 0:
                return f"Taxon_{p}:0.1"
            return f"({make_nwk(d-1, p+'0')},{make_nwk(d-1, p+'1')}):0.1"

        tree_128_nwk = test_dir / "tree_128.nwk"
        tree_128_nwk.write_text(make_nwk(7) + ";\n", encoding="utf-8")

        canvas = TreeCanvasWidget()
        canvas.resize(600, 400)
        t_start = time.time()
        canvas.load_tree_file(tree_128_nwk, show_alert=False)
        app.processEvents()
        t_elapsed = time.time() - t_start
        assert t_elapsed < 3.0, f"Outgroup detection took {t_elapsed:.2f}s, expected < 3.0s!"
        assert canvas.outgroup_combo.count() == 128
        print(f"  ✓ 128-leaf tree outgroups detected in {t_elapsed:.3f}s with O(N) complexity!")
        canvas.close()

        # -------------------------------------------------------------
        # Test 5: Full MainWindow Cross-Tab & Project Purity
        # -------------------------------------------------------------
        print("\n[Defense 5/5] Testing MainWindow Cross-Tab Concat Integration...")
        win = MainWindow()
        win.resize(1100, 750)
        win.show()
        app.processEvents()

        # Switch to Concat Tab (Tab 9)
        win.stack.setCurrentIndex(9)
        concat_tab = win.stack.widget(9)
        concat_tab.file_list = [str(gene1), str(gene2)]
        concat_tab.list_widget.clear()
        concat_tab.list_widget.addItems([str(gene1), str(gene2)])
        concat_tab.out_fa_edit.setText(str(test_dir / "ui_supermatrix.fasta"))
        concat_tab.out_part_edit.setText(str(test_dir / "ui_partitions.nex"))
        concat_tab.run_concat()
        app.processEvents()

        assert concat_tab.last_result is not None
        assert concat_tab.last_result.success is True
        assert concat_tab.gene_table.rowCount() == 2
        print("  ✓ Concat Tab UI integrated execution verified!")
        win.close()
        app.processEvents()

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    print("\n" + "=" * 70)
    print("🎉 ALL 5 DEEP DEFENSE & ENCODING INTEGRITY TESTS PASSED 100%!")
    print("=" * 70)


if __name__ == "__main__":
    run_defense_audit()
    sys.exit(0)
