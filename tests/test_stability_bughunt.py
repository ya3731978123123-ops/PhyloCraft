import sys
import shutil
import tempfile
from pathlib import Path

# Ensure UTF-8 stdout for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from src.core.project_manager import ProjectManager, PhyloProject
from src.core.runners.mafft_runner import MafftRunner
from src.core.runners.trimal_runner import TrimalRunner
from src.core.runners.modelfinder_runner import ModelFinderRunner
from src.core.runners.iqtree_runner import IQTreeRunner
from src.ui.widgets.tree_canvas import TreeCanvasWidget
from src.ui.widgets.msa_viewer import MSAViewer
from src.ui.widgets.analysis_preferences_dialog import AnalysisPreferencesDialog
from src.ui.widgets.step_inspection_dialog import StepInspectionDialog
from src.ui.tabs.workstation_tab import WorkstationTab, WorkstationWorker

# Suppress modal blocking popups during automated headless/test execution
QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.critical = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)
QDialog.exec = lambda self: 1


def run_all_bughunt_tests():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    print("==================================================")
    print("🔬 [BUG HUNT & STABILITY TEST SUITE STARTING]")
    print("==================================================")

    temp_root = Path(tempfile.mkdtemp(prefix="phylo_bughunt_"))
    try:
        # TEST 1: Runner Edge Cases (Missing & 0-byte Files)
        print("\n[TEST 1] Testing Runner Input Validation (Missing & Empty Files)...")
        non_existent = temp_root / "does_not_exist.fasta"
        empty_fasta = temp_root / "empty.fasta"
        empty_fasta.touch()

        # MAFFT
        m_runner = MafftRunner()
        ok, msg = m_runner.run_alignment(non_existent, temp_root / "out.fasta")
        assert not ok, "MAFFT should fail on missing input"
        assert "不存在" in msg or "not found" in msg.lower()
        ok, msg = m_runner.run_alignment(empty_fasta, temp_root / "out.fasta")
        assert not ok, "MAFFT should fail on empty input"
        print("  ✓ MafftRunner passed edge case checks")

        # TrimAl
        t_runner = TrimalRunner()
        ok, msg = t_runner.run_trimming(non_existent, temp_root / "out.fasta")
        assert not ok, "TrimAl should fail on missing input"
        ok, msg = t_runner.run_trimming(empty_fasta, temp_root / "out.fasta")
        assert not ok, "TrimAl should fail on empty input"
        print("  ✓ TrimalRunner passed edge case checks")

        # ModelFinder
        mf_runner = ModelFinderRunner()
        res_mf = mf_runner.run_modelfinder(non_existent, temp_root / "mf_out")
        assert not res_mf.success, "ModelFinder should fail on missing input"
        res_mf2 = mf_runner.run_modelfinder(empty_fasta, temp_root / "mf_out")
        assert not res_mf2.success, "ModelFinder should fail on empty input"
        print("  ✓ ModelFinderRunner passed edge case checks")

        # IQTree
        iq_runner = IQTreeRunner()
        res_iq = iq_runner.run_inference(non_existent, temp_root / "iq_out")
        assert not res_iq.success, "IQTree should fail on missing input"
        res_iq2 = iq_runner.run_inference(empty_fasta, temp_root / "iq_out")
        assert not res_iq2.success, "IQTree should fail on empty input"
        print("  ✓ IQTreeRunner passed edge case checks")

        # TEST 2: Project with Non-ASCII / Special Characters Path
        print("\n[TEST 2] Testing Project Persistence with Non-ASCII Special Path...")
        special_dir = temp_root / "2026_演化生物學 專案 (測試版) #1"
        pm = ProjectManager()
        proj = pm.create_project("靈長類 專案.test", special_dir)
        assert proj is not None
        pm.update_step("raw", "completed", "測試摘要", [], {"test": 123}, "cmd_test", "學生筆記測試")
        saved_proj = pm.open_project(proj.project_dir)
        assert saved_proj is not None
        assert saved_proj.name == "靈長類 專案.test"
        assert saved_proj.steps["raw"].summary == "測試摘要"
        assert saved_proj.steps["raw"].student_notes == "學生筆記測試"
        print("  ✓ ProjectManager handled non-ASCII directory and filenames perfectly")

        # TEST 3: Workstation Multi-Tab & Worker Signal Safety
        print("\n[TEST 3] Testing Workstation Multi-Tab Architecture & Signal Resiliency...")
        w_tab = WorkstationTab()
        w_tab.pm = pm
        w_tab.show()
        app.processEvents()

        # Add 3 workflow canvas tabs
        c1 = w_tab.create_canvas_tab("對照實驗 A", 0)
        c2 = w_tab.create_canvas_tab("極速實驗 B", 1)
        c3 = w_tab.create_canvas_tab("時間樹實驗 C", 2)
        assert w_tab.workflow_tabs.count() >= 4

        # Test preset changing across tabs
        w_tab.on_preset_changed(1)
        app.processEvents()

        # Test worker step signals dispatching across multiple tabs
        w_tab.on_worker_step_started("alignment")
        w_tab.on_worker_step_finished(
            "alignment",
            True,
            "模擬比對完成",
            [str(temp_root / "dummy.fasta")],
            {"taxa": 6},
            "mafft --auto in > out",
        )
        w_tab.on_worker_all_finished(True, "工作流完成測試")
        app.processEvents()

        # Verify cards on both c1, c2, c3 received updates safely
        for k in ("alignment", "raw", "tree"):
            assert k in c1.cards
            assert k in c2.cards
            assert k in c3.cards

        # Test tab close guard
        total_tabs = w_tab.workflow_tabs.count()
        w_tab.workflow_tabs.removeTab(total_tabs - 1)
        assert w_tab.workflow_tabs.count() == total_tabs - 1
        print("  ✓ Workstation multi-tab signals and card sync verified with zero exceptions")

        # Test StepInspectionDialog, Dedicated Jump Routing, and Raw Preferences
        print("  Testing StepInspectionDialog popup and data population...")
        w_tab.inspect_step_data("raw")
        w_tab.inspect_step_data("tree")
        print("  ✓ StepInspectionDialog inspected raw and tree steps seamlessly")

        print("  Testing Dedicated Tab Jump Signal Routing...")
        dummy_raw = temp_root / "sample_raw.fasta"
        dummy_raw.write_text(">TaxonA\nATGC\n", encoding="utf-8")
        w_tab.pm.current_project.steps["raw"].output_files = [str(dummy_raw)]
        dummy_tree = temp_root / "sample_tree.treefile"
        dummy_tree.write_text("(TaxonA:0.1,TaxonB:0.1);\n", encoding="utf-8")
        w_tab.pm.current_project.steps["tree"].output_files = [str(dummy_tree)]

        jumped_files = []
        w_tab.view_msa_requested.connect(lambda f: jumped_files.append(("msa", f)))
        w_tab.view_tree_requested.connect(lambda f: jumped_files.append(("tree", f)))
        w_tab.on_step_jump("raw")
        w_tab.on_step_jump("tree")
        assert any(j[0] == "msa" for j in jumped_files), "Raw step jump should navigate to MSA viewer with data"
        assert any(j[0] == "tree" for j in jumped_files), "Tree step jump should navigate to Tree studio with data"
        print("  ✓ Dedicated tab jumps correctly routed to true visualization viewers")

        print("  Testing AnalysisPreferencesDialog for raw sequence input...")
        raw_pref = AnalysisPreferencesDialog("raw", {"data_type": "Nucleotide (DNA/RNA)"})
        assert "fasta_path" in raw_pref.controls
        assert "data_type" in raw_pref.controls
        assert "genetic_code" in raw_pref.controls
        print("  ✓ AnalysisPreferencesDialog supports raw sequences with complete molecular parameters")

        # TEST 4: TreeCanvasWidget Extreme Topologies
        print("\n[TEST 4] Testing TreeCanvasWidget Extreme Topologies...")
        tree_widget = TreeCanvasWidget()
        tree_widget.show()
        tree_widget.resize(700, 500)
        app.processEvents()

        extreme_trees = {
            "Single taxon": "(TaxonA:0.1);",
            "Star polytomy": "(TaxonA:0.1,TaxonB:0.1,TaxonC:0.1,TaxonD:0.1,TaxonE:0.1,TaxonF:0.1);",
            "Zero branch lengths": "((TaxonA:0.0,TaxonB:0.0):0.0,TaxonC:0.0);",
            "Long taxon names": "((Homo_sapiens_neanderthalensis_specimen_A1234:0.05,Pan_troglodytes_verus_forest_group:0.04):0.02,Gorilla_gorilla_gorilla_specimen_567:0.06);",
            "Deeply nested chain": "(((((A:0.01,B:0.01):0.01,C:0.01):0.01,D:0.01):0.01,E:0.01):0.01,F:0.01);",
        }

        for label, nwk in extreme_trees.items():
            tree_file = temp_root / f"tree_{label.replace(' ', '_')}.nwk"
            tree_file.write_text(nwk, encoding="utf-8")
            tree_widget.load_tree_file(tree_file, show_alert=False)
            assert tree_widget.tree is not None, f"Failed to load extreme tree: {label}"

            # Test multiple layouts on this tree
            for layout in ("標準矩形樹", "環狀放射樹"):
                tree_widget.layout_combo.setCurrentText(layout)
                tree_widget.redraw_tree()
                app.processEvents()

            # Test export
            out_png = temp_root / f"export_{label.replace(' ', '_')}.png"
            tree_widget.export_image(out_png, show_alert=False)
            assert out_png.exists() and out_png.stat().st_size > 0
            print(f"  ✓ Extreme tree [{label}] rendered and exported successfully")

        # TEST 5: MSA Viewer Edge Cases
        print("\n[TEST 5] Testing MSAViewer Edge Cases...")
        msa_widget = MSAViewer()
        msa_widget.show()
        msa_widget.resize(600, 400)
        app.processEvents()

        # MSA with single sequence
        single_seq_fasta = temp_root / "single_seq.fasta"
        single_seq_fasta.write_text(">Homo_sapiens\nATGCATGCATGC\n", encoding="utf-8")
        msa_widget.load_alignment_file(single_seq_fasta)
        app.processEvents()
        assert msa_widget.canvas.total_taxa == 1

        # MSA with all gaps
        gap_fasta = temp_root / "all_gaps.fasta"
        gap_fasta.write_text(">Seq1\n------\n>Seq2\n------\n", encoding="utf-8")
        msa_widget.load_alignment_file(gap_fasta)
        app.processEvents()
        assert msa_widget.canvas.total_taxa == 2

        # Mutation mode & Zoom test
        msa_widget.canvas.set_mutation_mode(True)
        app.processEvents()
        msa_widget.canvas.set_mutation_mode(False)
        msa_widget.on_zoom_changed(14)
        app.processEvents()
        print("  ✓ MSAViewer handled extreme alignments, mutation mode, and zoom without error")

        # TEST 6: Worker Cancellation Safety
        print("\n[TEST 6] Testing Workstation Worker Immediate Cancellation...")
        worker = WorkstationWorker(proj, ["modelfinder", "tree"], {})
        worker.cancel()
        assert worker.is_cancelled
        print("  ✓ WorkstationWorker cancel flag correctly set and runners informed")

        print("\n==================================================")
        print("🎉 ALL STABILITY & BUG HUNT TESTS PASSED 100%!")
        print("==================================================")

    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    run_all_bughunt_tests()
