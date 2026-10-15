"""
Comprehensive Unit & GUI Integration Test for NCBIGeneTab
Validates:
1. NCBIGeneTab standalone UI initialization and control availability.
2. Preset loading: Ethylene Receptor ETR1, Ursidae Cytb, Cetartiodactyla Cytb, Primates Cytb, Spike.
3. Provenance verification table rendering (Accession, Coordinates, Protein ID, SHA-256, URL).
4. Provenance audit exports (CSV and Markdown) verification.
5. Cross-tab signal dispatch to SanitizerTab and AlignmentTab in MainWindow.
"""

import sys
import io
import os
import shutil
os.environ["HEADLESS_TEST"] = "1"
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ui.main_window import MainWindow
from src.ui.tabs.ncbi_extractor_tab import NCBIGeneTab, NCBI_PRESETS
from src.core.gene_extractor import ExtractedGeneRecord, GeneExtractionResult, GeneExtractor

def test_ncbi_gene_tab():
    print("=" * 65)
    print("🌐 STARTING NCBI GENE TAB & PROVENANCE AUDIT VERIFICATION")
    print("=" * 65)

    app = QApplication.instance() or QApplication(sys.argv)

    print("\n[Step 1/5] Testing NCBIGeneTab UI Instantiation...")
    tab = NCBIGeneTab()
    tab.show()
    app.processEvents()
    assert tab.preset_combo.count() >= 5
    assert tab.gene_combo.count() >= 8
    assert tab.table.columnCount() == 7
    print("  ✓ NCBIGeneTab successfully initialized with 7 provenance columns!")

    print("\n[Step 2/5] Testing Ethylene Receptor ETR1 & All Presets Loading...")
    # Test Ethylene receptor preset
    etr_preset = "被子植物乙烯受體 ETR1 (Ethylene Receptors)"
    assert etr_preset in NCBI_PRESETS
    tab.preset_combo.setCurrentText(etr_preset)
    app.processEvents()
    taxa_text = tab.taxa_edit.toPlainText()
    assert "NM_105305.4" in taxa_text # Arabidopsis
    assert "NM_001247220.2" in taxa_text # Tomato
    assert "NM_001402333.1" in taxa_text # Rice
    assert "NM_001325388.1" in taxa_text # Tobacco
    assert "XM_002311633.4" in taxa_text # Poplar
    assert "XM_003556299.5" in taxa_text # Soybean
    print("  ✓ Ethylene receptor ETR1 preset loaded with Arabidopsis, Tomato, Rice, Tobacco, Poplar, Soybean!")

    # Verify all presets load correctly
    for p_name in NCBI_PRESETS.keys():
        tab.preset_combo.setCurrentText(p_name)
        app.processEvents()
        assert len(tab.taxa_edit.toPlainText()) > 20
        print(f"  ✓ Preset '{p_name[:25]}...' verified")

    print("\n[Step 3/5] Testing Provenance Table Rendering with Cryptographic Records...")
    # Construct mock verified records (ETR1 and Cytb)
    rec_etr1 = ExtractedGeneRecord(
        accession="NM_105305.4",
        organism="Arabidopsis thaliana",
        gene_symbol="ETR1",
        product="ethylene receptor 1",
        sequence="ATG" + "GAA" * 100 + "TAA",
        seq_length=306,
        start=312,
        end=2528,
        strand=1,
        header="Arabidopsis_thaliana|NM_105305.4:312-2528(+)|ETR1",
        taxid="3702",
        protein_id="NP_174404.1",
        ncbi_url="https://www.ncbi.nlm.nih.gov/nuccore/NM_105305.4",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
        coordinates_str="312..2528 (+)",
        retrieved_at="2026-10-15T19:00:00"
    )

    rec_bear = ExtractedGeneRecord(
        accession="NC_003428.1",
        organism="Ursus maritimus",
        gene_symbol="CYTB",
        product="cytochrome b",
        sequence="ATG" + "AAA" * 100 + "TAA",
        seq_length=1140,
        start=14138,
        end=15277,
        strand=1,
        header="Ursus_maritimus|NC_003428.1:14138-15277(+)|CYTB",
        taxid="29073",
        protein_id="NP_659020.1",
        ncbi_url="https://www.ncbi.nlm.nih.gov/nuccore/NC_003428.1",
        sha256_hash="5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
        md5_hash="900150983cd24fb0d6963f7d28e17f72",
        coordinates_str="14138..15277 (+)",
        retrieved_at="2026-10-15T19:00:00"
    )

    mock_res = GeneExtractionResult(
        success=True,
        total_requested=2,
        total_extracted=2,
        records=[rec_etr1, rec_bear],
        output_fasta="output/test_provenance.fasta",
        output_csv="output/test_provenance.csv",
        output_md="output/test_provenance.md",
        message="OK"
    )

    tab.current_result = mock_res
    tab.populate_provenance_table(mock_res.records)
    app.processEvents()

    assert tab.table.rowCount() == 2
    # Check row 0
    assert tab.table.item(0, 0).text() == "Arabidopsis thaliana"
    assert tab.table.item(0, 1).text() == "NM_105305.4"
    assert "312..2528" in tab.table.item(0, 2).text()
    assert tab.table.item(0, 3).text() == "306 bp"
    assert tab.table.item(0, 4).text() == "NP_174404.1"
    assert tab.table.item(0, 5).text() == "e3b0c44298..."
    assert tab.table.cellWidget(0, 6) is not None
    # Check row 1
    assert tab.table.item(1, 0).text() == "Ursus maritimus"
    assert tab.table.item(1, 1).text() == "NC_003428.1"
    assert "14138..15277" in tab.table.item(1, 2).text()
    assert tab.table.item(1, 3).text() == "1140 bp"
    print("  ✓ Provenance verification table correctly rendered with coordinates, protein IDs, and SHA-256 hashes!")

    print("\n[Step 4/5] Testing Provenance Audit Report Exporters (CSV & Markdown)...")
    out_dir = Path("output/provenance_audit_test")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_file = out_dir / "provenance_audit.csv"
    md_file = out_dir / "provenance_audit.md"

    GeneExtractor.export_provenance_csv([rec_etr1, rec_bear], csv_file)
    GeneExtractor.export_provenance_markdown([rec_etr1, rec_bear], md_file, target_gene="ETR1")

    assert csv_file.exists()
    assert md_file.exists()

    with open(csv_file, "r", encoding="utf-8") as f:
        csv_content = f.read()
        assert "NM_105305.4" in csv_content
        assert "NC_003428.1" in csv_content
        assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in csv_content
        assert "https://www.ncbi.nlm.nih.gov/nuccore/NM_105305.4" in csv_content
    print("  ✓ Provenance CSV verified: contains full SHA-256, coordinates, protein IDs, and NCBI URLs!")

    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()
        assert "Gene Provenance & Traceability Audit" in md_content
        assert "Arabidopsis thaliana" in md_content
        assert "NP_174404.1" in md_content
        assert "https://www.ncbi.nlm.nih.gov/nuccore/NM_105305.4" in md_content
    print("  ✓ Provenance Markdown verified: contains publication-grade audit table and citations!")

    print("\n[Step 5/5] Testing MainWindow Cross-Tab Pipeline Signal Routing...")
    main_win = MainWindow()
    main_win.show()
    app.processEvents()

    # Test send to sanitizer signal
    fake_fasta = str(out_dir / "extracted_genes.fasta")
    with open(fake_fasta, "w", encoding="utf-8") as f:
        f.write(">Arabidopsis_thaliana\nATGCATGC\n")

    main_win.ncbi_gene_tab.send_to_sanitizer_requested.emit(fake_fasta)
    app.processEvents()
    assert main_win.stack.currentIndex() == 2
    assert main_win.sanitizer_tab.file_edit.text() == fake_fasta
    print("  ✓ Signal 'send_to_sanitizer_requested' successfully switched to SanitizerTab (index 2)!")

    # Test send to alignment signal
    main_win.ncbi_gene_tab.send_to_align_requested.emit(fake_fasta)
    app.processEvents()
    assert main_win.stack.currentIndex() == 3
    assert main_win.alignment_tab.in_edit.text() == fake_fasta
    print("  ✓ Signal 'send_to_align_requested' successfully switched to AlignmentTab (index 3)!")

    # Test top ribbon button for NCBI tab
    main_win.ribbon_buttons[11].click()
    app.processEvents()
    assert main_win.stack.currentIndex() == 11
    assert main_win.stack.currentWidget() == main_win.ncbi_gene_tab
    print("  ✓ Top Ribbon button [🌐 NCBI 溯源] successfully activated NCBIGeneTab (index 11)!")

    main_win.close()
    tab.close()
    app.processEvents()

    # Clean up output artifacts to ensure pristine environment
    shutil.rmtree(out_dir, ignore_errors=True)

    print("\n" + "=" * 65)
    print("🎉 ALL NCBI GENE TAB & PROVENANCE AUDIT TESTS PASSED 100%!")
    print("=" * 65)

if __name__ == "__main__":
    test_ncbi_gene_tab()
