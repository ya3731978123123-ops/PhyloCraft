import sys
import os
import shutil
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq
from Bio import Phylo

from src.config import BASE_DIR, BIN_DIR, DATA_DIR, OUTPUT_DIR, find_tool, get_tool_status
from src.core.sanitizer import clean_taxon_name, detect_seq_type, sanitize_fasta_file, save_sanitized_fasta
from src.core.converter import convert_alignment
from src.core.concatenator import concatenate_alignments
from src.core.project_manager import ProjectManager, PhyloProject, STEP_KEYS
from src.core.eln_generator import ELNGenerator, compute_file_sha256, format_file_size
from src.core.iqtree_parser import parse_iqtree_report
from src.core.runners.base_runner import CommandRunner
from src.core.runners.mafft_runner import MafftRunner
from src.core.runners.trimal_runner import TrimalRunner
from src.core.runners.modelfinder_runner import ModelFinderRunner
from src.core.runners.iqtree_runner import IQTreeRunner


def test_audit():
    print("=" * 60)
    print("🚀 STARTING PHYLOMETRIC FULL SYSTEM AUDIT & REGRESSION TESTS")
    print("=" * 60)

    # 1. Test Tools Availability
    print("\n[Audit 1/11] Checking Tool Detection & Configurations...")
    status = get_tool_status()
    for k, v in status.items():
        print(f"  • {v['name']}: {'FOUND' if v['found'] else 'NOT FOUND'} ({v['path']})")
    assert status["mafft"]["found"], "MAFFT must be found"
    assert status["trimal"]["found"], "trimAl must be found"
    assert status["iqtree"]["found"], "IQ-TREE must be found"
    print("  ✓ Tools detection passed!")

    # Setup isolated test sandbox
    test_dir = Path(tempfile.mkdtemp(prefix="phylo_audit_"))
    # Ensure pre-test cleanliness of OUTPUT_DIR
    recent_file = OUTPUT_DIR / ".recent_projects.json"
    if recent_file.exists():
        recent_file.unlink(missing_ok=True)
    for p in OUTPUT_DIR.glob("*.phylo"):
        shutil.rmtree(p, ignore_errors=True)

    try:
        # 2. Test Sanitizer & FASTA Header Integrity
        print("\n[Audit 2/11] Testing Sanitizer & Header Purity...")
        dirty_fasta = test_dir / "dirty_sample.fasta"
        with open(dirty_fasta, "w", encoding="utf-8") as f:
            f.write(">Homo sapiens (Human) [Cytb]:1\nATGCGATCGATCGATCGATCGATCGATCGA\n")
            f.write(">Homo sapiens (Human) [Cytb]:1\nATGCGATCGATCGATCGATCGATCGATCGA\n")
            f.write(">Pan troglodytes/Chimp|specimen=99\nATGCGATCGATCGATCGATCGATCGATCGA\n")

        san_res = sanitize_fasta_file(dirty_fasta)
        assert san_res.success, f"Sanitization failed: {san_res.warnings}"
        assert san_res.total_taxa == 3
        assert san_res.seq_type == "DNA"
        # Duplicate detection
        assert len(san_res.warnings) >= 1
        clean_fasta = test_dir / "clean_sample.fasta"
        save_sanitized_fasta(san_res.cleaned_records, clean_fasta)

        # Inspect raw file content to ensure no description leak
        raw_lines = clean_fasta.read_text(encoding="utf-8").splitlines()
        for line in raw_lines:
            if line.startswith(">"):
                assert " " not in line, f"Header contains illegal spaces: {line}"
                assert ":" not in line, f"Header contains illegal colons: {line}"
                assert "=" not in line, f"Header contains description leak: {line}"
                print(f"  Clean header verified: {line}")
        print("  ✓ Sanitizer & Header Purity passed!")

        # 3. Test Alignment Format Converter
        print("\n[Audit 3/11] Testing Format Converter...")
        phy_out = test_dir / "converted.phy"
        ok, msg = convert_alignment(clean_fasta, phy_out, out_format="phylip-relaxed")
        assert ok, f"PHYLIP conversion failed: {msg}"
        assert phy_out.exists() and phy_out.stat().st_size > 0
        nex_out = test_dir / "converted.nex"
        ok, msg = convert_alignment(clean_fasta, nex_out, out_format="nexus")
        assert ok, f"NEXUS conversion failed: {msg}"
        assert nex_out.exists() and nex_out.stat().st_size > 0
        print("  ✓ Format conversion (FASTA -> PHYLIP-Relaxed & NEXUS) passed!")

        # 4. Test Supermatrix Concatenator & Partition Generator
        print("\n[Audit 4/11] Testing Multi-Gene Concatenation & Partitioning...")
        gene1 = test_dir / "gene1.fasta"
        gene2 = test_dir / "gene2.fasta"
        with open(gene1, "w", encoding="utf-8") as f:
            f.write(">Taxon_A\nATGCCCGGG\n>Taxon_B\nATG---GGG\n>Taxon_C\nATGCCCGGG\n")
        with open(gene2, "w", encoding="utf-8") as f:
            f.write(">Taxon_A\nTTTAAA\n>Taxon_B\nTTTAAA\n")  # Taxon_C missing

        super_fa = test_dir / "supermatrix.fasta"
        super_part = test_dir / "partitions.nex"
        concat_res = concatenate_alignments(
            [gene1, gene2],
            super_fa,
            super_part,
            partition_style="iqtree",
            codon_partition=True,
        )
        assert concat_res.success, f"Concat failed: {concat_res.message}"
        assert concat_res.total_taxa == 3
        assert concat_res.total_sites == 15  # 9 + 6
        assert "gene2" in concat_res.missing_taxa_report
        assert "Taxon_C" in concat_res.missing_taxa_report["gene2"]
        # Check that Taxon_C got padded with '?' for gene2
        super_recs = {r.id: str(r.seq) for r in SeqIO.parse(str(super_fa), "fasta")}
        assert super_recs["Taxon_C"] == "ATGCCCGGG??????", f"Padding incorrect: {super_recs['Taxon_C']}"
        part_txt = super_part.read_text(encoding="utf-8")
        assert "charset" in part_txt
        print(f"  Supermatrix generated: {concat_res.total_taxa} taxa, {concat_res.total_sites} sites.")
        print(f"  Missing taxa correctly reported and padded with '?'.")
        print("  ✓ Multi-Gene Concatenation passed!")

        # 5. Test MAFFT Runner with Clean Stdout Redirection
        print("\n[Audit 5/11] Testing MAFFT Alignment Runner...")
        mafft_runner = MafftRunner()
        aln_out = test_dir / "primates_aligned.fasta"
        logs = []
        ok, msg = mafft_runner.run_alignment(
            DATA_DIR / "primates_cytb.fasta",
            aln_out,
            algorithm="auto",
            threads=-1,
            log_callback=logs.append,
        )
        assert ok, f"MAFFT failed: {msg}"
        assert aln_out.exists() and aln_out.stat().st_size > 0
        aln_recs = list(SeqIO.parse(str(aln_out), "fasta"))
        assert len(aln_recs) == 6
        lengths = {len(r.seq) for r in aln_recs}
        assert len(lengths) == 1, f"Alignment lengths differ! {lengths}"
        aln_len = lengths.pop()
        print(f"  MAFFT aligned {len(aln_recs)} taxa to uniform length of {aln_len} bp.")
        print("  ✓ MAFFT Alignment passed with 100% clean sequence integrity!")

        # 6. Test trimAl Runner
        print("\n[Audit 6/11] Testing trimAl Trimming Runner...")
        trim_runner = TrimalRunner()
        trim_out = test_dir / "primates_trimmed.fasta"
        ok, msg = trim_runner.run_trimming(aln_out, trim_out, method="automated1")
        assert ok, f"trimAl failed: {msg}"
        assert trim_out.exists() and trim_out.stat().st_size > 0
        trim_recs = list(SeqIO.parse(str(trim_out), "fasta"))
        assert len(trim_recs) == 6
        trim_len = len(trim_recs[0].seq)
        print(f"  trimAl automated1 trimmed alignment to {trim_len} bp.")
        print("  ✓ trimAl Trimming passed!")

        # 7. Test ModelFinder Runner
        print("\n[Audit 7/11] Testing ModelFinder Runner...")
        mf_runner = ModelFinderRunner()
        mf_prefix = test_dir / "primates_mf"
        mf_res = mf_runner.run_modelfinder(trim_out, mf_prefix, search_scope="TESTONLY", threads="1")
        assert mf_res.success, f"ModelFinder failed: {mf_res.message}"
        assert mf_res.best_model != "", "Best model should not be empty"
        assert len(mf_res.candidate_models) > 0, "Candidate models should be parsed"
        print(f"  ModelFinder optimal model (BIC): {mf_res.best_model}")
        print(f"  Candidate models evaluated: {len(mf_res.candidate_models)}")
        print("  ✓ ModelFinder Runner passed!")

        # 8. Test IQ-TREE 2 ML Tree Inference Runner
        print("\n[Audit 8/11] Testing IQ-TREE ML Inference Runner...")
        iq_runner = IQTreeRunner()
        iq_prefix = test_dir / "primates_tree"
        iq_res = iq_runner.run_inference(
            trim_out,
            iq_prefix,
            model=mf_res.best_model,
            bootstrap=1000,
            alrt=1000,
            threads="1",
        )
        assert iq_res.success, f"IQ-TREE failed: {iq_res.message}"
        assert Path(iq_res.tree_file).exists(), "Treefile not found"
        assert Path(iq_res.iqtree_report).exists(), "IQ-TREE report not found"
        print(f"  Tree inferred successfully: {Path(iq_res.tree_file).name}")
        print("  ✓ IQ-TREE Tree Inference passed!")

        # 9. Test Tree Canvas Rooting & Outgroup Recommendation
        print("\n[Audit 9/11] Testing Tree Canvas Outgroup Detection & Balancing...")
        from src.ui.widgets.tree_canvas import TreeCanvasWidget
        tree = Phylo.read(str(iq_res.tree_file), "newick")
        canvas = TreeCanvasWidget()
        canvas.tree = tree
        canvas.original_tree = Phylo.read(str(iq_res.tree_file), "newick")
        candidates = canvas.detect_candidate_outgroups(tree)
        assert len(candidates) >= 1
        best_og = candidates[0]
        assert "Lemur" in best_og, f"Expected Lemur_catta to be top outgroup, got: {best_og}"
        print(f"  Auto-detected candidate outgroup: {best_og} (most divergent taxon)")

        # Test outgroup rooting
        canvas.outgroup_combo.clear()
        canvas.outgroup_combo.addItem(f"{best_og} (⭐ 推薦外群 - 演化距最遠)")
        canvas.apply_outgroup_root()
        assert "✓ 已以外群定根" in canvas.root_status_label.text()

        # Test copy_newick
        canvas.copy_newick()
        assert "✓ Newick 字串已複製" in canvas.root_status_label.text()

        # Test all tree render layouts & modes (rectangular, circular, cladogram, align tips)
        canvas.redraw_tree()
        canvas.align_tips_cb.setChecked(True)
        canvas.redraw_tree()
        canvas.branch_combo.setCurrentIndex(1)  # Cladogram
        canvas.redraw_tree()
        canvas.layout_combo.setCurrentIndex(1)  # Circular
        canvas.redraw_tree()
        canvas.layout_combo.setCurrentIndex(0)  # Reset to Rectangular
        canvas.branch_combo.setCurrentIndex(0)  # Reset to Phylogram
        canvas.apply_midpoint_root()
        assert "✓ 已套用中點定根" in canvas.root_status_label.text()
        print("  ✓ Tree Canvas Rooting & Outgroup Detection passed!")

        # 10. Test Project Manager & ELN Generator
        print("\n[Audit 10/11] Testing Project Manager & Auto-ELN Generator...")
        pm = ProjectManager()
        proj = pm.create_project("Audit_Project", test_dir, author="Audit Tester")
        assert Path(proj.project_dir).exists()
        pm.update_step("raw", "completed", "Loaded test primates fasta", [str(DATA_DIR / "primates_cytb.fasta")])
        pm.update_step("alignment", "completed", "MAFFT aligned", [str(aln_out)])
        pm.update_step("trimming", "completed", "trimAl trimmed", [str(trim_out)])
        pm.update_step("modelfinder", "completed", f"Best model: {mf_res.best_model}", [str(mf_res.iqtree_report)])
        pm.update_step("tree", "completed", "ML tree inferred", [str(iq_res.tree_file), str(iq_res.iqtree_report)])

        # Verify JSON serialization
        assert (Path(proj.project_dir) / "project.json").exists()
        reopened = pm.open_project(Path(proj.project_dir))
        assert reopened is not None
        assert reopened.name == "Audit_Project"
        assert reopened.steps["tree"].status == "completed"

        # Verify ELN Generation
        md_eln = pm.generate_lab_notebook()
        assert (Path(proj.project_dir) / "lab_notebook.md").exists()
        assert (Path(proj.project_dir) / "lab_notebook.html").exists()
        assert "SHA-256" in md_eln
        assert "Materials & Methods" in md_eln

        # Verify Supplementary ZIP package
        zip_path = test_dir / "Supplementary_Package.zip"
        res_zip = pm.export_supplementary_package(zip_path)
        assert Path(res_zip).exists() and Path(res_zip).stat().st_size > 1000
        print(f"  Supplementary Materials ZIP packaged: {Path(res_zip).stat().st_size} bytes")
        print("  ✓ Project Manager & Auto-ELN Generator passed!")

        # 11. Test Report Dialog & IQ-TREE Parser
        print("\n[Audit 11/11] Testing IQ-TREE Report Parser & Methods Synthesis...")
        rep_data = parse_iqtree_report(iq_res.iqtree_report)
        assert rep_data.success
        assert rep_data.taxa_count == 6
        assert len(rep_data.english_methods) > 100
        assert len(rep_data.chinese_methods) > 100
        assert len(rep_data.citations) >= 4
        print(f"  Parsed {rep_data.taxa_count} taxa, {rep_data.site_count} sites.")
        print(f"  Generated publication English draft: {rep_data.english_methods[:80]}...")
        print("  ✓ IQ-TREE Report Parser passed!")

    finally:
        # Clean up temporary directory and test artifacts completely
        shutil.rmtree(test_dir, ignore_errors=True)
        recent_file = OUTPUT_DIR / ".recent_projects.json"
        if recent_file.exists():
            recent_file.unlink(missing_ok=True)
        for p in OUTPUT_DIR.glob("*.phylo"):
            shutil.rmtree(p, ignore_errors=True)

    print("\n" + "=" * 60)
    print("🎉 ALL 11 AUDIT & REGRESSION TESTS PASSED FLAWLESSLY!")
    print("=" * 60)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    test_audit()
