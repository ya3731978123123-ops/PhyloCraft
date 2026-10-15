import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class TopModelInfo:
    model: str
    logl: float
    aic: float
    bic: float
    w_bic: float


@dataclass
class IQTreeReportData:
    success: bool
    input_file: str = ""
    taxa_count: int = 0
    site_count: int = 0
    constant_sites: int = 0
    constant_pct: float = 0.0
    parsimony_informative_sites: int = 0
    distinct_patterns: int = 0
    best_model: str = ""
    log_likelihood: float = 0.0
    aic: float = 0.0
    bic: float = 0.0
    tree_length: float = 0.0
    top_models: list[TopModelInfo] = field(default_factory=list)
    english_methods: str = ""
    chinese_methods: str = ""
    citations: list[str] = field(default_factory=list)
    bibtex: str = ""


def parse_iqtree_report(iqtree_path: str | Path, alignment_tool: str = "MAFFT", trimming_tool: str = "trimAl (automated1)") -> IQTreeReportData:
    """
    Parses an .iqtree file to extract scientific metrics and generates
    publication-ready Materials & Methods text and citations.
    """
    p = Path(iqtree_path)
    if not p.exists():
        return IQTreeReportData(success=False)

    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Input data
        taxa = 0
        sites = 0
        m = re.search(r"Input data:\s+(\d+)\s+sequences with\s+(\d+)\s+nucleotide", content)
        if not m:
            m = re.search(r"Input data:\s+(\d+)\s+sequences with\s+(\d+)\s+amino-acid", content)
        if m:
            taxa = int(m.group(1))
            sites = int(m.group(2))

        # Constant sites
        const_sites = 0
        const_pct = 0.0
        m = re.search(r"Number of constant sites:\s+(\d+)\s+\(=\s+([\d\.]+)\%", content)
        if m:
            const_sites = int(m.group(1))
            const_pct = float(m.group(2))

        # Parsimony informative
        parsimony_inf = 0
        m = re.search(r"Number of parsimony informative sites:\s+(\d+)", content)
        if m:
            parsimony_inf = int(m.group(1))

        # Distinct patterns
        patterns = 0
        m = re.search(r"Number of distinct site patterns:\s+(\d+)", content)
        if m:
            patterns = int(m.group(1))

        # Best-fit model
        best_model = ""
        m = re.search(r"Best-fit model according to BIC:\s+([^\r\n]+)", content)
        if m:
            best_model = m.group(1).strip()
        elif "Best-fit model:" in content:
            m = re.search(r"Best-fit model:\s+([^\r\n]+)", content)
            if m:
                best_model = m.group(1).strip()
        elif "Model of substitution:" in content:
            m = re.search(r"Model of substitution:\s+([^\r\n]+)", content)
            if m:
                best_model = m.group(1).strip()

        # LogL, AIC, BIC
        logl = 0.0
        aic = 0.0
        bic = 0.0
        m = re.search(r"Log-likelihood of the tree:\s+([-\d\.]+)", content)
        if m:
            logl = float(m.group(1))

        m = re.search(r"Akaike information criterion \(AIC\) score:\s+([\d\.]+)", content)
        if m:
            aic = float(m.group(1))

        m = re.search(r"Bayesian information criterion \(BIC\) score:\s+([\d\.]+)", content)
        if m:
            bic = float(m.group(1))

        # Tree length
        tree_len = 0.0
        m = re.search(r"Total tree length \(sum of branch lengths\):\s+([\d\.]+)", content)
        if m:
            tree_len = float(m.group(1))

        # Check for ModelFinder block in current file or sibling *_modelfinder.iqtree
        mf_content = content
        if "List of models sorted by BIC scores:" not in mf_content and "List of models sorted by AIC scores:" not in mf_content:
            base_stem = p.stem.replace("_tree", "")
            mf_candidates = [
                p.parent / f"{base_stem}_modelfinder.iqtree",
                p.parent / f"{p.stem}_modelfinder.iqtree",
            ]
            for cand in mf_candidates:
                if cand.exists():
                    try:
                        with open(cand, "r", encoding="utf-8", errors="replace") as mf_f:
                            cand_txt = mf_f.read()
                            if not best_model:
                                m = re.search(r"Best-fit model according to BIC:\s+([^\r\n]+)", cand_txt)
                                if m:
                                    best_model = m.group(1).strip()
                                elif "Model of substitution:" in cand_txt:
                                    m = re.search(r"Model of substitution:\s+([^\r\n]+)", cand_txt)
                                    if m:
                                        best_model = m.group(1).strip()
                            if "List of models sorted by BIC scores:" in cand_txt or "List of models sorted by AIC scores:" in cand_txt:
                                mf_content = cand_txt
                                break
                    except Exception:
                        pass

        # Parse top models from ModelFinder table
        top_models = []
        mf_block = re.search(r"List of models sorted by BIC scores:\s*\n+([\s\S]+?)\n\n", mf_content)
        if not mf_block:
            mf_block = re.search(r"List of models sorted by AIC scores:\s*\n+([\s\S]+?)\n\n", mf_content)

        if mf_block:
            lines = mf_block.group(1).strip().splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("Model") or line.startswith("---"):
                    continue
                parts = line.split()
                if len(parts) >= 8:
                    try:
                        m_name = parts[0]
                        m_logl = float(parts[1])
                        m_aic = float(parts[2])

                        idx = 3
                        if parts[idx] in ("+", "-"):
                            idx += 1
                        idx += 1  # skip w_aic

                        m_aicc = 0.0
                        if idx < len(parts):
                            try:
                                m_aicc = float(parts[idx])
                            except ValueError:
                                pass
                            idx += 1

                        if idx < len(parts) and parts[idx] in ("+", "-"):
                            idx += 1
                        if idx < len(parts):
                            idx += 1  # skip w_aicc

                        m_bic = 0.0
                        if idx < len(parts):
                            try:
                                m_bic = float(parts[idx])
                            except ValueError:
                                pass
                            idx += 1

                        if idx < len(parts) and parts[idx] in ("+", "-"):
                            idx += 1

                        m_wbic = 0.0
                        if idx < len(parts):
                            try:
                                m_wbic = float(parts[idx])
                            except ValueError:
                                pass

                        top_models.append(TopModelInfo(
                            model=m_name,
                            logl=m_logl,
                            aic=m_aic,
                            bic=m_bic,
                            w_bic=m_wbic,
                        ))
                        if len(top_models) >= 5:
                            break
                    except Exception:
                        pass

        # Generate Publication English Text
        en_text = (
            f"Multiple sequence alignment was conducted using {alignment_tool} (Katoh & Standley, 2013). "
            f"Unreliably aligned regions and excessive gaps were filtered using {trimming_tool} (Capella-Gutiérrez et al., 2009). "
            f"The dataset comprised {taxa} taxa with {sites} aligned positions ({parsimony_inf} parsimony-informative sites). "
            f"The optimal nucleotide/amino-acid substitution model was determined to be {best_model} using ModelFinder "
            f"(Kalyaanamoorthy et al., 2017) based on the Bayesian Information Criterion (BIC). "
            f"Maximum likelihood (ML) phylogenetic reconstruction was performed with IQ-TREE 2 (Minh et al., 2020). "
            f"Branch support was evaluated using 1,000 ultrafast bootstrap (UFBoot2) replicates (Hoang et al., 2018) "
            f"and 1,000 SH-like approximate likelihood ratio test (SH-aLRT) replicates (Guindon et al., 2010). "
            f"Nodes with UFBoot >= 95% and SH-aLRT >= 80% were considered strongly supported. "
            f"Tree visualization was performed in PhyloCraft."
        )

        # Generate Traditional Chinese Text
        zh_text = (
            f"本研究之多重序列比對採用 {alignment_tool} 進行對齊（Katoh & Standley, 2013）。"
            f"對齊後序列以 {trimming_tool} 過濾低保守度與高空缺（Gap）位點（Capella-Gutiérrez et al., 2009）。"
            f"最終分析矩陣共涵蓋 {taxa} 個分類群，總長度為 {sites} bp（包含 {parsimony_inf} 個簡約訊息位點）。"
            f"依據貝氏資訊標準（Bayesian Information Criterion, BIC），以 ModelFinder 檢驗挑選之最佳分子取代模式為 {best_model}（Kalyaanamoorthy et al., 2017）。"
            f"系統發育樹推論採用最大概似法（Maximum Likelihood, ML），以 IQ-TREE 2 進行建構（Minh et al., 2020），"
            f"分支可靠度檢驗採用 1,000 次極速拔靴複製法（Ultrafast Bootstrap, UFBoot2；Hoang et al., 2018）"
            f"與 1,000 次 SH-aLRT 檢驗（Guindon et al., 2010）。"
            f"一般以 UFBoot >= 95% 且 SH-aLRT >= 80% 視為高度可信分支。"
        )

        # Citations list
        citations = [
            "Minh, B. Q., Schmidt, H. A., Chernomor, O., Schrempf, D., Woodhams, M. D., von Haeseler, A., & Lanfear, R. (2020). IQ-TREE 2: new models and efficient methods for phylogenetic inference in the genomic era. Molecular Biology and Evolution, 37(5), 1530-1534.",
            "Kalyaanamoorthy, S., Minh, B. Q., Wong, T. K., von Haeseler, A., & Jermiin, L. S. (2017). ModelFinder: fast model selection for accurate phylogenetic estimates. Nature Methods, 14(6), 587-589.",
            "Hoang, D. T., Chernomor, O., von Haeseler, A., Minh, B. Q., & Vinh, L. S. (2018). UFBoot2: improving the ultrafast bootstrap approximation. Molecular Biology and Evolution, 35(2), 518-522.",
            "Katoh, K., & Standley, D. M. (2013). MAFFT multiple sequence alignment software version 7: improvements in performance and usability. Molecular Biology and Evolution, 30(4), 772-780.",
            "Capella-Gutiérrez, S., Silla-Martínez, J. M., & Gabaldón, T. (2009). trimAl: a tool for automated alignment trimming in large-scale phylogenetic analyses. Bioinformatics, 25(15), 1972-1973.",
        ]

        bibtex = r"""@article{minh2020iqtree,
  title={IQ-TREE 2: new models and efficient methods for phylogenetic inference in the genomic era},
  author={Minh, Bui Quang and Schmidt, Heiko A and Chernomor, Olga and Schrempf, Dominik and Woodhams, Michael D and von Haeseler, Arndt and Lanfear, Robert},
  journal={Molecular Biology and Evolution},
  volume={37},
  number={5},
  pages={1530--1534},
  year={2020},
  publisher={Oxford University Press}
}

@article{kalyaanamoorthy2017modelfinder,
  title={ModelFinder: fast model selection for accurate phylogenetic estimates},
  author={Kalyaanamoorthy, Subha and Minh, Bui Quang and Wong, Thomas KF and von Haeseler, Arndt and Jermiin, Lars S},
  journal={Nature Methods},
  volume={14},
  number={6},
  pages={587--589},
  year={2017},
  publisher={Nature Publishing Group}
}

@article{hoang2018ufboot2,
  title={UFBoot2: improving the ultrafast bootstrap approximation},
  author={Hoang, Diep Thi and Chernomor, Olga and von Haeseler, Arndt and Minh, Bui Quang and Vinh, Le Sy},
  journal={Molecular Biology and Evolution},
  volume={35},
  number={2},
  pages={518--522},
  year={2018},
  publisher={Oxford University Press}
}

@article{katoh2013mafft,
  title={MAFFT multiple sequence alignment software version 7: improvements in performance and usability},
  author={Katoh, Kazutaka and Standley, Daron M},
  journal={Molecular Biology and Evolution},
  volume={30},
  number={4},
  pages={772--780},
  year={2013},
  publisher={Oxford University Press}
}

@article{capella2009trimal,
  title={trimAl: a tool for automated alignment trimming in large-scale phylogenetic analyses},
  author={Capella-Guti{\'e}rrez, Salvador and Silla-Mart{\'\i}nez, Jos{\'e} M and Gabald{\'o}n, Toni},
  journal={Bioinformatics},
  volume={25},
  number={15},
  pages={1972--1973},
  year={2009},
  publisher={Oxford University Press}
}"""

        return IQTreeReportData(
            success=True,
            input_file=p.name,
            taxa_count=taxa,
            site_count=sites,
            constant_sites=const_sites,
            constant_pct=const_pct,
            parsimony_informative_sites=parsimony_inf,
            distinct_patterns=patterns,
            best_model=best_model,
            log_likelihood=logl,
            aic=aic,
            bic=bic,
            tree_length=tree_len,
            top_models=top_models,
            english_methods=en_text,
            chinese_methods=zh_text,
            citations=citations,
            bibtex=bibtex,
        )

    except Exception:
        return IQTreeReportData(success=False)
