import os
import sys
import hashlib
import zipfile
import platform
from pathlib import Path
from datetime import datetime
from src.core.project_manager import PhyloProject, STEP_KEYS, STEP_TITLES, StepRecord


def compute_file_sha256(file_path: Path | str) -> str:
    """Computes SHA-256 hash of a file in 64KB blocks."""
    p = Path(file_path)
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def format_file_size(num_bytes: int) -> str:
    """Formats bytes into human readable KB/MB."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    else:
        return f"{num_bytes / (1024 * 1024):.2f} MB"


class ELNGenerator:
    """
    Phase 3: Academic-Grade Electronic Lab Notebook (Auto-ELN) &
    Supplementary Materials Generator.

    Features:
    - Full Data Provenance with Cryptographic SHA-256 Checksums
    - Auto-Drafting Journal Materials & Methods (English & Traditional Chinese)
    - Formal Citations & BibTeX Generator (EndNote / Zotero / Overleaf ready)
    - Multi-Format Export: GitHub-Flavored Markdown, Standalone HTML with Print CSS,
      and Bundled Publication Supplementary Package (.zip)
    """

    REFERENCES = {
        "mafft": {
            "title": "MAFFT multiple sequence alignment software version 7: improvements in performance and usability",
            "authors": "Katoh, K., & Standley, D. M.",
            "year": "2013",
            "journal": "Molecular Biology and Evolution",
            "vol": "30(4), 772-780",
            "doi": "10.1093/molbev/mst010",
            "bib": r"""@article{katoh2013mafft,
  title={MAFFT multiple sequence alignment software version 7: improvements in performance and usability},
  author={Katoh, Kazutaka and Standley, Daron M},
  journal={Molecular Biology and Evolution},
  volume={30},
  number={4},
  pages={772--780},
  year={2013},
  publisher={Oxford University Press},
  doi={10.1093/molbev/mst010}
}""",
        },
        "trimal": {
            "title": "trimAl: a tool for automated alignment trimming in large-scale phylogenetic analyses",
            "authors": "Capella-Gutiérrez, S., Silla-Martínez, J. M., & Gabaldón, T.",
            "year": "2009",
            "journal": "Bioinformatics",
            "vol": "25(15), 1972-1973",
            "doi": "10.1093/bioinformatics/btp348",
            "bib": r"""@article{capella2009trimal,
  title={trimAl: a tool for automated alignment trimming in large-scale phylogenetic analyses},
  author={Capella-Guti{\'e}rrez, Salvador and Silla-Mart{\'\i}nez, Jos{\'e} M and Gabald{\'o}n, Toni},
  journal={Bioinformatics},
  volume={25},
  number={15},
  pages={1972--1973},
  year={2009},
  publisher={Oxford University Press},
  doi={10.1093/bioinformatics/btp348}
}""",
        },
        "modelfinder": {
            "title": "ModelFinder: fast model selection for accurate phylogenetic estimates",
            "authors": "Kalyaanamoorthy, S., Minh, B. Q., Wong, T. K., von Haeseler, A., & Jermiin, L. S.",
            "year": "2017",
            "journal": "Nature Methods",
            "vol": "14(6), 587-589",
            "doi": "10.1038/nmeth.4285",
            "bib": r"""@article{kalyaanamoorthy2017modelfinder,
  title={ModelFinder: fast model selection for accurate phylogenetic estimates},
  author={Kalyaanamoorthy, Subha and Minh, Bui Quang and Wong, Thomas KF and von Haeseler, Arndt and Jermiin, Lars S},
  journal={Nature Methods},
  volume={14},
  number={6},
  pages={587--589},
  year={2017},
  publisher={Nature Publishing Group},
  doi={10.1038/nmeth.4285}
}""",
        },
        "iqtree": {
            "title": "IQ-TREE 2: new models and efficient methods for phylogenetic inference in the genomic era",
            "authors": "Minh, B. Q., Schmidt, H. A., Chernomor, O., Schrempf, D., Woodhams, M. D., von Haeseler, A., & Lanfear, R.",
            "year": "2020",
            "journal": "Molecular Biology and Evolution",
            "vol": "37(5), 1530-1534",
            "doi": "10.1093/molbev/msaa015",
            "bib": r"""@article{minh2020iqtree,
  title={IQ-TREE 2: new models and efficient methods for phylogenetic inference in the genomic era},
  author={Minh, Bui Quang and Schmidt, Heiko A and Chernomor, Olga and Schrempf, Dominik and Woodhams, Michael D and von Haeseler, Arndt and Lanfear, Robert},
  journal={Molecular Biology and Evolution},
  volume={37},
  number={5},
  pages={1530--1534},
  year={2020},
  publisher={Oxford University Press},
  doi={10.1093/molbev/msaa015}
}""",
        },
        "ufboot": {
            "title": "UFBoot2: improving the ultrafast bootstrap approximation",
            "authors": "Hoang, D. T., Chernomor, O., von Haeseler, A., Minh, B. Q., & Vinh, L. S.",
            "year": "2018",
            "journal": "Molecular Biology and Evolution",
            "vol": "35(2), 518-522",
            "doi": "10.1093/molbev/msx281",
            "bib": r"""@article{hoang2018ufboot2,
  title={UFBoot2: improving the ultrafast bootstrap approximation},
  author={Hoang, Diep Thi and Chernomor, Olga and von Haeseler, Arndt and Minh, Bui Quang and Vinh, Le Sy},
  journal={Molecular Biology and Evolution},
  volume={35},
  number={2},
  pages={518--522},
  year={2018},
  publisher={Oxford University Press},
  doi={10.1093/molbev/msx281}
}""",
        },
        "lsd2": {
            "title": "A fast dating algorithm for large trees (LSD2)",
            "authors": "To, T. H., Jung, M., Lycett, S., & Gascuel, O.",
            "year": "2016",
            "journal": "Systematic Biology",
            "vol": "65(1), 82-97",
            "doi": "10.1093/sysbio/syv068",
            "bib": r"""@article{to2016lsd2,
  title={A fast dating algorithm for large trees},
  author={To, Thu-Hien and Jung, Marcel and Lycett, Samantha and Gascuel, Olivier},
  journal={Systematic Biology},
  volume={65},
  number={1},
  pages={82--97},
  year={2016},
  publisher={Oxford University Press},
  doi={10.1093/sysbio/syv068}
}""",
        },
        "biopython": {
            "title": "Biopython: freely available Python tools for computational molecular biology and bioinformatics",
            "authors": "Cock, P. J., Antao, T., Chang, J. T., Chapman, B. A., Cox, C. J., Dalke, A., ... & de Hoon, M. J.",
            "year": "2009",
            "journal": "Bioinformatics",
            "vol": "25(11), 1422-1423",
            "doi": "10.1093/bioinformatics/btp163",
            "bib": r"""@article{cock2009biopython,
  title={Biopython: freely available Python tools for computational molecular biology and bioinformatics},
  author={Cock, Peter JA and Antao, Tiago and Chang, Jeffrey T and Chapman, Brad A and Cox, Cymon J and Dalke, Andrew and Friedberg, Iddo and Hamelryck, Thomas and Kauff, Frank and Wilczynski, Bartek and others},
  journal={Bioinformatics},
  volume={25},
  number={11},
  pages={1422--1423},
  year={2009},
  publisher={Oxford University Press},
  doi={10.1093/bioinformatics/btp163}
}""",
        },
    }

    @classmethod
    def get_audit_trail(cls, project: PhyloProject) -> list[dict]:
        """
        Gathers cryptographic SHA-256 hashes, file sizes, and timestamps
        for all registered step output files.
        """
        audit_records = []
        for key in STEP_KEYS:
            rec = project.steps.get(key)
            if not rec or not rec.output_files:
                continue
            for f_str in rec.output_files:
                p = Path(f_str)
                if p.is_file():
                    stat = p.stat()
                    sha = compute_file_sha256(p)
                    audit_records.append({
                        "step_key": key,
                        "step_folder": STEP_TITLES[key][1],
                        "step_title": STEP_TITLES[key][0].split()[1],
                        "filename": p.name,
                        "path": str(p.resolve()),
                        "size_bytes": stat.st_size,
                        "size_fmt": format_file_size(stat.st_size),
                        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "sha256": sha,
                    })
        return audit_records

    @classmethod
    def generate_materials_and_methods(cls, project: PhyloProject) -> dict[str, str]:
        """
        Synthesizes publication-grade Materials and Methods paragraphs in English and Traditional Chinese.
        """
        p_raw = project.steps.get("raw")
        p_san = project.steps.get("sanitize")
        p_aln = project.steps.get("alignment")
        p_trm = project.steps.get("trimming")
        p_mf = project.steps.get("modelfinder")
        p_tre = project.steps.get("tree")
        p_lsd = project.steps.get("timetree")

        # Extract parameters
        aln_params = p_aln.parameters if p_aln else {}
        aln_algo = aln_params.get("strategy", "auto")
        aln_algo_name = {
            "localpair": "L-INS-i iterative refinement",
            "globalpair": "G-INS-i iterative refinement",
            "fftns2": "FFT-NS-2 fast progressive heuristic",
            "auto": "auto-selected heuristic",
        }.get(aln_algo, aln_algo)

        trm_params = p_trm.parameters if p_trm else {}
        trm_method = trm_params.get("method", "automated1")

        mf_params = p_mf.parameters if p_mf else {}
        best_model = mf_params.get("best_model") or (p_tre.parameters.get("model") if p_tre else "MFP")
        if not best_model or best_model == "MFP":
            best_model = "the optimal substitution model selected by ModelFinder"

        tre_params = p_tre.parameters if p_tre else {}
        boot = tre_params.get("bootstrap", 1000)
        alrt = tre_params.get("alrt", 1000)

        # 1. English Academic Draft
        en_lines = [
            "### Sequence Quality Control and Multiple Sequence Alignment",
            f"Taxonomic sequence records were sanitized and validated for header integrity and length distribution using the automated QC pipeline in PhyloCraft. ",
            f"Multiple sequence alignment was conducted using MAFFT v7 (Katoh & Standley, 2013) implementing the {aln_algo_name} strategy. ",
        ]

        if p_trm and p_trm.status == "completed":
            en_lines.append(
                f"To minimize phylogenetic noise from poorly aligned or excessively gapped regions, the alignment was filtered using trimAl v1.4 (Capella-Gutiérrez et al., 2009) "
                f"with the heuristic '{trm_method}' algorithm. "
            )

        en_lines.append("\n### Model Selection and Maximum Likelihood Phylogenetic Inference\n")
        en_lines.append(
            f"The optimal nucleotide/amino-acid substitution model was determined using ModelFinder (Kalyaanamoorthy et al., 2017) "
            f"based on the Bayesian Information Criterion (BIC). The best-fitting model was identified as {best_model}. "
            f"Maximum likelihood (ML) phylogenetic reconstruction was performed with IQ-TREE 2 (Minh et al., 2020). "
            f"Branch support was evaluated using {boot:,} ultrafast bootstrap (UFBoot2) replicates (Hoang et al., 2018) "
            f"and {alrt:,} replicates of the SH-like approximate likelihood ratio test (SH-aLRT; Guindon et al., 2010). "
            f"Clades with UFBoot >= 95% and SH-aLRT >= 80% were considered robustly supported. "
        )

        if p_lsd and p_lsd.status == "completed":
            en_lines.append(
                f"Divergence times and TimeTree topologies were estimated using the Least-Squares Dating (LSD2) method (To et al., 2016) "
                f"under a strict or relaxed molecular clock with outlier detection (Z-score cutoff = 3.0). "
            )

        en_lines.append(
            f"Phylogenetic tree visualization and annotation were carried out within PhyloCraft."
        )

        # 2. Traditional Chinese Academic Draft
        zh_lines = [
            "### 序列品質管制與多重序列比對 (Quality Control & Alignment)",
            "本研究所有分子序列標頭均經由 PhyloCraft 自動化品質防呆模組進行正規化清洗與長度檢驗。",
            f"多重序列比對採用 MAFFT v7（Katoh & Standley, 2013）之 {aln_algo_name} 演算法進行精確對齊。",
        ]

        if p_trm and p_trm.status == "completed":
            zh_lines.append(
                f"比對矩陣隨後以 trimAl v1.4（Capella-Gutiérrez et al., 2009）之 '{trm_method}' 智慧啟發式演算法過濾低資訊量與高空缺率位點，以降低系統發育雜訊。"
            )

        zh_lines.append("\n### 分子取代模型檢定與系統發育樹推論 (Model Selection & Phylogeny)\n")
        zh_lines.append(
            f"依據貝氏資訊標準（Bayesian Information Criterion, BIC），以 ModelFinder（Kalyaanamoorthy et al., 2017）檢驗候選取代模型空間，"
            f"判定最適演化替代模型為 {best_model}。"
            f"系統發育樹採用最大概似法（Maximum Likelihood, ML），以 IQ-TREE 2（Minh et al., 2020）進行拓撲推論。"
            f"分支拓撲支持度檢驗採用 {boot:,} 次極速拔靴複製法（Ultrafast Bootstrap, UFBoot2；Hoang et al., 2018）"
            f"與 {alrt:,} 次 SH-aLRT 檢驗（Guindon et al., 2010）。"
            f"統計上以 UFBoot >= 95% 且 SH-aLRT >= 80% 視為具高度統計支持力之單系群。"
        )

        if p_lsd and p_lsd.status == "completed":
            zh_lines.append(
                "地質年代定年與分子鐘時間樹（TimeTree）估算採用 LSD2 最小平方法（To et al., 2016），結合化石校準或採樣年代校準節點年代。"
            )

        zh_lines.append("演化樹視覺化與分支拓撲註解皆於 PhyloCraft 視覺化演化生物學工作站完成。")

        return {
            "english": "".join(en_lines),
            "chinese": "".join(zh_lines),
        }

    @classmethod
    def generate_bibtex(cls, project: PhyloProject) -> str:
        """Gathers BibTeX entries for all active tools in the project."""
        used_keys = ["mafft", "trimal", "modelfinder", "iqtree", "ufboot", "biopython"]
        p_lsd = project.steps.get("timetree")
        if p_lsd and p_lsd.status == "completed":
            used_keys.append("lsd2")

        bib_entries = [cls.REFERENCES[k]["bib"] for k in used_keys if k in cls.REFERENCES]
        return "\n\n".join(bib_entries)

    @classmethod
    def generate_citations_list(cls, project: PhyloProject) -> list[str]:
        """Gathers formatted APA citations for all active tools."""
        used_keys = ["iqtree", "modelfinder", "ufboot", "mafft", "trimal", "biopython"]
        p_lsd = project.steps.get("timetree")
        if p_lsd and p_lsd.status == "completed":
            used_keys.append("lsd2")

        citations = []
        for k in used_keys:
            ref = cls.REFERENCES.get(k)
            if ref:
                citations.append(
                    f"{ref['authors']} ({ref['year']}). {ref['title']}. {ref['journal']}, {ref['vol']}. https://doi.org/{ref['doi']}"
                )
        return citations

    @classmethod
    def generate_markdown(cls, project: PhyloProject) -> str:
        """
        Compiles the full publication-grade Markdown Electronic Lab Notebook (lab_notebook.md).
        """
        audit_trail = cls.get_audit_trail(project)
        methods = cls.generate_materials_and_methods(project)
        citations = cls.generate_citations_list(project)

        md = [
            f"# 生物演化學論文級電子實驗紀錄簿 (Electronic Lab Notebook - ELN)",
            f"",
            f"> **PhyloCraft 科研工作站自動編譯報告 ｜ 符合國際學術期刊（Syst. Biol., MBE, Nature Comm.）標準**",
            f"",
            f"| 專案屬性項目 | 詳細資訊 |",
            f"| :--- | :--- |",
            f"| **專案名稱** | `{project.name}` |",
            f"| **研究負責人** | **{project.author}** |",
            f"| **專案研究目標** | {project.description} |",
            f"| **專案本機路徑** | `{project.project_dir}` |",
            f"| **建立時間** | `{project.created_at}` |",
            f"| **最後同步時間** | `{project.updated_at}` |",
            f"| **計算環境規格** | {platform.system()} {platform.release()} ({platform.machine()}), Python {platform.python_version()} |",
            f"",
            f"---",
            f"",
            f"## 一、 分析工作流各步驟詳細軌跡 (Analysis Provenance Trail)",
            f"",
        ]

        status_emojis = {
            "completed": "[已完成]",
            "running": "[執行中]",
            "failed": "[失敗]",
            "pending": "[待執行]",
        }

        for idx, key in enumerate(STEP_KEYS, 1):
            title, sub = STEP_TITLES[key]
            rec = project.steps.get(key, StepRecord())
            status_text = status_emojis.get(rec.status, "[待執行]")

            md.append(f"### 步驟 {idx}: {title} ｜ `{status_text}`")
            md.append(f"- **執行狀態**: `{rec.status}`")
            if rec.timestamp:
                md.append(f"- **執行時間戳記**: `{rec.timestamp}`")
            md.append(f"- **階段成果摘要**: {rec.summary}")

            if rec.parameters:
                params_str = ", ".join(f"`{k}={v}`" for k, v in rec.parameters.items())
                md.append(f"- **分析設定參數**: {params_str}")

            if rec.command_line:
                md.append(f"- **底層執行指令**: `{rec.command_line}`")

            if rec.output_files:
                md.append(f"- **產出檔案清單**:")
                for out_f in rec.output_files:
                    p = Path(out_f)
                    size_str = format_file_size(p.stat().st_size) if p.exists() else "N/A"
                    md.append(f"  - `{p.name}` ({size_str}) -> `{out_f}`")

            if rec.student_notes and rec.student_notes.strip():
                md.append(f"- **實驗備忘筆記**:")
                for n_line in rec.student_notes.strip().splitlines():
                    md.append(f"  > *{n_line}*")
            else:
                md.append(f"- **實驗備忘筆記**: *(無紀錄)*")

            md.append("")

        # Section 2: Materials & Methods Draft
        md.append("---")
        md.append("## 二、 論文材料與方法草稿 (Materials & Methods Draft)")
        md.append("")
        md.append("#### Academic English (適用於國際英文期刊投稿):")
        md.append(f"```text\n{methods['english']}\n```")
        md.append("")
        md.append("#### 繁體中文學術版（適用於碩博士論文或國科會報告）:")
        md.append(f"```text\n{methods['chinese']}\n```")
        md.append("")

        # Section 3: Data Integrity Audit Trail
        md.append("---")
        md.append("## 三、 數據全生命週期防偽審計 (Cryptographic Audit Trail)")
        md.append("")
        md.append("依循 FAIR（Findable, Accessible, Interoperable, Reusable）數據原則，所有輸入與中間過程產物均附帶 SHA-256 數位指紋以確保科研數據不可竄改性：")
        md.append("")
        md.append("| 階段模組 | 檔案名稱 | 大小 | SHA-256 數位指紋 (Checksum) |")
        md.append("| :--- | :--- | :--- | :--- |")
        for rec in audit_trail:
            md.append(f"| {rec['step_title']} | `{rec['filename']}` | {rec['size_fmt']} | `{rec['sha256'][:16]}...{rec['sha256'][-8:]}` |")
        md.append("")

        # Section 4: Literature Citations
        md.append("---")
        md.append("## 四、 軟體工具正式學術引用 (References & Citations)")
        md.append("")
        for cite in citations:
            md.append(f"- {cite}")
        md.append("")

        md.append("---")
        md.append(
            f"*本報告由 PhyloCraft 演化生物學工作站於 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 自動編譯產出。*"
        )

        return "\n".join(md)

    @classmethod
    def generate_html(cls, project: PhyloProject) -> str:
        """
        Compiles a publication-grade standalone HTML Electronic Lab Notebook (lab_notebook.html)
        complete with responsive styling, KaTeX-style badges, print CSS, and collapsible sections.
        """
        audit_trail = cls.get_audit_trail(project)
        methods = cls.generate_materials_and_methods(project)
        citations = cls.generate_citations_list(project)
        bibtex = cls.generate_bibtex(project)

        # Build steps cards HTML
        step_cards_html = []
        for idx, key in enumerate(STEP_KEYS, 1):
            title, sub = STEP_TITLES[key]
            rec = project.steps.get(key, StepRecord())
            status_colors = {
                "completed": ("#1e3a2f", "#a6da95", "[已完成]"),
                "running": ("#4a3b1a", "#eed49f", "[執行中]"),
                "failed": ("#4a1b1b", "#ed8796", "[失敗]"),
                "pending": ("#1e2030", "#a5adcb", "[待執行]"),
            }
            bg_col, txt_col, badge_text = status_colors.get(rec.status, status_colors["pending"])

            params_html = ""
            if rec.parameters:
                p_items = "".join(f"<span class='pill'><b>{k}</b>: {v}</span>" for k, v in rec.parameters.items())
                params_html = f"<div class='section-item'><b>參數設定:</b> {p_items}</div>"

            cmd_html = ""
            if rec.command_line:
                cmd_html = f"<div class='section-item'><b>終端機指令:</b> <code class='cmd-box'>{rec.command_line}</code></div>"

            files_html = ""
            if rec.output_files:
                f_list = "".join(f"<li><code>{Path(f).name}</code> <span class='sub-text'>({f})</span></li>" for f in rec.output_files)
                files_html = f"<div class='section-item'><b>產出檔案:</b><ul class='file-list'>{f_list}</ul></div>"

            notes_html = ""
            if rec.student_notes and rec.student_notes.strip():
                notes_escaped = "<br>".join(rec.student_notes.strip().splitlines())
                notes_html = (
                    f"<div class='note-callout'>"
                    f"<b>實驗備忘筆記:</b><br>"
                    f"<em>{notes_escaped}</em>"
                    f"</div>"
                )

            card_html = f"""
            <div class="step-card">
                <div class="step-header">
                    <span class="step-title">步驟 {idx}: {title}</span>
                    <span class="status-badge" style="background-color: {bg_col}; color: {txt_col};">{badge_text}</span>
                </div>
                <div class="step-body">
                    <div class="section-item"><b>執行成果:</b> {rec.summary or '尚未執行'}</div>
                    {f"<div class='section-item'><b>時間戳記:</b> {rec.timestamp}</div>" if rec.timestamp else ""}
                    {params_html}
                    {cmd_html}
                    {files_html}
                    {notes_html}
                </div>
            </div>
            """
            step_cards_html.append(card_html)

        # Build Audit Trail Rows
        audit_rows_html = []
        for r in audit_trail:
            audit_rows_html.append(f"""
            <tr>
                <td><b>{r['step_title']}</b></td>
                <td><code>{r['filename']}</code></td>
                <td>{r['size_fmt']}</td>
                <td><code class="hash-code">{r['sha256']}</code></td>
            </tr>
            """)

        # Build Citations HTML
        cites_html = "".join(f"<li>{c}</li>" for c in citations)

        html_template = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>電子實驗紀錄簿 (ELN) - {project.name}</title>
    <style>
        :root {{
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-color: #1e293b;
            --heading-color: #006644;
            --border-color: #e2e8f0;
            --accent-green: #006644;
            --accent-orange: #d97706;
            --accent-yellow: #b45309;
            --code-bg: #f1f5f9;
        }}

        @media screen {{
            body {{
                background-color: var(--bg-color);
                color: var(--text-color);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 24px;
                line-height: 1.6;
            }}
            .container {{
                max-width: 960px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid var(--border-color);
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
                padding: 36px 44px;
            }}
        }}

        @media print {{
            body {{
                background-color: #ffffff;
                color: #111111;
                font-family: Georgia, 'Times New Roman', serif;
                margin: 0;
                padding: 10mm;
            }}
            .container {{
                max-width: 100%;
                margin: 0;
                padding: 0;
                box-shadow: none;
                border: none;
            }}
            .step-card {{
                page-break-inside: avoid;
                border: 1px solid #ccc !important;
                background-color: #fafafa !important;
                color: #111 !important;
            }}
            .note-callout {{
                border-left: 3px solid #666 !important;
                background-color: #f2f2f2 !important;
                color: #222 !important;
            }}
            .status-badge {{
                border: 1px solid #888 !important;
                color: #000 !important;
            }}
            .no-print {{
                display: none !important;
            }}
        }}

        h1, h2, h3, h4 {{
            color: var(--heading-color);
            margin-top: 24px;
            margin-bottom: 12px;
        }}
        h1 {{
            font-size: 26px;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 12px;
        }}
        h2 {{
            font-size: 20px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
            margin-top: 36px;
        }}
        h3 {{
            font-size: 16px;
        }}

        .meta-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
        }}
        .meta-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid var(--border-color);
        }}
        .meta-table td:first-child {{
            font-weight: bold;
            color: var(--accent-orange);
            width: 180px;
        }}

        .step-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            margin-bottom: 16px;
            overflow: hidden;
        }}
        .step-header {{
            background-color: #f8fafc;
            padding: 12px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
        }}
        .step-title {{
            font-weight: bold;
            font-size: 15px;
            color: #0f172a;
        }}
        .status-badge {{
            font-size: 11px;
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 12px;
        }}
        .step-body {{
            padding: 16px;
        }}
        .section-item {{
            margin-bottom: 8px;
            font-size: 13px;
        }}
        .pill {{
            background-color: #f1f5f9;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 12px;
            margin-right: 6px;
            color: var(--accent-yellow);
        }}
        .cmd-box {{
            background-color: var(--code-bg);
            color: var(--accent-green);
            padding: 4px 8px;
            border-radius: 4px;
            font-family: Consolas, monospace;
            font-size: 12px;
            display: inline-block;
        }}
        .file-list {{
            margin: 6px 0 0 20px;
            padding: 0;
            font-size: 12px;
        }}
        .file-list li {{
            margin-bottom: 4px;
        }}
        .sub-text {{
            color: #64748b;
            font-size: 11px;
        }}
        .note-callout {{
            background-color: #fffbeb;
            border-left: 4px solid var(--accent-orange);
            border-radius: 4px;
            padding: 10px 14px;
            margin-top: 10px;
            font-size: 13px;
            color: #92400e;
        }}
        .audit-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            margin-top: 12px;
        }}
        .audit-table th, .audit-table td {{
            border: 1px solid var(--border-color);
            padding: 8px 10px;
            text-align: left;
        }}
        .audit-table th {{
            background-color: #f8fafc;
            color: var(--heading-color);
        }}
        .hash-code {{
            font-family: Consolas, monospace;
            font-size: 11px;
            color: var(--accent-green);
            word-break: break-all;
        }}
        .pre-box {{
            background-color: var(--code-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 14px;
            font-family: Consolas, Georgia, monospace;
            font-size: 13px;
            line-height: 1.5;
            white-space: pre-wrap;
            color: #cad3f5;
        }}
        .footer {{
            margin-top: 40px;
            border-top: 1px solid var(--border-color);
            padding-top: 16px;
            font-size: 12px;
            color: #a5adcb;
            text-align: center;
        }}
        .print-btn {{
            background-color: #3b5284;
            color: #ffffff;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: bold;
            cursor: pointer;
            margin-bottom: 20px;
        }}
        .print-btn:hover {{
            background-color: #4b66a0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="no-print" style="text-align: right;">
            <button class="print-btn" onclick="window.print()">列印或存為 PDF (Print / Save as PDF)</button>
        </div>

        <h1>生物演化學論文級電子實驗紀錄簿 (Electronic Lab Notebook)</h1>
        <p style="color: #a5adcb; font-size: 13px;">PhyloCraft 科研工作站自動編譯報告 ｜ 符合國際學術期刊（Systematic Biology、MBE、Nature Communications）論文標準</p>

        <table class="meta-table">
            <tr><td>專案名稱:</td><td><code>{project.name}</code></td></tr>
            <tr><td>研究負責人:</td><td><b>{project.author}</b></td></tr>
            <tr><td>專案研究目的:</td><td>{project.description}</td></tr>
            <tr><td>專案儲存位置:</td><td><code>{project.project_dir}</code></td></tr>
            <tr><td>建立時間:</td><td>{project.created_at}</td></tr>
            <tr><td>最後同步時間:</td><td>{project.updated_at}</td></tr>
            <tr><td>計算環境:</td><td>{platform.system()} {platform.release()} ({platform.machine()}), Python {platform.python_version()}</td></tr>
        </table>

        <h2>一、 分析工作流各步驟詳細軌跡 (Analysis Provenance Trail)</h2>
        {''.join(step_cards_html)}

        <h2>二、 論文材料與方法段落草稿 (Materials & Methods Draft)</h2>
        <h3>Academic English (適用於國際期刊投稿):</h3>
        <div class="pre-box">{methods['english']}</div>

        <h3>繁體中文學術版（適用於學位論文或研究報告）:</h3>
        <div class="pre-box">{methods['chinese']}</div>

        <h2>三、 數據全生命週期防偽審計 (Cryptographic Audit Trail)</h2>
        <p style="font-size: 13px; color: #a5adcb;">
            依循國際頂級期刊之數據重現性政策，所有原始與中間過渡檔案均以 SHA-256 演算法進行雜湊驗證：
        </p>
        <table class="audit-table">
            <thead>
                <tr>
                    <th style="width: 15%;">階段模組</th>
                    <th style="width: 25%;">檔案名稱</th>
                    <th style="width: 10%;">檔案大小</th>
                    <th style="width: 50%;">SHA-256 數位指紋 (Checksum)</th>
                </tr>
            </thead>
            <tbody>
                {''.join(audit_rows_html)}
            </tbody>
        </table>

        <h2>四、 軟體工具正式學術引用 (References & Citations)</h2>
        <ul style="font-size: 13px; line-height: 1.6;">
            {cites_html}
        </ul>

        <h3>BibTeX 引用項目 (可直接導入 Zotero / EndNote / Overleaf):</h3>
        <div class="pre-box" style="font-family: Consolas, monospace; font-size: 11px;">{bibtex}</div>

        <div class="footer">
            本報告由 PhyloCraft 視覺化演化生物學工作站於 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 自動編譯產出。
        </div>
    </div>
</body>
</html>
        """
        return html_template

    @classmethod
    def export_supplementary_zip(cls, project: PhyloProject, zip_output_path: Path | str) -> str:
        """
        Bundles all notebook outputs, methods drafts, bibtex citations, and core dataset files
        into a single publication-ready Supplementary Materials .zip archive.
        """
        z_path = Path(zip_output_path)
        z_path.parent.mkdir(parents=True, exist_ok=True)

        md_content = cls.generate_markdown(project)
        html_content = cls.generate_html(project)
        methods = cls.generate_materials_and_methods(project)
        bibtex = cls.generate_bibtex(project)

        with zipfile.ZipFile(z_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Text and report documents
            zf.writestr(f"{project.name}_ELN_Notebook.md", md_content)
            zf.writestr(f"{project.name}_ELN_Notebook.html", html_content)
            zf.writestr(f"{project.name}_Materials_and_Methods_Draft.txt", f"=== ACADEMIC ENGLISH ===\n\n{methods['english']}\n\n\n=== TRADITIONAL CHINESE ===\n\n{methods['chinese']}")
            zf.writestr("references.bib", bibtex)

            # 2. Add actual output files from project
            for key in STEP_KEYS:
                rec = project.steps.get(key)
                if not rec or not rec.output_files:
                    continue
                subfolder = STEP_TITLES[key][1]
                for f_str in rec.output_files:
                    p = Path(f_str)
                    if p.is_file():
                        arc_name = f"data/{subfolder}/{p.name}"
                        zf.write(p, arc_name)

        return str(z_path.resolve())
