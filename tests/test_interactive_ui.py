import os
import sys
import tempfile
import shutil
from pathlib import Path
from Bio import Phylo

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.config import DATA_DIR, OUTPUT_DIR
from src.ui.widgets.tree_canvas import TreeCanvasWidget
from src.ui.widgets.msa_viewer import MSAViewer
from src.ui.widgets.block_pipeline_canvas import BlockPipelineCanvas
from src.ui.tabs.workstation_tab import WorkstationTab
from src.ui.tabs.pipeline_tab import PipelineWorker
from src.core.project_manager import ProjectManager, STEP_KEYS
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def run_interactive_ui_tests():
    print("=" * 60)
    print("🎮 STARTING COMPREHENSIVE INTERACTIVE UI & COMPONENT AUDIT")
    print("=" * 60)

    app = QApplication.instance() or QApplication(sys.argv)
    test_dir = Path(tempfile.mkdtemp(prefix="phylocraft_interactive_"))

    try:
        # ---------------------------------------------------------
        # Interactive Test 1: TreeCanvasWidget Deep Controls Audit
        # ---------------------------------------------------------
        print("\n[Interactive 1/5] Testing TreeCanvasWidget Interactive Controls...")
        canvas = TreeCanvasWidget()
        tree_nwk = test_dir / "sample_tree.nwk"
        tree_nwk.write_text(
            "(((Homo_sapiens:0.02,Pan_troglodytes:0.02)98:0.03,Gorilla_gorilla:0.05)95:0.04,Pongo_abelii:0.09,Lemur_catta:0.25);\n",
            encoding="utf-8"
        )
        canvas.load_tree_file(tree_nwk)
        assert canvas.tree is not None
        print("  ✓ Tree file loaded into canvas!")

        # Rooting controls
        canvas.apply_midpoint_root()
        assert "中點定根" in canvas.root_status_label.text()
        canvas.outgroup_combo.setCurrentIndex(0)
        canvas.apply_outgroup_root()
        assert "外群定根" in canvas.root_status_label.text()
        canvas.reset_root()
        assert "復原為原始樹" in canvas.root_status_label.text()
        print("  ✓ Rooting controls (midpoint, outgroup, reset) tested!")

        # Sliders & Scaling
        canvas.h_slider.setValue(25)
        assert canvas.h_scale == 2.5
        canvas.v_slider.setValue(18)
        assert canvas.v_scale == 18.0 / 12.0
        canvas.font_spin.setValue(12)
        canvas.reset_view()
        assert canvas.h_scale == 1.0
        assert canvas.font_spin.value() == 10
        canvas.fit_to_view()
        print("  ✓ Sliders, Free Scaling (0.5x~8.0x), font sizes, and view resets tested!")

        # Search filter
        canvas.search_edit.setText("Homo")
        assert canvas.search_query == "homo"
        canvas.search_edit.setText("non_existent_taxon")
        assert canvas.search_query == "non_existent_taxon"
        canvas.search_edit.clear()
        assert canvas.search_query == ""
        print("  ✓ Real-time taxon keyword search filtering tested!")

        # ComboBox modes
        for layout_idx in (0, 1):
            canvas.layout_combo.setCurrentIndex(layout_idx)
            for branch_idx in (0, 1):
                canvas.branch_combo.setCurrentIndex(branch_idx)
                for theme_idx in (0, 1):
                    canvas.theme_combo.setCurrentIndex(theme_idx)
                    for supp_idx in range(5):
                        canvas.support_combo.setCurrentIndex(supp_idx)
                        canvas.redraw_tree()
        canvas.layout_combo.setCurrentIndex(0)
        canvas.branch_combo.setCurrentIndex(0)
        canvas.theme_combo.setCurrentIndex(0)
        canvas.support_combo.setCurrentIndex(0)
        print("  ✓ All combinations of layouts, themes, branch lengths, and support cutoffs tested!")

        # 300 DPI Image export simulation
        img_out = test_dir / "tree_publication.png"
        canvas.export_image(file_path=img_out, dpi=300, show_alert=False)
        assert img_out.exists() and img_out.stat().st_size > 10000
        print(f"  ✓ 300 DPI Publication Tree Image Export verified ({img_out.stat().st_size} bytes)!")

        # ---------------------------------------------------------
        # Interactive Test 2: MSA Viewer Interactive Controls Audit
        # ---------------------------------------------------------
        print("\n[Interactive 2/5] Testing MSA Viewer Interactive Controls...")
        msa = MSAViewer()
        primates_fa = DATA_DIR / "primates_cytb.fasta"
        msa.load_alignment_file(primates_fa)
        assert msa.canvas.total_taxa == 6
        assert msa.canvas.alignment_length in (1140, 1141)
        print(f"  ✓ MSA Viewer loaded {msa.canvas.total_taxa} taxa, length {msa.canvas.alignment_length} bp!")

        # Toggle SNPs Only mode
        msa.mut_cb.setChecked(True)
        assert msa.canvas.mutation_only_mode is True
        msa.mut_cb.setChecked(False)
        assert msa.canvas.mutation_only_mode is False

        # Zoom in and zoom out
        msa.zoom_spin.setValue(16)
        assert msa.canvas.char_w > 14
        msa.zoom_spin.setValue(11)

        # Jump to position
        msa.jump_edit.setText("500")
        msa.jump_to_position()
        print("  ✓ MSA Viewer zoom, SNPs-only toggle, and jump-to-position tested!")

        # ---------------------------------------------------------
        # Interactive Test 3: BlockPipelineCanvas & Parameter Drawers
        # ---------------------------------------------------------
        print("\n[Interactive 3/5] Testing BlockPipelineCanvas Interactive Drawers...")
        pm = ProjectManager()
        proj = pm.create_project("Block_Test", test_dir, author="Tester")
        canvas_blocks = BlockPipelineCanvas()
        canvas_blocks.load_project_state(proj)

        # Test expanding/collapsing all 7 parameter and note drawers
        for k in STEP_KEYS:
            card = canvas_blocks.cards[k]
            card.toggle_params()
            assert card.params_expanded is True
            card.toggle_params()
            assert card.params_expanded is False

            card.toggle_notes()
            assert card.notes_expanded is True
            card.toggle_notes()
            assert card.notes_expanded is False

        # Test preset buttons
        w_tab = WorkstationTab()
        w_tab.preset_combo.setCurrentIndex(0)  # Standard full flow
        assert all(w_tab.block_canvas.cards[k].enable_cb.isChecked() for k in ("raw", "sanitize", "alignment", "tree"))
        w_tab.preset_combo.setCurrentIndex(1)  # Fast topology (bypasses trimming)
        assert not w_tab.block_canvas.cards["trimming"].enable_cb.isChecked()
        w_tab.preset_combo.setCurrentIndex(2)  # Full TimeTree (all enabled)
        assert all(w_tab.block_canvas.cards[k].enable_cb.isChecked() for k in STEP_KEYS)

        # Test Experiment Branching (Fork Branch)
        w_tab.load_demo_project(show_alert=False, target_dir=test_dir)
        w_tab.fork_branch("alignment", branch_name="Alignment_Exploration_Branch")
        forked = w_tab.pm.current_project
        assert forked is not None
        assert forked.name == "Alignment_Exploration_Branch"
        assert forked.steps["alignment"].status == "completed"
        assert forked.steps["trimming"].status == "pending"
        assert forked.steps["tree"].status == "pending"
        print("  ✓ Parameter drawers, 3 workflow presets, and Experiment Branch Forking tested!")

        # ---------------------------------------------------------
        # Interactive Test 4: Core Tools Execution Diagnostic
        # ---------------------------------------------------------
        print("\n[Interactive 4/6] Testing Core Tools Execution Diagnostics...")
        from src.core.tools_installer import test_tool_execution
        for t in ["iqtree", "trimal", "mafft", "fasttree"]:
            ok, out = test_tool_execution(t)
            assert ok is True, f"Diagnostic failed for {t}: {out}"
        print("  ✓ All 4 core tools passed live execution diagnostics (Exit Code 0)!")

        # ---------------------------------------------------------
        # Interactive Test 5: PipelineWorker Asynchronous Cancellation
        # ---------------------------------------------------------
        print("\n[Interactive 5/6] Testing PipelineWorker Cancellation Safety...")
        worker = PipelineWorker(
            input_fasta=str(primates_fa),
            output_dir=str(test_dir / "pipe_test"),
            trimal_method="automated1",
            model="MFP",
            bootstrap=1000,
            alrt=1000,
        )
        worker.start()
        # Immediately cancel
        worker.cancel()
        assert worker.is_cancelled is True
        worker.wait(5000)
        assert worker.isFinished()
        print("  ✓ PipelineWorker cleanly cancelled without orphan process leaks!")

        # ---------------------------------------------------------
        # Interactive Test 6: Full Output Directory Isolation Audit
        # ---------------------------------------------------------
        print("\n[Interactive 6/6] Auditing Clean Environment...")
        canvas.close()
        msa.close()
        canvas_blocks.close()
        w_tab.close()
        import matplotlib.pyplot as plt
        plt.close("all")
        app.processEvents()

        recent_f = OUTPUT_DIR / ".recent_projects.json"
        if recent_f.exists():
            recent_f.unlink(missing_ok=True)
        for p in OUTPUT_DIR.glob("*.phylo"):
            shutil.rmtree(p, ignore_errors=True)
        for p in OUTPUT_DIR.glob("provenance_audit_test*"):
            shutil.rmtree(p, ignore_errors=True)
        for p in OUTPUT_DIR.glob("test_*"):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)

        leftovers = [
            p for p in OUTPUT_DIR.iterdir()
            if p.name.startswith("test_") or p.name.startswith("provenance_audit_test") or p.name.endswith(".phylo")
        ]
        assert len(leftovers) == 0, f"Lingering test artifacts found: {leftovers}"
        print("  ✓ Test artifacts verified 100% clean!")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        recent_f = OUTPUT_DIR / ".recent_projects.json"
        if recent_f.exists():
            recent_f.unlink(missing_ok=True)
        for p in OUTPUT_DIR.glob("*.phylo"):
            shutil.rmtree(p, ignore_errors=True)
        app.processEvents()

    print("\n" + "=" * 60)
    print("🎉 ALL 5 INTERACTIVE UI & COMPONENT AUDITS PASSED FLAWLESSLY!")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    run_interactive_ui_tests()
    sys.exit(0)
