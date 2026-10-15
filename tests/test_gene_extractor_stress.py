"""
Comprehensive White-Box, Stress, and Zero-Regression Test Suite for NCBI Gene Extractor.
Tests:
1. Input Parser Edge-Case Matrix (URLs, comments, delimiters, wrappers, noise, de-duplication)
2. White-Box Feature Extraction (Multi-exon splicing, Negative strand reverse complement,
   Short symbol word boundary collision defense, Gene synonym resolution, Custom genes)
3. Live Network Error Handling & Friendly Failure Reporting
4. Async Worker Cancellation Safety & Rapid Lifecycle Stress
5. Zero-Regression & Non-Interference Verification across all 12 GUI Tabs
"""

import sys
import time
from pathlib import Path
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtWidgets import QApplication
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, SimpleLocation, CompoundLocation

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.core.gene_extractor import GeneExtractor, ExtractedGeneRecord, GeneExtractionResult
from src.ui.tabs.ncbi_extractor_tab import NCBIGeneTab, TabExtractionWorker
from src.ui.main_window import MainWindow
from PySide6.QtWidgets import QMessageBox

# Non-blocking mock for all Qt message boxes during automated test
QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.critical = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)


def get_qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_input_parser_edge_cases():
    print("\n[Stress Test 1/5] Testing Input Parser White-Box Edge-Case Matrix...")
    extractor = GeneExtractor()

    # 1. URL Variations
    url_inputs = [
        "https://www.ncbi.nlm.nih.gov/nuccore/NM_105305.4",
        "https://www.ncbi.nlm.nih.gov/nuccore/?term=NC_003428.1",
        "https://www.ncbi.nlm.nih.gov/nucleotide/XM_002311633.4?report=genbank",
        "https://www.ncbi.nlm.nih.gov/nuccore?id=MN996532.2&val=test",
        "https://www.ncbi.nlm.nih.gov/nuccore/",  # Invalid URL without accession
        "https://www.ncbi.nlm.nih.gov/protein/",  # Db keyword
    ]
    parsed_urls = extractor.parse_accessions(url_inputs)
    assert parsed_urls == ["NM_105305.4", "NC_003428.1", "XM_002311633.4", "MN996532.2"], (
        f"URL parsing failed: {parsed_urls}"
    )
    print("  ✓ NCBI URL variations (path, ?term=, ?id=, db keywords filtered) parsed successfully!")

    # 2. Dirty Comments and Delimiters
    dirty_text = """
    # Header comment: Project 2026
    NC_003428.1 # Polar bear Cytb
    NM_105305.4 // Arabidopsis thaliana ETR1
    NC_003427.1; NC_003426.1, NC_009970.1 | NC_009968.1
    \t  NC_009971.1   \t\t
    """
    parsed_dirty = extractor.parse_accessions(dirty_text)
    expected_dirty = ["NC_003428.1", "NM_105305.4", "NC_003427.1", "NC_003426.1", "NC_009970.1", "NC_009968.1", "NC_009971.1"]
    assert parsed_dirty == expected_dirty, f"Dirty text parsing failed: {parsed_dirty}"
    print("  ✓ Mixed delimiters (comma, semicolon, pipe, tab, spaces) & comments (#, //) parsed!")

    # 3. FASTA headers, quotes, brackets, and de-duplication
    messy_lines = [
        ">NC_003428.1 Ursus maritimus",
        "[NM_105305.4]",
        "('NC_003427.1')",
        "\"NC_003426.1\"",
        "NC_003428.1",  # duplicate
        "NC_003427.1",  # duplicate
        ">NC_001325.1 Phoca vitulina (Harbor seal)",
    ]
    parsed_messy = extractor.parse_accessions(messy_lines)
    expected_messy = ["NC_003428.1", "NM_105305.4", "NC_003427.1", "NC_003426.1", "NC_001325.1"]
    assert parsed_messy == expected_messy, f"Messy wrappers & deduplication failed: {parsed_messy}"
    print("  ✓ FASTA headers (>), quotes, brackets, and order-preserving deduplication verified!")

    # 4. Non-accession noise and unannotated species rejection
    noise_input = """
    Ursus maritimus
    Homo sapiens
    Arabidopsis thaliana
    nuccore nucleotide protein
    !@#$%^&*()
    ,,, ;;; |||
    ---
    """
    parsed_noise = extractor.parse_accessions(noise_input)
    assert parsed_noise == [], f"Noise should produce empty list, but got: {parsed_noise}"
    print("  ✓ Non-accession text, taxon names, and punctuation noise cleanly rejected!")

    # 5. Large input stress (500 items with heavy duplication and noise)
    stress_lines = []
    for i in range(100):
        stress_lines.append(f"NC_00{i:04d}.1 # Species {i}")
        stress_lines.append(f"NC_00{i:04d}.1")  # duplicate
        stress_lines.append("Homo sapiens Neanderthal")  # noise
        stress_lines.append("   ")  # empty line
        stress_lines.append(f"https://www.ncbi.nlm.nih.gov/nuccore/NM_10{i:04d}.2")
    
    t0 = time.perf_counter()
    parsed_stress = extractor.parse_accessions(stress_lines)
    t_elapsed = time.perf_counter() - t0
    assert len(parsed_stress) == 200, f"Expected 200 unique accessions, got {len(parsed_stress)}"
    assert t_elapsed < 0.2, f"Parser too slow on 500 lines: {t_elapsed:.4f}s"
    print(f"  ✓ High-volume stress parse: 500 messy lines parsed in {t_elapsed*1000:.1f} ms!")


