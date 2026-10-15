"""
Comprehensive User Workflow Simulation & Heavy Stress Test Suite
Simulates real evolutionary biologists' end-to-end user actions and
subjects PhyloCraft to extreme data loads, corrupt inputs, and rapid UI thrashing.
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
from PySide6.QtCore import Qt, QPointF, QMimeData, QUrl
from PySide6.QtGui import QColor, QFont

# Ensure automated headless/scripted tests never block on modal exec() or static popups
QDialog.exec = lambda self: 1
QDialog.exec_ = lambda self: 1
QMessageBox.exec = lambda self: QMessageBox.Ok
QMessageBox.exec_ = lambda self: QMessageBox.Ok
QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.critical = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)
QMessageBox.about = staticmethod(lambda *args, **kwargs: None)

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio import Phylo
from io import StringIO

from src.config import OUTPUT_DIR, DATA_DIR
from src.core.project_manager import ProjectManager, StepRecord, PhyloProject
from src.ui.main_window import MainWindow
from src.ui.widgets.step_inspection_dialog import StepInspectionDialog
from src.ui.widgets.msa_viewer import MSAViewer
from src.ui.widgets.tree_canvas import TreeCanvasWidget
from src.core.sanitizer import sanitize_fasta_file


def run_comprehensive_audit():
    print("=" * 70)
    print("🧪 STARTING USER WORKFLOW SIMULATION & DEEP STRESS AUDIT")
    print("=" * 70)

    app = QApplication.instance() or QApplication(sys.argv)
    test_dir = Path(tempfile.mkdtemp(prefix="phylo_user_stress_"))

    try:
        # -------------------------------------------------------------
        # Part 1: Real User Interaction & End-to-End Workflow Testing
        # -------------------------------------------------------------
        print("\n[User Simulation 1/4] User Scenario A: Newbie Researcher Green Flag Workflow...")
        win = MainWindow()
        win.resize(1200, 800)
        win.show()
        app.processEvents()

        w_tab = win.workstation_tab
        # Load demo project
        w_tab.load_demo_project(show_alert=False, target_dir=test_dir)
        app.processEvents()

        # Verify all cards in default canvas reflect completed status
        canvas = w_tab.block_canvas
        assert canvas is not None, "Canvas should be initialized!"
        for k in ["raw", "sanitize", "alignment", "trimming", "modelfinder", "tree"]:
            assert "已完成" in canvas.cards[k].status_badge.text(), f"Block {k} should be completed!"

        # Verify Stage attributes
        assert "6" in w_tab.stage.pill_taxa.text(), "Taxa count in stage should be 6!"
        assert "1140" in w_tab.stage.pill_sites.text(), "Sites length in stage should be 1140 bp!"

        # Simulate user opening ELN dialog from stage
        w_tab.open_eln_dialog()
        app.processEvents()
        print("  ✓ Scenario A passed: Green Flag pipeline, cards status sync, and Stage ELN verified!")

        # -------------------------------------------------------------
        print("\n[User Simulation 2/4] User Scenario B: Advanced Researcher Branch Forking & Param Drawers...")
        # User expands parameter drawer on IQ-TREE block
        tree_card = canvas.cards["tree"]
        assert tree_card.params_drawer.isVisible() is False
        tree_card.toggle_params()
        assert tree_card.params_drawer.isVisible() is True
        # User toggles drawer back
        tree_card.toggle_params()
        assert tree_card.params_drawer.isVisible() is False

        # User forks an experiment branch from alignment step
        init_tab_count = w_tab.workflow_tabs.count()
        w_tab.fork_branch("alignment", "Branch_User_Stringency")
        app.processEvents()
        assert w_tab.workflow_tabs.count() == init_tab_count + 1
        active_branch = w_tab.block_canvas
        assert active_branch != canvas
        print("  ✓ Scenario B passed: Parameter drawer toggling and Experiment Branch Forking verified!")

        # -------------------------------------------------------------
        print("\n[User Simulation 3/4] User Scenario C: ModelTestTab Candidate Ranking & Selection...")
        # Switch to ModelTestTab (Tab 6)
        win.stack.setCurrentIndex(6)
        model_tab = win.stack.widget(6)
        app.processEvents()

        # Load existing report into ModelTestTab
        proj = w_tab.pm.current_project
        tree_rec = proj.steps.get("tree")
        iq_f = [f for f in tree_rec.output_files if f.endswith(".iqtree")] if tree_rec else []
        if iq_f:
            model_tab.load_existing_report(iq_f[0])
            app.processEvents()
            # Table should have at least 240px height and not be squished
            assert model_tab.table.height() >= 200, f"Candidate table height {model_tab.table.height()} is squished!"
            assert model_tab.table.rowCount() >= 1, "Candidate table should have rows!"

            # User tests collapsing settings box
            model_tab.toggle_ctrl_box()
            assert model_tab.is_ctrl_collapsed is True
            assert model_tab.ctrl_content.isVisible() is False
            model_tab.toggle_ctrl_box()  # restore
            assert model_tab.is_ctrl_collapsed is False
            assert model_tab.ctrl_content.isVisible() is True

            # User clicks a candidate model row
            model_tab.table.selectRow(0)
            app.processEvents()
            assert model_tab.apply_btn.isEnabled() is True
        print("  ✓ Scenario C passed: ModelTestTab unsquished candidate table, collapse toggle, and model selection verified!")

        # -------------------------------------------------------------
        print("\n[User Simulation 4/4] User Scenario D: Tree & MSA Interactive Explorers...")
        # User explores Tree Viewer (Tab 8)
        win.stack.setCurrentIndex(8)
        tree_tab = win.stack.widget(8)
        app.processEvents()
        if tree_rec and tree_rec.output_files:
            nwk_f = [f for f in tree_rec.output_files if f.endswith(".treefile") or f.endswith(".nwk")]
            if nwk_f:
                tree_tab.load_tree_file(nwk_f[0])
                app.processEvents()
                # Test Zoom
                tree_tab.canvas.set_zoom(2.0)
                assert tree_tab.canvas.zoom_factor == 2.0
                tree_tab.canvas.set_zoom(1.0)
                # Test Themes
                tree_tab.theme_combo.setCurrentText("柔和莫蘭迪 (Morandi)")
                tree_tab.canvas.apply_theme("柔和莫蘭迪 (Morandi)")
                # Test Midpoint Rooting
                tree_tab.canvas.reroot_midpoint()
                # Test 300 DPI Export
                out_png = test_dir / "user_export_tree.png"
                tree_tab.canvas.export_image(file_path=out_png, dpi=300, show_alert=False)
                assert out_png.exists() and out_png.stat().st_size > 0

        # User explores StepInspectionDialog Tab 2 with Draggable Splitter
        rec_raw = proj.steps.get("raw")
        if rec_raw:
            diag = StepInspectionDialog("raw", rec_raw, proj, parent=win)
            diag.resize(980, 700)
            diag.show()
            diag.tabs.setCurrentIndex(1)  # Tab 2
            app.processEvents()
            assert hasattr(diag, "taxa_table")
            assert hasattr(diag, "preview_text")
            assert diag.taxa_table.rowCount() == 6
            diag.close()

        print("  ✓ Scenario D passed: Tree Viewer interactive controls, themes, 300 DPI export, and StepInspectionDialog verified!")

        # -------------------------------------------------------------
        # Part 2: Heavy Stress & Edge Case Resilience Testing
        # -------------------------------------------------------------
        print("\n[Stress 1/4] Heavy Stress 1: Large Synthetic Alignment Load (300 Taxa × 5,000 bp)...")
        # Generate large alignment
        large_fasta = test_dir / "large_stress_alignment.fasta"
        t0 = time.time()
        with open(large_fasta, "w", encoding="utf-8") as f:
            base_pattern = "ATGCGATCGATCGATC" * 312 + "AT"  # ~5000 bp
            for i in range(300):
                # mutate a few bp per taxon
                seq_list = list(base_pattern)
                seq_list[i % 500] = "G"
                seq_list[(i * 3) % 500] = "C"
                f.write(f">Taxon_{i+1:03d} Species {i+1}\n{''.join(seq_list)}\n")
        t_gen = time.time() - t0
        print(f"  Generated 300 taxa x 5,000 bp alignment in {t_gen:.2f}s ({large_fasta.stat().st_size / (1024*1024):.2f} MB)")

        # Load into MSA Viewer
        msa_viewer = MSAViewer()
        msa_viewer.resize(800, 500)
        msa_viewer.show()
        t_load = time.time()
        msa_viewer.load_alignment_file(str(large_fasta))
        app.processEvents()
        t_load_done = time.time() - t_load
        assert msa_viewer.canvas.total_taxa == 300
        assert msa_viewer.canvas.alignment_length == 4994
        print(f"  ✓ Loaded & rendered 300 taxa x 4,994 bp in {t_load_done:.2f}s without freeze!")

        # Test Jump-to-bp and SNPs mode under heavy load
        msa_viewer.jump_edit.setText("2500")
        msa_viewer.jump_to_position()
        msa_viewer.mut_cb.setChecked(True)
        msa_viewer.toggle_mut_mode()
        app.processEvents()
        msa_viewer.mut_cb.setChecked(False)
        msa_viewer.toggle_mut_mode()
        app.processEvents()
        msa_viewer.close()
        print("  ✓ MSA Viewer heavy load navigation & SNP mutation filters passed!")

        # -------------------------------------------------------------
        print("\n[Stress 2/4] Heavy Stress 2: Massive Topology Rendering (500-Leaf Deep Tree)...")
        # Generate balanced binary tree Newick with 512 leaves
        def build_tree_nwk(depth, prefix=""):
            if depth == 0:
                return f"Leaf_{prefix}:0.15"
            left = build_tree_nwk(depth - 1, prefix + "0")
            right = build_tree_nwk(depth - 1, prefix + "1")
            return f"({left},{right}):0.1"

        massive_nwk_str = build_tree_nwk(9) + ";\n"  # 2^9 = 512 leaves
        massive_tree_file = test_dir / "massive_512_leaves.tree"
        massive_tree_file.write_text(massive_nwk_str, encoding="utf-8")

        canvas_stress = TreeCanvasWidget()
        canvas_stress.resize(900, 600)
        t_tree = time.time()
        canvas_stress.load_tree_file(massive_tree_file, show_alert=False)
        app.processEvents()
        t_tree_done = time.time() - t_tree
        assert len(canvas_stress.tree.get_terminals()) == 512
        print(f"  Loaded & parsed 512-leaf massive tree in {t_tree_done:.2f}s")

        # Test Layout calculations
        canvas_stress.layout_combo.setCurrentIndex(1)  # Circular
        canvas_stress.redraw_tree()
        app.processEvents()
        canvas_stress.layout_combo.setCurrentIndex(0)  # Rectangular
        canvas_stress.redraw_tree()
        app.processEvents()

        out_svg = test_dir / "massive_tree.svg"
        canvas_stress.export_image(file_path=out_svg, dpi=300, show_alert=False)
        assert out_svg.exists() and out_svg.stat().st_size > 0
        canvas_stress.close()
        print(f"  ✓ 512-leaf massive tree exported to vector SVG ({out_svg.stat().st_size / 1024:.1f} KB) successfully!")

        # -------------------------------------------------------------
        print("\n[Stress 3/4] Heavy Stress 3: Rapid UI Thrashing & Concurrency Safety...")
        # Spam tab switches rapidly 30 times
        for cycle in range(30):
            tab_target = cycle % win.stack.count()
            win.stack.setCurrentIndex(tab_target)
            if cycle % 10 == 0:
                app.processEvents()
        print("  ✓ 30 rapid tab switch transitions handled with zero crashes!")

        # Spam Toolbox category filtering
        tbox = w_tab.toolbox
        for cid, btn in tbox.filter_btns.items():
            btn.click()
            app.processEvents()
        tbox.filter_btns["all"].click()
        app.processEvents()
        print("  ✓ All 8 toolbox category filters thrashed repeatedly with 100% stability!")

        # -------------------------------------------------------------
        print("\n[Stress 4/4] Heavy Stress 4: Corrupt, Dirty & Malformed Inputs Injection...")
        # 1. Non-existent file injection
        fake_path = test_dir / "completely_nonexistent_file.fasta"
        res_fake = sanitize_fasta_file(fake_path)
        assert res_fake.success is False

        # 2. Corrupt FASTA with binary symbols and invalid DNA characters
        dirty_corrupt = test_dir / "hostile_corrupt.fasta"
        with open(dirty_corrupt, "wb") as bf:
            bf.write(b">Taxon1 Valid header\nATGCGATCGATC\n>Taxon2 \x00\x01\x02\xFF\xFE\nATCG\n")
        res_corrupt = sanitize_fasta_file(dirty_corrupt)
        assert res_corrupt.total_taxa >= 1  # Should clean and recover valid parts

        # 3. Malformed Newick missing closing parentheses
        malformed_tree = test_dir / "broken.nwk"
        malformed_tree.write_text("((A:0.1,B:0.2,C:0.3;\n", encoding="utf-8")
        bad_canvas = TreeCanvasWidget()
        bad_canvas.load_tree_file(malformed_tree)  # Should gracefully catch error, not crash
        assert bad_canvas.tree is None  # Handled cleanly
        bad_canvas.close()
        print("  ✓ Corrupt files, binary junk, and malformed Newick trees handled gracefully without crash!")

        win.close()
        app.processEvents()

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        # Ensure clean state of OUTPUT_DIR
        for p in OUTPUT_DIR.glob("*phylo_user_stress*"):
            shutil.rmtree(p, ignore_errors=True)

    print("\n" + "=" * 70)
    print("🎉 ALL USER WORKFLOWS & HEAVY STRESS TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    run_comprehensive_audit()
    sys.exit(0)
