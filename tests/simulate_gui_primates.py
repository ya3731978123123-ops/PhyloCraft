import sys
import os
import time
from pathlib import Path

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer
from src.ui.main_window import MainWindow
from src.ui.tabs.ncbi_extractor_tab import NCBIGeneTab

# Mock all message boxes so test is non-blocking
QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.critical = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)

def run_gui_simulation():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow()
    window.resize(1340, 850)
    window.show()

    # Switch to NCBI Extractor Tab (Index 11)
    window.nav_list.setCurrentRow(11)
    app.processEvents()
    ncbi_tab = window.stack.widget(11)
    assert isinstance(ncbi_tab, NCBIGeneTab), "NCBI Gene Extractor tab not found!"

    print(f"Current Tab: {window.nav_list.item(11).text()}")

    # Step 1: Set Target Gene to P53 and input "靈長目"
    # Find P53 or set combo
    for i in range(ncbi_tab.gene_combo.count()):
        t = ncbi_tab.gene_combo.itemText(i)
        if "P53" in t:
            ncbi_tab.gene_combo.setCurrentIndex(i)
            break

    ncbi_tab.taxa_edit.setPlainText("靈長目")
    app.processEvents()
    time.sleep(0.5)

    print("Step 1: Clicking '解析物種俗名 ➔ 官方登錄號'...")
    ncbi_tab.resolve_vernacular_names()
    app.processEvents()

    resolved_text = ncbi_tab.taxa_edit.toPlainText().strip()
    print("Resolved lines:")
    print(resolved_text)
    resolved_lines = [l for l in resolved_text.splitlines() if l.strip()]
    assert len(resolved_lines) >= 8, f"Expected at least 8 species, got {len(resolved_lines)}"

    # Step 2: Start extraction for all 8 primate species
    print("\nStep 2: Starting online extraction and coordinate slicing...")
    out_dir = PROJECT_ROOT / "screens"
    out_dir.mkdir(exist_ok=True)
    out_fasta = out_dir / "primates_p53_8_species.fasta"
    ncbi_tab.out_path_edit.setText(str(out_fasta))

    ncbi_tab.start_extraction()

    # Wait for background extraction worker to finish
    max_wait = 45  # seconds
    start_time = time.time()
    while ncbi_tab.worker and ncbi_tab.worker.isRunning() and (time.time() - start_time < max_wait):
        app.processEvents()
        time.sleep(0.2)

    app.processEvents()
    time.sleep(1.0)

    # Check table rows
    row_count = ncbi_tab.table.rowCount()
    print(f"Extracted rows in GUI table: {row_count}")
    assert row_count >= 8, f"Expected at least 8 rows in table, got {row_count}"

    for row in range(row_count):
        org = ncbi_tab.table.item(row, 0).text() if ncbi_tab.table.item(row, 0) else ""
        acc = ncbi_tab.table.item(row, 1).text() if ncbi_tab.table.item(row, 1) else ""
        coord = ncbi_tab.table.item(row, 2).text() if ncbi_tab.table.item(row, 2) else ""
        seq_len = ncbi_tab.table.item(row, 3).text() if ncbi_tab.table.item(row, 3) else ""
        sha = ncbi_tab.table.item(row, 5).text() if ncbi_tab.table.item(row, 5) else ""
        print(f"  Row {row+1}: {org} | {acc} | {coord} | len={seq_len} | SHA={sha[:12]}")

    # Capture pristine GUI Screenshot
    screen_path = out_dir / "43_ncbi_primates_p53_clade_expansion.png"
    pixmap = window.grab()
    pixmap.save(str(screen_path), "PNG")
    print(f"\n🎉 Screenshot successfully captured at: {screen_path}")

    # Also copy to artifacts dir if possible
    brain_dir = Path(r"C:\Users\Alan\.gemini\antigravity\brain\b252e923-3bcb-4e1f-b6b5-41ade74e0f9b\screens")
    brain_dir.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(brain_dir / "43_ncbi_primates_p53_clade_expansion.png"), "PNG")
    print(f"Artifact screenshot copied to: {brain_dir / '43_ncbi_primates_p53_clade_expansion.png'}")

    window.close()
    print("Simulation finished successfully!")

if __name__ == "__main__":
    run_gui_simulation()