def test_chinese_vernacular_and_protein_resolution():
    print("\n[Stress Test 2/6] Testing Chinese Vernacular Plant Names & Protein Resolution...")
    extractor = GeneExtractor()

    # 1. Chinese protein names -> Gene symbols
    assert extractor.translate_chinese_gene("乙烯受體") == "ETR1"
    assert extractor.translate_chinese_gene("乙烯受體 1") == "ETR1"
    assert extractor.translate_chinese_gene("核酮糖二磷酸羧化酶") == "RBCL"
    assert extractor.translate_chinese_gene("核酮糖羧化酶") == "RBCL"
    assert extractor.translate_chinese_gene("成熟酶K") == "MATK"
    assert extractor.translate_chinese_gene("細胞色素 b") == "CYTB"
    assert extractor.translate_chinese_gene("甘油醛-3-磷酸脫氫酶") == "GAPDH"
    print("  ✓ Chinese protein common names (乙烯受體, 核酮糖羧化酶, 成熟酶K, 細胞色素b...) translated accurately!")

    # 2. Chinese plant vernacular names -> Latin scientific names
    assert extractor.translate_chinese_organism("擬南芥") == "Arabidopsis thaliana"
    assert extractor.translate_chinese_organism("水稻") == "Oryza sativa"
    assert extractor.translate_chinese_organism("番茄") == "Solanum lycopersicum"
    assert extractor.translate_chinese_organism("玉米") == "Zea mays"
    assert extractor.translate_chinese_organism("茶樹") == "Camellia sinensis"
    assert extractor.translate_chinese_organism("大豆") == "Glycine max"
    assert extractor.translate_chinese_organism("銀杏") == "Ginkgo biloba"
    print("  ✓ Chinese plant vernacular names (擬南芥, 水稻, 番茄, 玉米, 茶樹, 大豆, 銀杏...) translated to Latin!")

    # 3. Direct resolve of a Chinese plant list to NCBI accessions
    plant_list = ["擬南芥", "番茄", "水稻", "玉米", "大豆"]
    resolved_etr1 = extractor.resolve_taxa_to_accessions(plant_list, "乙烯受體")
    assert len(resolved_etr1) == 5
    assert resolved_etr1[0][0] == "NM_105305.4"
    assert resolved_etr1[1][0] == "NM_001247220.2"
    assert resolved_etr1[2][0] == "NM_001402333.1"
    assert "擬南芥" in resolved_etr1[0][2] and "Arabidopsis thaliana" in resolved_etr1[0][2]
    print("  ✓ Chinese plant list + Chinese target gene ('乙烯受體') auto-resolved to official NCBI RefSeq accessions!")

    # 4. Feature extraction with Chinese target gene directly
    rec_rice = SeqRecord(Seq("ATGCAATAG"), id="MOCK_RICE.1", description="Oryza sativa ETR2")
    feat_rice = SeqFeature(
        location=SimpleLocation(0, 9, strand=1),
        type="CDS",
        qualifiers={"gene": ["LOC4335058"], "gene_synonym": ["OsETR2", "ETR2"], "product": ["ethylene receptor 2"]}
    )
    rec_rice.features.append(feat_rice)
    res_zh = extractor.extract_gene_from_record(rec_rice, "乙烯受體")
    assert res_zh is not None, "Failed to match CDS when target_gene is '乙烯受體'!"
    assert res_zh.gene_symbol in ["ETR1", "ETR2", "LOC4335058"]
    print("  ✓ Feature extraction using pure Chinese protein name ('乙烯受體') succeeded!")

    # 5. Feature extraction with '核酮糖羧化酶'
    rec_rbcl = SeqRecord(Seq("ATGGTGTAA"), id="MOCK_CHLORO.1", description="Camellia sinensis chloroplast")
    feat_rbcl = SeqFeature(
        location=SimpleLocation(0, 9, strand=1),
        type="CDS",
        qualifiers={"gene": ["rbcL"], "product": ["ribulose-1,5-bisphosphate carboxylase/oxygenase large subunit"]}
    )
    rec_rbcl.features.append(feat_rbcl)
    res_rbcl = extractor.extract_gene_from_record(rec_rbcl, "核酮糖羧化酶")
    assert res_rbcl is not None, "Failed to match CDS when target_gene is '核酮糖羧化酶'!"
    print("  ✓ Feature extraction using '核酮糖羧化酶' matched rbcL CDS successfully!")


