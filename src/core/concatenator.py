import csv
from pathlib import Path
from dataclasses import dataclass, field
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq


@dataclass
class PartitionInfo:
    gene_name: str
    start: int  # 1-indexed
    end: int
    length: int
    taxa_count: int = 0
    total_taxa: int = 0
    completeness_pct: float = 100.0
    data_type: str = "DNA"


@dataclass
class ConcatResult:
    success: bool
    total_taxa: int = 0
    total_sites: int = 0
    overall_completeness: float = 100.0
    genes: list[PartitionInfo] = field(default_factory=list)
    output_fasta: str = ""
    output_partition: str = ""
    output_csv: str = ""
    missing_taxa_report: dict[str, list[str]] = field(default_factory=dict)
    message: str = ""


def concatenate_alignments(
    file_paths: list[str | Path],
    output_fasta_path: str | Path,
    output_partition_path: str | Path,
    partition_style: str = "iqtree",  # "iqtree", "nexus", "raxml"
    codon_partition: bool = False,
    fill_char: str = "?",
) -> ConcatResult:
    """
    Concatenates multiple aligned FASTA files into a single supermatrix,
    generates an associated partition file (IQ-TREE / RAxML format),
    and exports a gene occupancy & completeness matrix CSV.
    """
    if not file_paths:
        return ConcatResult(success=False, message="未選取任何待串聯之基因比對檔案。")

    # 1. Load all alignments
    gene_data: dict[str, dict[str, str]] = {}
    gene_lengths: dict[str, int] = {}
    ordered_gene_names: list[str] = []
    all_taxa: set[str] = set()

    for fp in file_paths:
        p = Path(fp)
        base_name = p.stem
        gene_name = base_name
        idx = 2
        while gene_name in gene_data:
            gene_name = f"{base_name}_{idx}"
            idx += 1
        ordered_gene_names.append(gene_name)

        try:
            with open(p, "r", encoding="utf-8", errors="replace") as handle:
                records = list(SeqIO.parse(handle, "fasta"))
        except Exception as e:
            return ConcatResult(success=False, message=f"檔案讀取失敗 ({p.name}): {str(e)}")

        if not records:
            return ConcatResult(success=False, message=f"檔案中未讀取到有效序列: {p.name}")

        # Check lengths within gene
        lengths = {len(r.seq) for r in records}
        if len(lengths) > 1:
            return ConcatResult(
                success=False,
                message=f"基因比對檔 '{p.name}' 尚未對齊！內部序列長度不一致: {lengths}",
            )

        gene_len = lengths.pop()
        gene_lengths[gene_name] = gene_len

        taxa_dict = {}
        for r in records:
            if r.id in taxa_dict:
                return ConcatResult(
                    success=False,
                    message=f"檔案 '{p.name}' 內含有重複物種標頭 '{r.id}'，請先使用「序列清洗防呆」模組進行標頭唯一化！",
                )
            taxa_dict[r.id] = str(r.seq)
            all_taxa.add(r.id)

        gene_data[gene_name] = taxa_dict

    sorted_taxa = sorted(all_taxa)
    sorted_genes = ordered_gene_names
    num_total_taxa = len(sorted_taxa)

    # 2. Build supermatrix and calculate occupancy
    supermatrix: dict[str, str] = {taxon: "" for taxon in sorted_taxa}
    missing_taxa_report: dict[str, list[str]] = {}
    partitions: list[PartitionInfo] = []

    total_matrix_cells = 0
    present_matrix_cells = 0

    current_pos = 1
    for gene_name in sorted_genes:
        length = gene_lengths[gene_name]
        start = current_pos
        end = current_pos + length - 1
        current_pos = end + 1

        missing_in_this_gene = []
        present_count = 0

        for taxon in sorted_taxa:
            seq = gene_data[gene_name].get(taxon)
            total_matrix_cells += length
            if seq is None:
                missing_in_this_gene.append(taxon)
                supermatrix[taxon] += fill_char * length
            else:
                present_count += 1
                # count non-gap characters
                non_gap = sum(1 for c in seq if c not in ("-", "?", "N", "n"))
                present_matrix_cells += non_gap
                supermatrix[taxon] += seq

        comp_pct = (present_count / num_total_taxa * 100) if num_total_taxa > 0 else 0.0

        partitions.append(
            PartitionInfo(
                gene_name=gene_name,
                start=start,
                end=end,
                length=length,
                taxa_count=present_count,
                total_taxa=num_total_taxa,
                completeness_pct=round(comp_pct, 1),
            )
        )

        if missing_in_this_gene:
            missing_taxa_report[gene_name] = missing_in_this_gene

    overall_comp = (
        (present_matrix_cells / total_matrix_cells * 100)
        if total_matrix_cells > 0
        else 100.0
    )

    # 3. Write concatenated FASTA
    out_fa = Path(output_fasta_path).resolve()
    out_fa.parent.mkdir(parents=True, exist_ok=True)
    records = [
        SeqRecord(Seq(seq), id=taxon, name=taxon, description="")
        for taxon, seq in supermatrix.items()
    ]
    with open(out_fa, "w", encoding="utf-8") as f:
        SeqIO.write(records, f, "fasta")

    # 4. Write Partition file
    out_part = Path(output_partition_path).resolve()
    out_part.parent.mkdir(parents=True, exist_ok=True)
    with open(out_part, "w", encoding="utf-8") as f:
        if partition_style == "nexus":
            f.write("#NEXUS\nBEGIN SETS;\n")
            for p in partitions:
                if codon_partition and p.length % 3 == 0:
                    f.write(f"  CHARSET {p.gene_name}_pos1 = {p.start}-{p.end}\\3;\n")
                    f.write(f"  CHARSET {p.gene_name}_pos2 = {p.start + 1}-{p.end}\\3;\n")
                    f.write(f"  CHARSET {p.gene_name}_pos3 = {p.start + 2}-{p.end}\\3;\n")
                else:
                    f.write(f"  CHARSET {p.gene_name} = {p.start}-{p.end};\n")
            f.write("END;\n")
        elif partition_style == "raxml":
            for p in partitions:
                if codon_partition and p.length % 3 == 0:
                    f.write(f"DNA, {p.gene_name}_pos1 = {p.start}-{p.end}\\3\n")
                    f.write(f"DNA, {p.gene_name}_pos2 = {p.start + 1}-{p.end}\\3\n")
                    f.write(f"DNA, {p.gene_name}_pos3 = {p.start + 2}-{p.end}\\3\n")
                else:
                    f.write(f"DNA, {p.gene_name} = {p.start}-{p.end}\n")
        else:
            # IQ-TREE NEXUS format (Recommended by IQ-TREE documentation)
            f.write("#nexus\nbegin sets;\n")
            for p in partitions:
                if codon_partition and p.length % 3 == 0:
                    f.write(f"  charset {p.gene_name}_1 = {p.start}-{p.end}\\3;\n")
                    f.write(f"  charset {p.gene_name}_2 = {p.start + 1}-{p.end}\\3;\n")
                    f.write(f"  charset {p.gene_name}_3 = {p.start + 2}-{p.end}\\3;\n")
                else:
                    f.write(f"  charset {p.gene_name} = {p.start}-{p.end};\n")
            f.write("end;\n")

    # 5. Write Gene Occupancy Matrix CSV
    out_csv = out_fa.with_suffix(".occupancy.csv")
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        header = ["Taxon_ID", "Completeness_Pct"] + sorted_genes
        writer.writerow(header)
        for taxon in sorted_taxa:
            gene_status = []
            present_gene_count = 0
            for g in sorted_genes:
                if taxon in gene_data[g]:
                    gene_status.append("Present")
                    present_gene_count += 1
                else:
                    gene_status.append("Missing")
            taxon_pct = round((present_gene_count / len(sorted_genes)) * 100, 1)
            writer.writerow([taxon, f"{taxon_pct}%"] + gene_status)

    return ConcatResult(
        success=True,
        total_taxa=len(sorted_taxa),
        total_sites=current_pos - 1,
        overall_completeness=round(overall_comp, 1),
        genes=partitions,
        output_fasta=str(out_fa),
        output_partition=str(out_part),
        output_csv=str(out_csv),
        missing_taxa_report=missing_taxa_report,
        message=f"已成功將 {len(sorted_genes)} 個基因串聯為 {len(sorted_taxa)} 物種超矩陣（總位點長度 {current_pos - 1} bp，整體完整度 {round(overall_comp, 1)}%）。",
    )
