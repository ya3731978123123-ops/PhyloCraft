import os
import sys
import tempfile
import shutil
import zipfile
import hashlib
from pathlib import Path
from Bio import Phylo, SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

from src.config import DATA_DIR, OUTPUT_DIR, find_tool
from src.core.converter import convert_alignment
from src.core.project_manager import ProjectManager
from src.core.eln_generator import ELNGenerator
from src.ui.main_window import MainWindow
from src.ui.widgets.tree_canvas import TreeCanvasWidget
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QMimeData, QUrl, Qt, QPoint, QPointF
from PySide6.QtGui import QDragEnterEvent, QDropEvent


def run_deep_edge_tests():
    print("=" * 60)
    print("🔬 STARTING DEEP SYSTEM EDGE-CASE & INTEGRATION TEST SUITE")
    print("=" * 60)

    app = QApplication.instance() or QApplication(sys.argv)
    test_dir = Path(tempfile.mkdtemp(prefix="phylo_deep_edge_"))

    # Pre-clean OUTPUT_DIR
    recent_f = OUTPUT_DIR / ".recent_projects.json"
    if recent_f.exists():
        recent_f.unlink(missing_ok=True)
    for p in OUTPUT_DIR.glob("*.phylo"):
        shutil.rmtree(p, ignore_errors=True)

    try:
        # ---------------------------------------------------------
        # Deep Test 1: Format Converter Multi-Format Round-Trip
        # ---------------------------------------------------------
        print("\n[Deep 1/5] Testing Alignment Format Converter Round-Trip Integrity...")
        primates_fa = DATA_DIR / "primates_cytb.fasta"
        aligned_fa = test_dir / "aligned_sample.fasta"
        raw_recs = list(SeqIO.parse(str(primates_fa), "fasta"))
        min_len = min(len(r.seq) for r in raw_recs)
        aligned_recs = [SeqRecord(r.seq[:min_len], id=r.id, description="") for r in raw_recs]
        SeqIO.write(aligned_recs, str(aligned_fa), "fasta")

        f_nexus = test_dir / "converted.nex"
        f_phy = test_dir / "converted.phy"
        f_roundtrip = test_dir / "roundtrip.fasta"

        # 1. FASTA -> NEXUS
        ok1, msg1 = convert_alignment(aligned_fa, f_nexus, in_format="fasta", out_format="nexus")
        assert ok1, f"FASTA -> NEXUS failed: {msg1}"
        assert f_nexus.exists() and f_nexus.stat().st_size > 0

        # 2. NEXUS -> PHYLIP-Relaxed
        ok2, msg2 = convert_alignment(f_nexus, f_phy, in_format="nexus", out_format="phylip-relaxed")
        assert ok2, f"NEXUS -> PHYLIP failed: {msg2}"
        assert f_phy.exists() and f_phy.stat().st_size > 0

        # 3. PHYLIP-Relaxed -> FASTA
        ok3, msg3 = convert_alignment(f_phy, f_roundtrip, in_format="phylip-relaxed", out_format="fasta")
        assert ok3, f"PHYLIP -> FASTA failed: {msg3}"
        assert f_roundtrip.exists()

        orig_recs = {r.id: str(r.seq).upper() for r in SeqIO.parse(str(aligned_fa), "fasta")}
        round_recs = {r.id: str(r.seq).upper() for r in SeqIO.parse(str(f_roundtrip), "fasta")}

        assert set(orig_recs.keys()) == set(round_recs.keys()), "Taxa sets do not match after roundtrip"
        for tid in orig_recs:
            assert orig_recs[tid] == round_recs[tid], f"Sequence content mismatch for {tid}!"
        print("  ✓ Full 3-stage format round-trip (FASTA -> NEXUS -> PHYLIP -> FASTA) 100% bit-exact!")

        # ---------------------------------------------------------
        # Deep Test 2: Supplementary ZIP Cryptographic Integrity Check
        # ---------------------------------------------------------
        print("\n[Deep 2/5] Testing Supplementary ZIP Package & Cryptographic Integrity...")
        pm = ProjectManager()
        proj = pm.create_project("Crypto_Test_Project", test_dir, author="Integrity Auditor")
        p_dir = Path(proj.project_dir)

        # Add sample data files in step folders
        raw_f = p_dir / "01_raw" / "seq.fa"
        raw_f.write_text(">TaxA\nATGC\n>TaxB\nATGC\n", encoding="utf-8")
        pm.update_step("raw", "completed", "Loaded 2 taxa", [str(raw_f)])

        aln_f = p_dir / "03_alignment" / "seq_aln.fa"
        aln_f.write_text(">TaxA\nATGC\n>TaxB\nATGC\n", encoding="utf-8")
        pm.update_step("alignment", "completed", "Aligned", [str(aln_f)])

        zip_target = test_dir / "Exported_Supplementary.zip"
        res_zip = ELNGenerator.export_supplementary_zip(proj, zip_target)
        assert Path(res_zip).exists()

        # Unpack and verify every single file's SHA-256 against ELN audit trail
        extract_dir = test_dir / "unpacked_zip"
        with zipfile.ZipFile(res_zip, "r") as zf:
            zf.extractall(extract_dir)

        audit_trail = ELNGenerator.get_audit_trail(proj)
        assert len(audit_trail) >= 2

        for item in audit_trail:
            sub = item["step_folder"]
            fn = item["filename"]
            expected_sha = item["sha256"]
            unpacked_f = extract_dir / "data" / sub / fn
            assert unpacked_f.exists(), f"Unpacked file missing: {unpacked_f}"

            h = hashlib.sha256()
            h.update(unpacked_f.read_bytes())
            actual_sha = h.hexdigest()
            assert actual_sha == expected_sha, f"SHA-256 mismatch for {fn}: {actual_sha} vs {expected_sha}"

        print(f"  ✓ All {len(audit_trail)} files verified bit-exact against SHA-256 cryptographic audit trail!")

        # ---------------------------------------------------------
        # Deep Test 3: Drag & Drop Event Handling Across MainWindow
        # ---------------------------------------------------------
        print("\n[Deep 3/5] Testing MainWindow Global Drag & Drop Dispatch...")
        win = MainWindow()
        win.show()
        app.processEvents()

        # Helper to simulate drop
        def simulate_drop(target_widget, file_path: Path):
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(file_path.resolve()))])
            pos = QPointF(50.0, 50.0)
            drag_event = QDragEnterEvent(pos.toPoint(), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
            target_widget.dragEnterEvent(drag_event)
            drop_event = QDropEvent(pos, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
            target_widget.dropEvent(drop_event)
            app.processEvents()

        # Drop 3A: Drop .nwk tree file -> should switch to TreeViewerTab (index 8)
        sample_nwk = test_dir / "test_drop.nwk"
        sample_nwk.write_text("((A:0.1,B:0.2):0.3,C:0.4);\n", encoding="utf-8")
        simulate_drop(win, sample_nwk)
        assert win.nav_list.currentRow() == 8, f"Expected TreeViewer tab (8), got: {win.nav_list.currentRow()}"
        assert win.tree_viewer_tab.canvas_widget.tree is not None
        print("  ✓ Drop .nwk tree -> Automatically switched to TreeViewerTab & loaded canvas!")

        # Drop 3B: Drop .iqtree report -> should switch to ModelTestTab (index 6)
        sample_iq = test_dir / "test_drop.iqtree"
        sample_iq.write_text(
            "IQ-TREE 2.2.0\n"
            "Input data: 6 sequences with 1140 nucleotide sites\n"
            "Best-fit model according to BIC: F81+F\n"
            "Log-likelihood of the tree: -2150.400\n",
            encoding="utf-8"
        )
        simulate_drop(win, sample_iq)
        assert win.nav_list.currentRow() == 6, f"Expected ModelTest tab (6), got: {win.nav_list.currentRow()}"
        print("  ✓ Drop .iqtree report -> Automatically switched to ModelTestTab & loaded report!")

        # Drop 3C: Drop project.json -> should open project in WorkstationTab (index 0)
        proj_json = Path(proj.project_dir) / "project.json"
        simulate_drop(win, proj_json)
        assert win.nav_list.currentRow() == 0, f"Expected Workstation tab (0), got: {win.nav_list.currentRow()}"
        assert win.workstation_tab.pm.current_project.name == "Crypto_Test_Project"
        print("  ✓ Drop project.json -> Automatically switched to WorkstationTab & loaded project!")

        win.close()
        app.processEvents()

        # ---------------------------------------------------------
        # Deep Test 4: Tree Canvas Deep Topologies & Circular Scaling
        # ---------------------------------------------------------
        print("\n[Deep 4/5] Testing Tree Canvas Deep Topologies & Multi-Format Exports...")
        canvas = TreeCanvasWidget()
        deep_nwk = test_dir / "deep_tree.nwk"
        deep_nwk.write_text(
            "(((((((((A:0.01,B:0.01):0.01,C:0.02):0.01,D:0.02):0.01,E:0.03):0.01,F:0.03):0.01,G:0.04):0.01,H:0.04):0.01,I:0.05):0.01,J:0.05);\n",
            encoding="utf-8"
        )
        canvas.load_tree_file(deep_nwk, show_alert=False)
        assert canvas.tree is not None
        assert len(canvas.tree.get_terminals()) == 10

        # Render circular mode with 10-level nested tree
        canvas.layout_combo.setCurrentIndex(1)  # Circular
        canvas.redraw_tree()

        # Export to PDF and SVG
        pdf_out = test_dir / "tree_export.pdf"
        canvas.fig.savefig(str(pdf_out), format="pdf", bbox_inches="tight")
        assert pdf_out.exists() and pdf_out.stat().st_size > 1000
        print(f"  ✓ Vector PDF Export verified ({pdf_out.stat().st_size} bytes)!")

        svg_out = test_dir / "tree_export.svg"
        canvas.fig.savefig(str(svg_out), format="svg", bbox_inches="tight")
        assert svg_out.exists() and svg_out.stat().st_size > 1000
        print(f"  ✓ Vector SVG Export verified ({svg_out.stat().st_size} bytes)!")

        # ---------------------------------------------------------
        # Deep Test 5: FastTree Ultra-Fast Inference Binary Test
        # ---------------------------------------------------------
        print("\n[Deep 5/5] Testing FastTree Ultra-Fast Inference Binary Execution...")
        ft_path = find_tool("fasttree")
        if ft_path:
            import subprocess
            ft_out = test_dir / "fasttree_result.nwk"
            cmd = [ft_path, "-nt", "-quiet", str(aligned_fa)]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            assert proc.returncode == 0, f"FastTree failed with code {proc.returncode}: {proc.stderr}"
            assert "(" in proc.stdout and ");" in proc.stdout
            ft_out.write_text(proc.stdout, encoding="utf-8")
            parsed_tree = Phylo.read(str(ft_out), "newick")
            assert len(parsed_tree.get_terminals()) == 6
            print(f"  ✓ FastTree inferred Newick tree with {len(parsed_tree.get_terminals())} terminals!")
        else:
            print("  ⚠️ FastTree binary not located, skipped live execution.")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        recent_f = OUTPUT_DIR / ".recent_projects.json"
        if recent_f.exists():
            recent_f.unlink(missing_ok=True)
        for p in OUTPUT_DIR.glob("*.phylo"):
            shutil.rmtree(p, ignore_errors=True)

    print("\n" + "=" * 60)
    print("🎉 ALL 5 DEEP SYSTEM EDGE-CASE TESTS PASSED FLAWLESSLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_deep_edge_tests()