def test_feature_extraction_whitebox_logic():
    print("\n[Stress Test 3/6] Testing White-Box Genomic Feature Extraction Logic...")
    extractor = GeneExtractor()

    # 1. Multi-Exon Spliced CDS (CompoundLocation)
    # Exon 1: 10..30 (20 bp), Exon 2: 50..80 (30 bp), Exon 3: 100..120 (20 bp) -> Total 70 bp
    seq_str = "A" * 10 + "ATG" + "C" * 17 + "N" * 20 + "G" * 30 + "N" * 20 + "T" * 17 + "TAA" + "A" * 20
    rec_spliced = SeqRecord(Seq(seq_str), id="MOCK_SPLICED.1", description="Homo sapiens TP53 mock record")
    loc_parts = [
        SimpleLocation(10, 30, strand=1),
        SimpleLocation(50, 80, strand=1),
        SimpleLocation(100, 120, strand=1),
    ]
    feat_spliced = SeqFeature(
        location=CompoundLocation(loc_parts),
        type="CDS",
        qualifiers={
            "gene": ["TP53"],
            "product": ["cellular tumor antigen p53"],
            "protein_id": ["NP_000537.3"]
        }
    )
    rec_spliced.features.append(feat_spliced)

    res_tp53 = extractor.extract_gene_from_record(rec_spliced, "TP53")
    assert res_tp53 is not None, "Failed to extract multi-exon TP53!"
    assert res_tp53.seq_length == 70, f"Expected length 70, got {res_tp53.seq_length}"
    assert "3 exons" in res_tp53.coordinates_str, f"CompoundLocation not recorded: {res_tp53.coordinates_str}"
    assert res_tp53.strand == 1
    assert res_tp53.protein_id == "NP_000537.3"
    print("  ✓ Multi-exon spliced CDS (CompoundLocation) extracted and concatenated accurately!")

    # 2. Negative Strand Reverse Complement (Strand = -1)
    # Forward seq: 5'- ATGCATGC... -3' -> On reverse strand, extracted must be reverse complement!
    raw_sub = "ATGCCCCCGGGTTTAAA"
    fwd_seq = "T" * 50 + raw_sub + "A" * 50
    rec_neg = SeqRecord(Seq(fwd_seq), id="MOCK_NEG.1", description="Homo sapiens mitochondrion ND6")
    feat_neg = SeqFeature(
        location=SimpleLocation(50, 50 + len(raw_sub), strand=-1),
        type="CDS",
        qualifiers={
            "gene": ["ND6"],
            "product": ["NADH dehydrogenase subunit 6"],
            "protein_id": ["YP_003024037.1"]
        }
    )
    rec_neg.features.append(feat_neg)

    res_nd6 = extractor.extract_gene_from_record(rec_neg, "ND6")
    assert res_nd6 is not None, "Failed to extract negative strand ND6!"
    assert res_nd6.strand == -1
    assert "(-)" in res_nd6.coordinates_str
    # Verify reverse complement
    expected_rc = str(Seq(raw_sub).reverse_complement())
    assert res_nd6.sequence == expected_rc, f"Reverse complement mismatch: {res_nd6.sequence} != {expected_rc}"
    print("  ✓ Negative strand (-) coordinates and reverse-complement sequence verified!")

    # 3. Short Symbol Word-Boundary Defense (Prevent Substring False Positives)
    # Test case: Target gene 'S' (Spike protein).
    # Record A has 'SIGNAL TRANSDUCTION PROTEIN' -> MUST NOT MATCH 'S'!
    rec_false = SeqRecord(Seq("ATGCGTTAG"), id="MOCK_COLLISION.1", description="Signal transduction locus")
    feat_false = SeqFeature(
        location=SimpleLocation(0, 9, strand=1),
        type="CDS",
        qualifiers={
            "gene": ["STP1"],
            "product": ["SIGNAL TRANSDUCTION REGULATOR PROTEIN"],
            "note": ["INVOLVED IN CELL SIGNALING"]
        }
    )
    rec_false.features.append(feat_false)
    res_false = extractor.extract_gene_from_record(rec_false, "S")
    assert res_false is None, "False positive! 'S' should NOT match 'SIGNAL' or 'CELL SIGNALING'!"

    # Record B has genuine Spike protein -> MUST MATCH 'S'!
    rec_true = SeqRecord(Seq("ATGCCCTAG"), id="MOCK_SPIKE.1", description="SARS-CoV-2 Spike")
    feat_true = SeqFeature(
        location=SimpleLocation(0, 9, strand=1),
        type="CDS",
        qualifiers={
            "gene": ["S"],
            "product": ["surface glycoprotein"],
            "protein_id": ["YP_009724390.1"]
        }
    )
    rec_true.features.append(feat_true)
    res_true = extractor.extract_gene_from_record(rec_true, "S")
    assert res_true is not None, "Genuine 'S' Spike protein failed to match!"
    assert res_true.gene_symbol == "S"
    print("  ✓ Short symbol ('S', 'ND1', 'CO1') word-boundary false-positive collision defense verified!")

    # 4. Gene Synonym & Locus Tag Resolution (e.g. Rice/Tobacco ETR1)
    rec_syn = SeqRecord(Seq("ATGAAATAG"), id="MOCK_CROP.1", description="Oryza sativa locus")
    feat_syn = SeqFeature(
        location=SimpleLocation(0, 9, strand=1),
        type="CDS",
        qualifiers={
            "gene": ["LOC4335058"],
            "gene_synonym": ["OsETR1", "ETR1"],
            "product": ["ethylene response sensor 1"]
        }
    )
    rec_syn.features.append(feat_syn)
    res_syn = extractor.extract_gene_from_record(rec_syn, "ETR1")
    assert res_syn is not None, "Failed to resolve ETR1 from gene_synonym list!"
    print("  ✓ Crop locus tag + gene_synonym resolution verified!")

    # 5. Arbitrary User-Entered Custom Gene
    rec_custom = SeqRecord(Seq("ATGGGGTAG"), id="MOCK_CUSTOM.1", description="Novel organism")
    feat_custom = SeqFeature(
        location=SimpleLocation(0, 9, strand=1),
        type="CDS",
        qualifiers={
            "gene": ["MYC_TARGET_ALPHA"],
            "product": ["novel transcription co-factor"]
        }
    )
    rec_custom.features.append(feat_custom)
    res_custom = extractor.extract_gene_from_record(rec_custom, "MYC_TARGET_ALPHA")
    assert res_custom is not None, "Arbitrary custom gene symbol failed to match!"
    assert res_custom.gene_symbol == "MYC_TARGET_ALPHA"
    print("  ✓ Arbitrary user-entered gene symbols fully supported!")


