"""
Interactive Test for GeneExtractorDialog GUI
"""

import sys
import io
from pathlib import Path
from PySide6.QtWidgets import QApplication

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ui.dialogs.gene_extractor_dialog import GeneExtractorDialog, PRESETS

def test_gene_extractor_dialog_ui():
    print("Testing GeneExtractorDialog GUI instantiation and presets...")
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = GeneExtractorDialog()

    # Verify presets
    for p_name in PRESETS.keys():
        dialog.preset_combo.setCurrentText(p_name)
        assert len(dialog.taxa_edit.toPlainText()) > 10
        print(f"  ✓ Preset '{p_name}' successfully loaded into editor!")

    # Verify target gene parsing
    dialog.gene_combo.setCurrentIndex(0) # CYTB
    combo_txt = dialog.gene_combo.currentText()
    target_gene = combo_txt.split()[0].split("/")[0].strip()
    assert target_gene == "CYTB"
    print("  ✓ Target gene parsing verified: CYTB")

    print("\n🎉 GeneExtractorDialog UI test passed 100%!")

if __name__ == "__main__":
    test_gene_extractor_dialog_ui()
