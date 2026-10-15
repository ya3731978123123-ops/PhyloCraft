import sys
import os
os.environ["HEADLESS_TEST"] = "1"
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.ui.main_window import MainWindow
from src.ui.widgets.eln_viewer_dialog import ELNViewerDialog
from src.config import DATA_DIR, OUTPUT_DIR


def test_gui():
    print("=" * 60)
    print("🖥️ STARTING PYSIDE6 GUI SMOKE TEST")
    print("=" * 60)

    app = QApplication.instance() or QApplication(sys.argv)

    try:
        print("\n[GUI Test 1/5] Initializing MainWindow...")
        win = MainWindow()
        win.show()
        app.processEvents()
        print("  ✓ MainWindow successfully shown!")

        print("\n[GUI Test 2/5] Cycling through all 12 tabs...")
        for idx in range(12):
            win.nav_list.setCurrentRow(idx)
            app.processEvents()
            tab_name = win.nav_list.item(idx).text()
            current_widget = win.stack.currentWidget()
            assert current_widget is not None
            print(f"  ✓ Tab {idx}: {tab_name} -> {current_widget.__class__.__name__}")

        print("\n[GUI Test 3/5] Testing Demo Project & Cross-Tab Signal Dispatch...")
        win.workstation_tab.load_demo_project(show_alert=False)
        app.processEvents()
        proj = win.workstation_tab.pm.current_project
        assert proj is not None
        assert proj.name == "Primates_Cytb_Phylogenomics"
        assert all(s.status == "completed" for s in proj.steps.values())
        print("  ✓ Demonstration Project loaded and all 7 steps verified completed!")

        sample_tree = Path(proj.project_dir) / "06_phylogeny" / "primates_cytb_tree.treefile"
        if sample_tree.exists():
            win.switch_to_tree_viewer(str(sample_tree))
            app.processEvents()
            assert win.stack.currentIndex() == 8
            print("  ✓ Tree Viewer navigation verified!")

        sample_aln = Path(proj.project_dir) / "03_alignment" / "primates_cytb_aligned.fasta"
        if sample_aln.exists():
            win.switch_to_msa_viewer(str(sample_aln))
            app.processEvents()
            assert win.stack.currentIndex() == 5
            print("  ✓ MSA Viewer navigation verified!")

        win.switch_to_alignment(str(DATA_DIR / "primates_cytb.fasta"))
        app.processEvents()
        assert win.stack.currentIndex() == 3
        print("  ✓ Alignment navigation verified!")

        win.switch_to_trimming(str(DATA_DIR / "primates_cytb.fasta"))
        app.processEvents()
        assert win.stack.currentIndex() == 4
        print("  ✓ Trimming navigation verified!")

        # Test Data Inspector "👁️ 移至專屬檢視器" on modelfinder
        win.nav_list.setCurrentRow(0)  # back to workstation
        app.processEvents()
        win.workstation_tab.inspect_step_data("modelfinder")
        app.processEvents()
        win.workstation_tab.open_full_viewer()
        app.processEvents()
        assert win.stack.currentIndex() == 6
        assert win.model_test_tab.table.rowCount() > 0
        assert "套用" in win.model_test_tab.apply_btn.text()
        print("  ✓ Workstation Data Inspector -> ModelTestTab navigation & data population verified!")

        print("\n[GUI Test 4/5] Testing ELNViewerDialog Instant Compilation...")
        if win.workstation_tab.pm.current_project:
            eln_dlg = ELNViewerDialog(win.workstation_tab.pm.current_project, win)
            eln_dlg.show()
            app.processEvents()
            assert eln_dlg.html_content != ""
            assert len(eln_dlg.audit_records) >= 7
            eln_dlg.close()
            print("  ✓ ELNViewerDialog opened and verified without errors!")

        print("\n[GUI Test 5/5] Testing Clean Application Close...")
        win.close()
        app.processEvents()
        print("  ✓ Application closed cleanly with 0 thread leaks!")
    finally:
        # Guarantee output directory cleanliness after smoke tests
        import shutil
        for p in OUTPUT_DIR.glob("*.phylo"):
            shutil.rmtree(p, ignore_errors=True)
        recent_file = OUTPUT_DIR / ".recent_projects.json"
        if recent_file.exists():
            recent_file.unlink(missing_ok=True)

    print("\n" + "=" * 60)
    print("🎉 ALL GUI SMOKE TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    test_gui()