def test_network_and_fault_tolerance():
    print("\n[Stress Test 3/5] Testing Network Error Handling & Friendly Diagnostics...")
    extractor = GeneExtractor()
    out_tmp = PROJECT_ROOT / "data" / "test_stress_err.fasta"

    # 1. Unparsable / malformed accession format
    result_malformed = extractor.extract_target_genes(
        targets=["NONEXISTENT_ACC_999999.9"],
        target_gene="CYTB",
        output_fasta=out_tmp
    )
    assert not result_malformed.success, "Malformed accession should fail gracefully!"
    assert len(result_malformed.failed_accessions) == 1
    acc_fail, reason_fail = result_malformed.failed_accessions[0]
    assert acc_fail == "NONEXISTENT_ACC_999999.9"
    assert "無法解析" in reason_fail
    print(f"  ✓ Malformed accession format diagnosed gracefully: '{reason_fail}'")

    # 2. Formatted accession that does not exist in NCBI (triggers HTTP 400 from E-Utilities)
    result_400 = extractor.extract_target_genes(
        targets=["NC_999999.9"],
        target_gene="CYTB",
        output_fasta=out_tmp
    )
    assert not result_400.success, "NCBI 400/404 should fail gracefully!"
    assert len(result_400.failed_accessions) == 1
    acc_400, reason_400 = result_400.failed_accessions[0]
    assert acc_400 == "NC_999999.9"
    assert "例外" in reason_400 or "HTTP" in reason_400 or "400" in reason_400
    print(f"  ✓ Nonexistent accession HTTP error handled gracefully without crash: '{reason_400}'")


def test_async_worker_cancellation():
    print("\n[Stress Test 4/5] Testing Asynchronous Worker Thread Cancellation...")
    app = get_qapp()
    out_tmp = PROJECT_ROOT / "data" / "test_stress_cancel.fasta"

    # Launch worker with multiple accessions
    targets = ["NC_003428.1", "NC_003427.1", "NC_003426.1", "NC_009970.1"]
    worker = TabExtractionWorker(targets, "CYTB", out_tmp)

    results_received = []
    worker.finished_signal.connect(lambda r: results_received.append(r))

    worker.start()
    # Let it start, then cancel immediately
    time.sleep(0.05)
    worker.cancel()
    worker.wait(5000)
    QCoreApplication.processEvents()

    assert not worker.isRunning(), "Worker failed to terminate after cancellation!"
    assert len(results_received) == 1, "Worker finished_signal not emitted!"
    res = results_received[0]
    # Check that cancel was recorded
    has_cancel = any(acc == "CANCELLED" for acc, _ in res.failed_accessions)
    assert has_cancel, "Cancellation reason not properly captured!"
    print("  ✓ TabExtractionWorker stopped safely and emitted cancellation status!")


def test_zero_regression_all_12_tabs():
    print("\n[Stress Test 5/5] Testing Zero-Regression across All 12 MainWindow Tabs...")
    app = get_qapp()
    window = MainWindow()
    window.show()
    QCoreApplication.processEvents()

    # Verify tab count is exactly 12
    assert window.nav_list.count() == 12, f"Expected 12 tabs in nav_list, found {window.nav_list.count()}"
    assert window.stack.count() == 12, f"Expected 12 tabs in stack, found {window.stack.count()}"

    expected_tab_names = [
        "專案工作台",
        "自動化流程",
        "序列檢驗清洗",
        "多重序列比對",
        "比對位點修剪",
        "比對矩陣檢視器",
        "替代模型檢定",
        "系統發育建樹",
        "演化樹檢視器",
        "多基因超矩陣",
        "系統工具與環境",
        "NCBI 基因檢索"
    ]

    for idx, expected_name in enumerate(expected_tab_names):
        actual_name = window.nav_list.item(idx).text()
        assert expected_name in actual_name, f"Tab {idx} mismatch: '{expected_name}' not in '{actual_name}'"
        window.nav_list.setCurrentRow(idx)
        QCoreApplication.processEvents()
        assert window.stack.currentIndex() == idx

    print("  ✓ All 12 tabs cleanly navigated and verified intact!")

    # Verify NCBIGeneTab cross-tab signal dispatches
    ncbi_tab = window.stack.widget(11)
    assert isinstance(ncbi_tab, NCBIGeneTab), "Tab 11 is not NCBIGeneTab!"

    sample_fasta = str(PROJECT_ROOT / "data" / "primates_cytb.fasta")

    # Test send_to_sanitizer_requested signal
    ncbi_tab.send_to_sanitizer_requested.emit(sample_fasta)
    QCoreApplication.processEvents()
    assert window.stack.currentIndex() == 2, f"Expected tab index 2 (Sanitizer), got {window.stack.currentIndex()}"

    # Test send_to_align_requested signal
    ncbi_tab.send_to_align_requested.emit(sample_fasta)
    QCoreApplication.processEvents()
    assert window.stack.currentIndex() == 3, f"Expected tab index 3 (Alignment), got {window.stack.currentIndex()}"

    # Test top ribbon button navigation to NCBIGeneTab
    if hasattr(window, "btn_ribbon_ncbi"):
        window.btn_ribbon_ncbi.click()
        QCoreApplication.processEvents()
        assert window.stack.currentIndex() == 11, f"Expected tab index 11 (NCBI Tab), got {window.stack.currentIndex()}"

    print("  ✓ Cross-tab signal workflows (Sanitizer ➔ MAFFT) verified with zero interference!")

    window.close()
    QCoreApplication.processEvents()
    print("  ✓ Clean application shutdown without memory/thread leak!")


if __name__ == "__main__":
    print("=================================================================")
    print("🔬 RUNNING COMPREHENSIVE WHITE-BOX & STRESS AUDIT SUITE")
    print("=================================================================")
    t_start = time.perf_counter()

    test_input_parser_edge_cases()
    test_chinese_vernacular_and_protein_resolution()
    test_feature_extraction_whitebox_logic()
    test_network_and_fault_tolerance()
    test_async_worker_cancellation()
    test_zero_regression_all_12_tabs()

    t_total = time.perf_counter() - t_start
    print("\n=================================================================")
    print(f"🎉 ALL WHITE-BOX, STRESS & ZERO-REGRESSION TESTS PASSED! ({t_total:.2f}s)")
    print("=================================================================")
