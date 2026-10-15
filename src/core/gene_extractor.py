"""
Target Gene Extractor & Provenance Auditing Module (特定基因自動檢索與全透明溯源攫取器)
Extracts specific target genes (e.g. ETR1, CYTB, COX1, 16S, rbcL, Spike) from NCBI GenBank
or local GenBank (.gb/.gbk) files with 100% cryptographic provenance and audit trail.
"""

import io
import re
import csv
import time
import hashlib
import urllib.request
import urllib.parse
import json
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
import xml.etree.ElementTree as ET
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord


@dataclass
class ExtractedGeneRecord:
    accession: str
    organism: str
    gene_symbol: str
    product: str
    start: int
    end: int
    strand: int  # 1 for forward (+), -1 for reverse (-)
    seq_length: int
    sequence: str
    header: str
    ncbi_url: str = ""
    taxid: str = ""
    protein_id: str = ""
    translation: str = ""
    protein_length: int = 0
    sha256_hash: str = ""
    md5_hash: str = ""
    coordinates_str: str = ""
    retrieved_at: str = ""
    qc_status: str = ""


@dataclass
class GeneExtractionResult:
    success: bool
    total_requested: int = 0
    total_extracted: int = 0
    records: list[ExtractedGeneRecord] = field(default_factory=list)
    output_fasta: str = ""
    output_protein_fasta: str = ""
    output_csv: str = ""
    output_md: str = ""
    failed_accessions: list[tuple[str, str]] = field(default_factory=list)  # (acc_or_org, reason)
    message: str = ""
    qc_warnings: list[str] = field(default_factory=list)


class GeneExtractor:
    """
    Bioinformatics Target Gene Extractor with 100% Provenance & Traceability.
    Slices target CDS/rRNA coordinates from GenBank Feature Tables, computes SHA-256 digital hashes,
    and records clickable NCBI URLs to ensure reproducibility.
    """

    USER_AGENT = "PhyloCraft-GeneExtractor/2.0 (Academic Bioinformatics Research; mailto:admin@phylocraft.org)"

    ALIASES_MAP = {
        "CYTB": ["CYTOCHROME B", "COB", "CYB"],
        "COX1": ["COI", "CO1", "CYTOCHROME C OXIDASE SUBUNIT I", "CYTOCHROME C OXIDASE SUBUNIT 1"],
        "COX2": ["COII", "CO2", "CYTOCHROME C OXIDASE SUBUNIT II"],
        "COX3": ["COIII", "CO3", "CYTOCHROME C OXIDASE SUBUNIT III"],
        "ND1": ["NADH DEHYDROGENASE SUBUNIT 1", "MT-ND1"],
        "ND2": ["NADH DEHYDROGENASE SUBUNIT 2", "MT-ND2"],
        "ND4": ["NADH DEHYDROGENASE SUBUNIT 4", "MT-ND4"],
        "ND6": [
            "NADH DEHYDROGENASE SUBUNIT 6",
            "NADH-UBIQUINONE OXIDOREDUCTASE CHAIN 6",
            "MT-ND6",
            "ND6"
        ],
        "12S": ["12S RRNA", "12S RIBOSOMAL RNA", "RNR1"],
        "16S": ["16S RRNA", "16S RIBOSOMAL RNA", "RNR2", "18S RRNA", "18S RIBOSOMAL RNA", "SSU RRNA"],
        "18S": ["18S RRNA", "18S RIBOSOMAL RNA", "SSU RRNA", "16S RRNA", "16S RIBOSOMAL RNA"],
        "SSU": ["16S RRNA", "16S RIBOSOMAL RNA", "18S RRNA", "18S RIBOSOMAL RNA", "SSU RRNA", "SMALL SUBUNIT RIBOSOMAL RNA", "RNR2"],
        "28S": ["28S RRNA", "28S RIBOSOMAL RNA", "LSU RRNA"],
        "ITS": ["INTERNAL TRANSCRIBED SPACER", "ITS1", "ITS2"],
        "RBCL": ["RIBULOSE-1,5-BISPHOSPHATE CARBOXYLASE/OXYGENASE LARGE SUBUNIT", "RIBULOSE-1,5-BISPHOSPHATE CARBOXYLASE"],
        "MATK": ["MATURASE K"],
        "S": ["SPIKE", "SPIKE GLYCOPROTEIN", "SURFACE GLYCOPROTEIN"],
        "TP53": ["P53", "TUMOR PROTEIN P53", "CELLULAR TUMOR ANTIGEN P53", "TP53"],
        "P53": ["TP53", "TUMOR PROTEIN P53", "CELLULAR TUMOR ANTIGEN P53", "P53"],
        "GAPDH": ["GLYCERALDEHYDE-3-PHOSPHATE DEHYDROGENASE", "GAPD"],
        "ACTB": ["ACTIN BETA", "BETA-ACTIN"],
        "BRCA1": ["BREAST CANCER TYPE 1 SUSCEPTIBILITY PROTEIN"],
        "ETR1": [
            "ETHYLENE RECEPTOR 1",
            "ETHYLENE RECEPTOR ETR1",
            "HISTIDINE KINASE ETR1",
            "ETR1",
            "LEETR1",
            "SLETR1",
            "OSETR1"
        ],
        "ERS1": [
            "ETHYLENE RESPONSE SENSOR 1",
            "ETHYLENE RESPONSE SENSOR",
            "ERS1"
        ],
        "ETR2": [
            "ETHYLENE RECEPTOR 2",
            "ETR2",
            "OSETR2"
        ],
        "EIN4": [
            "ETHYLENE INSENSITIVE 4",
            "EIN4"
        ],
        "PSBA": ["PHOTOSYSTEM II PROTEIN D1", "PSBA"],
        "PSAA": ["PHOTOSYSTEM I PROTEIN A1", "PSAA"],
        "ATPB": ["ATP SYNTHASE SUBUNIT BETA", "ATPB"],
        "PHYA": ["PHYTOCHROME A", "PHYA"],
        "PHYB": ["PHYTOCHROME B", "PHYB"],
        "TIR1": ["TRANSPORT INHIBITOR RESPONSE 1", "TIR1"],
        "BRI1": ["BRASSINOSTEROID INSENSITIVE 1", "BRI1"],
        "CHS": ["CHALCONE SYNTHASE", "CHS"],
        "ANS": ["ANTHOCYANIDIN SYNTHASE", "ANS"],
        "PAL": ["PHENYLALANINE AMMONIA-LYASE", "PAL"],
        "MB": ["MYOGLOBIN", "MB"],
        "HBB": ["HEMOGLOBIN SUBUNIT BETA", "BETA-GLOBIN", "HBB"],
        "HBA1": ["HEMOGLOBIN SUBUNIT ALPHA 1", "ALPHA-GLOBIN", "HBA1"],
        "INS": ["INSULIN", "INS"],
        "ALB": ["ALBUMIN", "SERUM ALBUMIN", "ALB"],
        "LYZ": ["LYSOZYME", "LYZ"],
        "CYCS": ["CYTOCHROME C", "CYCS", "CYC"],
        "COL1A1": ["COLLAGEN TYPE I ALPHA 1 CHAIN", "COL1A1"],
        "FTH1": ["FERRITIN HEAVY CHAIN", "FTH1"],
        "SOD1": ["SUPEROXIDE DISMUTASE 1", "SOD1"],
        "CAT": ["CATALASE", "CAT"],
        "RB1": [
            "RB", "PRB", "P105-RB", "P110-RB1", "P105", "P110",
            "RETINOBLASTOMA", "RETINOBLASTOMA PROTEIN",
            "RB TRANSCRIPTIONAL COREPRESSOR 1", "RB1"
        ],
        "RB": [
            "RB1", "PRB", "P105-RB", "P110-RB1",
            "RETINOBLASTOMA", "RETINOBLASTOMA PROTEIN", "RB"
        ],
        "CDKN1A": ["P21", "CIP1", "WAF1", "CDKN1", "CDKN1A"],
        "P21": ["CDKN1A", "CIP1", "WAF1", "CDKN1", "P21"],
        "CDKN2A": ["P16", "INK4A", "CDKN2", "CDKN2A"],
        "P16": ["CDKN2A", "INK4A", "CDKN2", "P16"],
    }

    # Canonical Symbol Mapping for English aliases and informal names
    GENE_CANONICAL_MAP = {
        "P53": "TP53",
        "TP53": "TP53",
        "RB": "RB1",
        "RB1": "RB1",
        "PRB": "RB1",
        "P105-RB": "RB1",
        "P110-RB1": "RB1",
        "P21": "CDKN1A",
        "CDKN1A": "CDKN1A",
        "P16": "CDKN2A",
        "CDKN2A": "CDKN2A",
        "P27": "CDKN1B",
        "CDKN1B": "CDKN1B",
        "CO1": "COX1",
        "COI": "COX1",
        "CO2": "COX2",
        "COII": "COX2",
        "CO3": "COX3",
        "COIII": "COX3",
        "CYB": "CYTB",
        "COB": "CYTB",
        "RUBISCO": "RBCL",
        "SPIKE": "S",
        "MYOGLOBIN": "MB",
        "MB": "MB",
        "HEMOGLOBIN": "HBB",
        "HBB": "HBB",
        "BETA-GLOBIN": "HBB",
        "ALPHA-GLOBIN": "HBA1",
        "HBA1": "HBA1",
        "INSULIN": "INS",
        "INS": "INS",
        "ALBUMIN": "ALB",
        "ALB": "ALB",
        "LYSOZYME": "LYZ",
        "LYZ": "LYZ",
        "BETA-ACTIN": "ACTB",
        "ACTIN": "ACTB",
        "ACTB": "ACTB",
        "TUBULIN": "TUBB",
        "TUBB": "TUBB",
        "GAPD": "GAPDH",
        "GAPDH": "GAPDH",
        "CYTB": "CYTB",
        "COX1": "COX1",
        "COX2": "COX2",
        "COX3": "COX3",
        "RBCL": "RBCL",
        "MATK": "MATK",
        "CYCS": "CYCS",
        "ETR": "ETR1",
    }

    # Bilingual Mapping: Chinese Common Protein/Gene Names -> Standard Gene Symbol
    CHINESE_GENE_MAP = {
        # 植物荷爾蒙與感知蛋白
        "乙烯受體": "ETR1",
        "乙烯受體1": "ETR1",
        "乙烯受體2": "ETR2",
        "乙烯反應傳感器": "ERS1",
        "乙烯感知蛋白": "ETR1",
        "生長素受體": "TIR1",
        "赤黴素受體": "GID1",
        "脫落酸受體": "PYR1",
        "細胞分裂素受體": "CRE1",
        "油菜素內酯受體": "BRI1",
        "光敏色素": "PHYA",
        "隱花色素": "CRY1",

        # 葉綠體與光合作用核心蛋白
        "核酮糖二磷酸羧化酶": "RBCL",
        "核酮糖羧化酶": "RBCL",
        "核酮糖二磷酸羧化酶大亞基": "RBCL",
        "二磷酸核酮糖羧化酶": "RBCL",
        "二磷酸核酮糖羧化酶大亞基": "RBCL",
        "RUBISCO": "RBCL",
        "成熟酶": "MATK",
        "成熟酶K": "MATK",
        "光系統IID1": "PSBA",
        "光系統II蛋白D1": "PSBA",
        "PSBA": "PSBA",
        "光系統I蛋白": "PSAA",
        "ATP合成酶": "ATPB",
        "葉綠體ATP合成酶": "ATPB",
        "葉綠素結合蛋白": "LHCB",

        # 粒線體經典演化標記
        "細胞色素B": "CYTB",
        "細胞色素C氧化酶": "COX1",
        "細胞色素C氧化酶I": "COX1",
        "細胞色素C氧化酶1": "COX1",
        "細胞色素C氧化酶II": "COX2",
        "細胞色素C氧化酶III": "COX3",
        "NADH脫氫酶1": "ND1",
        "NADH脫氫酶2": "ND2",
        "NADH脫氫酶4": "ND4",
        "NADH脫氫酶6": "ND6",
        "12S核糖體RNA": "12S",
        "12S核糖體": "12S",
        "16S核糖體RNA": "16S",
        "16S核糖體": "16S",

        # 通用與管家蛋白
        "甘油醛-3-磷酸脫氫酶": "GAPDH",
        "甘油醛3磷酸脫氫酶": "GAPDH",
        "甘油醛磷酸脫氫酶": "GAPDH",
        "肌動蛋白": "ACTB",
        "微管蛋白": "TUBB",
        "微管蛋白A": "TUBA",
        "微管蛋白B": "TUBB",
        "熱休克蛋白": "HSP70",
        "熱休克蛋白70": "HSP70",
        "熱震蛋白": "HSP70",
        "過氧化物酶": "POD",
        "超氧化物歧化酶": "SOD",

        # 二次代謝與抗病
        "查爾酮合成酶": "CHS",
        "花青素合成酶": "ANS",
        "苯丙氨酸解氨酶": "PAL",

        # 真核核糖體與條形碼
        "18S核糖體RNA": "18S",
        "18S核糖體": "18S",
        "28S核糖體RNA": "28S",
        "28S核糖體": "28S",
        "ITS": "ITS",
        "內部轉錄間隔區": "ITS",

        # 病毒與醫學標的
        "刺突蛋白": "S",
        "刺突醣蛋白": "S",
        "S蛋白": "S",
        "腫瘤蛋白P53": "TP53",
        "腫瘤抑制蛋白P53": "TP53",
        "乳腺癌易感蛋白1": "BRCA1",

        # 經典動物、生理與醫學標靶蛋白
        "肌紅蛋白": "MB",
        "肌紅素": "MB",
        "血紅蛋白": "HBB",
        "血紅素": "HBB",
        "血紅蛋白A": "HBA1",
        "血紅蛋白B": "HBB",
        "胰島素": "INS",
        "白蛋白": "ALB",
        "清蛋白": "ALB",
        "血清白蛋白": "ALB",
        "膠原蛋白": "COL1A1",
        "溶菌酶": "LYZ",
        "細胞色素C": "CYCS",
        "肌球蛋白": "MYH",
        "鐵蛋白": "FTH1",
        "骨鈣素": "BGLAP",
        "催產素": "OXT",
        "瘦素": "LEP",
        "生長激素": "GH1",
    }

    # Chinese Vernacular Organism Names -> Latin Scientific Names (Traditional & Simplified)
    CHINESE_ORGANISM_MAP = {
        # 模式植物與農糧經濟作物
        "擬南芥": "Arabidopsis thaliana",
        "阿拉伯芥": "Arabidopsis thaliana",
        "水稻": "Oryza sativa",
        "稻米": "Oryza sativa",
        "番茄": "Solanum lycopersicum",
        "西紅柿": "Solanum lycopersicum",
        "玉米": "Zea mays",
        "包谷": "Zea mays",
        "小麥": "Triticum aestivum",
        "大麥": "Hordeum vulgare",
        "大豆": "Glycine max",
        "黃豆": "Glycine max",
        "菸草": "Nicotiana tabacum",
        "煙草": "Nicotiana tabacum",
        "毛果楊": "Populus trichocarpa",
        "楊樹": "Populus trichocarpa",
        "馬鈴薯": "Solanum tuberosum",
        "土豆": "Solanum tuberosum",
        "洋芋": "Solanum tuberosum",
        "棉花": "Gossypium hirsutum",
        "陸地棉": "Gossypium hirsutum",
        "茶樹": "Camellia sinensis",
        "茶": "Camellia sinensis",
        "油菜": "Brassica napus",
        "甘藍型油菜": "Brassica napus",
        "白菜": "Brassica rapa",
        "大白菜": "Brassica rapa",
        "高麗菜": "Brassica oleracea",
        "甘藍": "Brassica oleracea",
        "向日葵": "Helianthus annuus",
        "高粱": "Sorghum bicolor",
        "木薯": "Manihot esculenta",
        "甘薯": "Ipomoea batatas",
        "地瓜": "Ipomoea batatas",
        "番薯": "Ipomoea batatas",

        # 園藝果樹、林木與早期陸生植物
        "蘋果": "Malus domestica",
        "葡萄": "Vitis vinifera",
        "香蕉": "Musa acuminata",
        "柑橘": "Citrus sinensis",
        "甜橙": "Citrus sinensis",
        "西瓜": "Citrullus lanatus",
        "黃瓜": "Cucumis sativus",
        "辣椒": "Capsicum annuum",
        "茄子": "Solanum melongena",
        "草莓": "Fragaria vesca",
        "桃樹": "Prunus persica",
        "銀杏": "Ginkgo biloba",
        "蘇鐵": "Cycas revoluta",
        "紅豆杉": "Taxus wallichiana",
        "松樹": "Pinus sylvestris",
        "歐洲赤松": "Pinus sylvestris",
        "杉木": "Cunninghamia lanceolata",
        "苔蘚": "Physcomitrium patens",
        "小立碗蘚": "Physcomitrium patens",
        "卷柏": "Selaginella moellendorffii",
        "江南卷柏": "Selaginella moellendorffii",

        # 動物模式與演化經典
        "人": "Homo sapiens",
        "智人": "Homo sapiens",
        "人類": "Homo sapiens",
        "黑猩猩": "Pan troglodytes",
        "大猩猩": "Gorilla gorilla",
        "紅毛猩猩": "Pongo abelii",
        "北極熊": "Ursus maritimus",
        "棕熊": "Ursus arctos",
        "美洲黑熊": "Ursus americanus",
        "亞洲黑熊": "Ursus thibetanus",
        "大熊貓": "Ailuropoda melanoleuca",
        "熊貓": "Ailuropoda melanoleuca",
        "馬來熊": "Helarctos malayanus",
        "懶熊": "Melursus ursinus",
        "家犬": "Canis lupus familiaris",
        "小鼠": "Mus musculus",
        "大鼠": "Rattus norvegicus",
        "斑馬魚": "Danio rerio",
        "果蠅": "Drosophila melanogaster",
        "黑腹果蠅": "Drosophila melanogaster",
        "酵母": "Saccharomyces cerevisiae",
        "大腸桿菌": "Escherichia coli",

        # 高階演化群 / 門綱目科屬 (Clades & Higher Taxa)
        "節肢動物": "Arthropoda",
        "節肢動物門": "Arthropoda",
        "昆蟲": "Insecta",
        "昆蟲綱": "Insecta",
        "靈長類": "Primates",
        "靈長目": "Primates",
        "靈長動物": "Primates",
        "食肉目": "Carnivora",
        "食肉類": "Carnivora",
        "食肉動物": "Carnivora",
        "哺乳類": "Mammalia",
        "哺乳動物": "Mammalia",
        "哺乳綱": "Mammalia",
        "鳥類": "Aves",
        "鳥綱": "Aves",
        "硬骨魚": "Actinopterygii",
        "禾本科": "Poaceae",
        "十字花科": "Brassicaceae",
        "薔薇科": "Rosaceae",
        "茄科": "Solanaceae",
        "豆科": "Fabaceae",
        "熊科": "Ursidae",
        "貓科": "Felidae",
        "犬科": "Canidae",
        "人科": "Hominidae",
        "長臂猿科": "Hylobatidae",
        "猴科": "Cercopithecidae",
        "狐猴科": "Lemuridae",
        "鯨偶蹄目": "Cetartiodactyla",
        "偶蹄目": "Artiodactyla",
        "鯨目": "Cetacea",
        "囓齒目": "Rodentia",
        "齧齒目": "Rodentia",
        "齧齒動物": "Rodentia",
        "翼手目": "Chiroptera",
        "蝙蝠": "Chiroptera",
        "爬行類": "Reptilia",
        "爬行綱": "Reptilia",
        "兩棲類": "Amphibia",
        "兩棲綱": "Amphibia",
        "魚類": "Pisces",
        "被子植物": "Magnoliopsida",
        "裸子植物": "Acrogymnospermae",
        "真菌": "Fungi",
        "藻類": "Algae",
        "線蟲": "Nematoda",
        "軟體動物": "Mollusca",
        "環節動物": "Annelida",
        "扁形動物": "Platyhelminthes",
        "刺胞動物": "Cnidaria",
        "海綿動物": "Porifera",
        "脊椎動物": "Vertebrata",
        "脊索動物": "Chordata",
        "果蠅屬": "Drosophila",
    }

    # English Vernacular / Common Names -> Latin Scientific Names
    ENGLISH_ORGANISM_MAP = {
        "human": "Homo sapiens",
        "chimpanzee": "Pan troglodytes",
        "chimp": "Pan troglodytes",
        "gorilla": "Gorilla gorilla",
        "orangutan": "Pongo abelii",
        "macaque": "Macaca mulatta",
        "rhesus": "Macaca mulatta",
        "mouse": "Mus musculus",
        "rat": "Rattus norvegicus",
        "dog": "Canis lupus familiaris",
        "wolf": "Canis lupus",
        "cat": "Felis catus",
        "horse": "Equus caballus",
        "cattle": "Bos taurus",
        "cow": "Bos taurus",
        "bovine": "Bos taurus",
        "pig": "Sus scrofa",
        "swine": "Sus scrofa",
        "sheep": "Ovis aries",
        "goat": "Capra hircus",
        "whale": "Physeter macrocephalus",
        "sperm whale": "Physeter macrocephalus",
        "chicken": "Gallus gallus",
        "duck": "Anas platyrhynchos",
        "zebrafish": "Danio rerio",
        "frog": "Xenopus tropicalis",
        "fruit fly": "Drosophila melanogaster",
        "fruitfly": "Drosophila melanogaster",
        "nematode": "Caenorhabditis elegans",
        "yeast": "Saccharomyces cerevisiae",
        "arabidopsis": "Arabidopsis thaliana",
        "thale cress": "Arabidopsis thaliana",
        "rice": "Oryza sativa",
        "corn": "Zea mays",
        "maize": "Zea mays",
        "wheat": "Triticum aestivum",
        "barley": "Hordeum vulgare",
        "soybean": "Glycine max",
        "tomato": "Solanum lycopersicum",
        "potato": "Solanum tuberosum",
        "tobacco": "Nicotiana tabacum",
        "tea": "Camellia sinensis",
        "apple": "Malus domestica",
        "grape": "Vitis vinifera",
        "banana": "Musa acuminata",
        "ginkgo": "Ginkgo biloba",
        "cycad": "Cycas revoluta",
    }

    # High-confidence verified RefSeq Accessions for classic scientific benchmarks
    KNOWN_BENCHMARK_ACCESSIONS = {
        # ETR1 / 乙烯受體
        ("Arabidopsis thaliana", "ETR1"): "NM_105305.4",
        ("Solanum lycopersicum", "ETR1"): "NM_001247220.2",
        ("Oryza sativa", "ETR1"): "NM_001402333.1",
        ("Nicotiana tabacum", "ETR1"): "NM_001325388.1",
        ("Populus trichocarpa", "ETR1"): "XM_002311633.4",
        ("Glycine max", "ETR1"): "XM_003556299.5",
        ("Zea mays", "ETR1"): "NM_001155986.3",
        ("Triticum aestivum", "ETR1"): "XM_044547444.1",
        ("Solanum tuberosum", "ETR1"): "XM_006362141.2",
        ("Malus domestica", "ETR1"): "XM_008350711.3",

        # RBCL / 核酮糖二磷酸羧化酶
        ("Arabidopsis thaliana", "RBCL"): "NC_000932.1",
        ("Oryza sativa", "RBCL"): "NC_001320.1",
        ("Zea mays", "RBCL"): "NC_001666.2",
        ("Solanum lycopersicum", "RBCL"): "NC_007898.3",
        ("Nicotiana tabacum", "RBCL"): "NC_001879.2",
        ("Populus trichocarpa", "RBCL"): "NC_009949.1",
        ("Glycine max", "RBCL"): "NC_007942.1",
        ("Triticum aestivum", "RBCL"): "NC_002762.1",
        ("Camellia sinensis", "RBCL"): "NC_020019.1",
        ("Ginkgo biloba", "RBCL"): "NC_016986.1",
        ("Cycas revoluta", "RBCL"): "NC_020319.1",
        ("Physcomitrium patens", "RBCL"): "NC_005087.1",

        # MATK / 成熟酶 K
        ("Arabidopsis thaliana", "MATK"): "NC_000932.1",
        ("Oryza sativa", "MATK"): "NC_001320.1",
        ("Zea mays", "MATK"): "NC_001666.2",
        ("Solanum lycopersicum", "MATK"): "NC_007898.3",
        ("Camellia sinensis", "MATK"): "NC_020019.1",
        ("Ginkgo biloba", "MATK"): "NC_016986.1",

        # CYTB / 細胞色素 b
        ("Ursus maritimus", "CYTB"): "NC_003428.1",
        ("Ursus arctos", "CYTB"): "NC_003427.1",
        ("Ursus americanus", "CYTB"): "NC_003426.1",
        ("Ursus thibetanus", "CYTB"): "NC_009971.1",
        ("Helarctos malayanus", "CYTB"): "NC_009968.1",
        ("Melursus ursinus", "CYTB"): "NC_009970.1",
        ("Tremarctos ornatus", "CYTB"): "NC_009969.1",
        ("Ailuropoda melanoleuca", "CYTB"): "NC_009492.1",
        ("Homo sapiens", "CYTB"): "NC_012920.1",
        ("Pan troglodytes", "CYTB"): "NC_001643.1",
        ("Gorilla gorilla", "CYTB"): "NC_001645.1",
        ("Pongo abelii", "CYTB"): "NC_002083.1",
        ("Macaca mulatta", "CYTB"): "NC_005943.1",
        ("Lemur catta", "CYTB"): "NC_004025.1",

        # MB / 肌紅蛋白 (Nobel Prize & Physiology benchmark)
        ("Homo sapiens", "MB"): "NM_005368.3",
        ("Mus musculus", "MB"): "NM_013593.3",
        ("Rattus norvegicus", "MB"): "NM_021588.2",
        ("Equus caballus", "MB"): "NM_001081829.1",
        ("Physeter macrocephalus", "MB"): "XM_007111818.1",
        ("Canis lupus familiaris", "MB"): "NM_001003194.1",

        # HBB / 血紅蛋白 β 亞基
        ("Homo sapiens", "HBB"): "NM_000518.5",
        ("Mus musculus", "HBB"): "NM_001278161.1",
        ("Gorilla gorilla", "HBB"): "NM_001279262.1",

        # INS / 胰島素 (Classic vertebrate hormone evolution)
        ("Homo sapiens", "INS"): "NM_000207.3",
        ("Pan troglodytes", "INS"): "XM_016919751.2",
        ("Mus musculus", "INS"): "NM_008387.5",
        ("Rattus norvegicus", "INS"): "NM_019130.2",
        ("Sus scrofa", "INS"): "NM_001109772.1",
        ("Bos taurus", "INS"): "NM_001185126.1",
        ("Equus caballus", "INS"): "NM_001434734.1",
        ("Canis lupus familiaris", "INS"): "NM_001399719.1",
        ("Gallus gallus", "INS"): "NM_205222.1",
        ("Danio rerio", "INS"): "NM_131056.1",

        # TP53 / P53 (Classic tumor suppressor across model organisms)
        ("Homo sapiens", "TP53"): "NM_001407264.1",
        ("Homo sapiens", "P53"): "NM_001407264.1",
        ("Pan troglodytes", "TP53"): "XM_001172077.5",
        ("Pan troglodytes", "P53"): "XM_001172077.5",
        ("Gorilla gorilla", "TP53"): "XM_004058511.4",
        ("Gorilla gorilla", "P53"): "XM_004058511.4",
        ("Mus musculus", "TP53"): "NM_011640.3",
        ("Mus musculus", "P53"): "NM_011640.3",
        ("Rattus norvegicus", "TP53"): "NM_030989.3",
        ("Rattus norvegicus", "P53"): "NM_030989.3",
        ("Danio rerio", "TP53"): "NM_131327.2",
        ("Danio rerio", "P53"): "NM_131327.2",
        ("Drosophila melanogaster", "TP53"): "NM_079545.4",
        ("Drosophila melanogaster", "P53"): "NM_079545.4",
    }

    @classmethod
    def search_online_gene_synonyms_ncbi(cls, gene_input: str, timeout: int = 8) -> tuple[str, list[str]]:
        """
        Dynamically queries NCBI Entrez Gene database to discover the official gene symbol
        and standard aliases for ANY arbitrary, un-hardcoded gene symbol.
        Inspects top candidate IDs to avoid being shadowed by non-mammalian short acronym collisions.
        """
        clean = gene_input.strip()
        upper = clean.upper()
        if not clean:
            return clean, []
        try:
            url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gene&term={urllib.parse.quote(clean)}[Gene%20Name]&retmax=6&retmode=xml"
            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                tree = ET.fromstring(resp.read())
                ids = [e.text for e in tree.findall(".//IdList/Id")]
            if not ids:
                return upper, []
            url2 = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=gene&id={','.join(ids[:6])}&retmode=xml"
            req2 = urllib.request.Request(url2, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                st = ET.fromstring(resp2.read())

            discovered_symbols: set[str] = set()
            discovered_aliases: set[str] = set()
            for doc in st.findall(".//DocumentSummary"):
                name = doc.find("Name")
                aliases = doc.find("OtherAliases")
                sym = name.text.strip().upper() if name is not None and name.text else ""
                alias_list = [a.strip().upper() for a in aliases.text.split(",")] if aliases is not None and aliases.text else []

                # If user input matches official symbol or one of the aliases
                if upper == sym or upper in alias_list:
                    if sym:
                        discovered_symbols.add(sym)
                    for a in alias_list:
                        if len(a) <= 12:
                            discovered_aliases.add(a)

            primary = upper
            if discovered_symbols:
                def symbol_score(s: str) -> tuple:
                    is_exact = (s == upper)
                    is_clean = bool(re.match(r"^[A-Z][A-Z0-9]{1,7}$", s))
                    is_derived = (upper in s or s in upper)
                    return (is_exact, is_clean, is_derived, -len(s))

                cand_list = sorted(list(discovered_symbols), key=symbol_score, reverse=True)
                primary = cand_list[0]

            all_al = list(discovered_symbols | discovered_aliases)
            return primary, all_al
        except Exception:
            return upper, []

    @classmethod
    def canonicalize_gene_symbol(cls, gene_input: str) -> str:
        """
        Converts any gene input (Chinese common name, English alias, or informal symbol)
        into its official international standard gene symbol (e.g. 'P53' -> 'TP53', '乙烯受體' -> 'ETR1', 'Rb' -> 'RB1').
        """
        if not gene_input:
            return ""
        clean = gene_input.strip()
        if re.search(r"[\u4e00-\u9fff]", clean):
            zh_trans = cls.translate_chinese_gene(clean)
            if zh_trans:
                clean = zh_trans
        clean_upper = clean.upper()
        if clean_upper in cls.GENE_CANONICAL_MAP:
            return cls.GENE_CANONICAL_MAP[clean_upper]

        # Dynamic discovery via NCBI Gene for unknown/short symbols (e.g. 'Rb' -> 'RB1')
        off_sym, _ = cls.search_online_gene_synonyms_ncbi(clean_upper)
        if off_sym and off_sym != clean_upper:
            cls.GENE_CANONICAL_MAP[clean_upper] = off_sym
            return off_sym

        return clean_upper

    @classmethod
    def get_gene_aliases(cls, gene_symbol: str) -> list[str]:
        """
        Returns all synonymous gene symbols and product names for a given gene,
        supporting bidirectional lookups (e.g. P53 <-> TP53, CO1 <-> COX1).
        """
        canonical = cls.canonicalize_gene_symbol(gene_symbol)
        aliases: set[str] = set()
        if canonical:
            aliases.add(canonical)
        upper = gene_symbol.strip().upper()
        if upper:
            aliases.add(upper)

        for key, val_list in cls.ALIASES_MAP.items():
            if key == canonical or key == upper or canonical in val_list or upper in val_list:
                aliases.add(key)
                aliases.update(val_list)

        # Dynamic Tier: If no synonyms found in local dictionary, query NCBI Gene database live!
        if len(aliases) <= 1:
            off_sym, dynamic_aliases = cls.search_online_gene_synonyms_ncbi(upper)
            if off_sym and off_sym != upper:
                aliases.add(off_sym)
            for a in dynamic_aliases:
                aliases.add(a)

        return [a for a in aliases if a]

    @classmethod
    def translate_chinese_gene(cls, text: str) -> str:
        """
        Translates Chinese protein or gene names into standard international symbols.
        Supports exact match, keyword normalization, and dynamic online fallback (Wikidata P353).
        """
        if not text:
            return ""
        clean = re.sub(r"[\s\-_/]+", "", text.strip().upper())
        # 1. Exact match in map
        if clean in cls.CHINESE_GENE_MAP:
            return cls.CHINESE_GENE_MAP[clean]

        # 2. Only perform fuzzy matching if the input contains Chinese characters!
        if re.search(r"[\u4e00-\u9fff]", text):
            for zh_name, sym in cls.CHINESE_GENE_MAP.items():
                norm_zh = re.sub(r"[\s\-_/]+", "", zh_name).upper()
                if norm_zh in clean or clean in norm_zh:
                    return sym

            # Dynamic Tier 3: Query online biological database (Wikidata) for arbitrary Chinese gene/protein names
            online_sym = cls.search_online_gene_for_chinese(clean)
            if online_sym:
                cls.CHINESE_GENE_MAP[clean] = online_sym  # Cache for future lookups
                return online_sym

        return ""

    @classmethod
    def search_online_gene_for_chinese(cls, chinese_name: str, timeout: int = 8) -> str:
        """
        Dynamically resolves arbitrary Chinese protein or gene names to standard international
        gene symbols (e.g. HGNC / UniProt) using Wikidata entity search and P353 / P594 claims.
        """
        try:
            url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={urllib.parse.quote(chinese_name)}&language=zh&format=json&limit=4"
            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                results = data.get("search", [])
                for item in results:
                    qid = item.get("id")
                    if not qid:
                        continue
                    url_entity = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&props=claims|labels&languages=en&format=json"
                    req2 = urllib.request.Request(url_entity, headers={"User-Agent": cls.USER_AGENT})
                    with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                        edata = json.loads(resp2.read().decode("utf-8", errors="ignore"))
                        ent = edata.get("entities", {}).get(qid, {})
                        claims = ent.get("claims", {})

                        # 1. P353 = HGNC Gene Symbol (Gold standard for human/mammalian genes)
                        if "P353" in claims:
                            val = claims["P353"][0].get("mainsnak", {}).get("datavalue", {}).get("value", "")
                            if val:
                                return val.upper()

                        # 2. If English label is a canonical gene symbol (2-7 uppercase letters/numbers)
                        en_label = ent.get("labels", {}).get("en", {}).get("value", "")
                        if re.match(r"^[A-Z0-9]{2,7}$", en_label.strip()):
                            return en_label.strip()
        except Exception:
            pass
        return ""

    @classmethod
    def translate_chinese_organism(cls, text: str) -> str:
        """
        Translates Chinese or English common plant/animal names to standard Latin scientific names.
        Tier 1: High-speed local Chinese dictionary (0ms)
        Tier 2: High-speed local English common names dictionary (0ms)
        Tier 3: Fuzzy local match
        Tier 4: Dynamic online taxonomy fallback (Wikidata P225 scientific name API)
        """
        if not text:
            return ""
        clean = text.strip()
        # 1. Direct match in local Chinese dictionary
        if clean in cls.CHINESE_ORGANISM_MAP:
            return cls.CHINESE_ORGANISM_MAP[clean]

        # 2. Direct match in English common names dictionary
        lower_clean = clean.lower()
        if lower_clean in cls.ENGLISH_ORGANISM_MAP:
            return cls.ENGLISH_ORGANISM_MAP[lower_clean]

        # 3. Only perform fuzzy matching if the input contains Chinese characters
        if re.search(r"[\u4e00-\u9fff]", text):
            for zh_name, sci_name in cls.CHINESE_ORGANISM_MAP.items():
                if zh_name in clean or clean in zh_name:
                    return sci_name

            # Dynamic Tier 4: Query online biological taxonomy (Wikidata API) for rare/arbitrary species
            online_sci = cls.search_online_taxonomy_for_chinese(clean)
            if online_sci:
                cls.CHINESE_ORGANISM_MAP[clean] = online_sci  # Cache for future lookups
                return online_sci

        # 4. English fuzzy match
        for en_name, sci_name in cls.ENGLISH_ORGANISM_MAP.items():
            if en_name in lower_clean or lower_clean in en_name:
                return sci_name

        return ""

    @classmethod
    def search_online_taxonomy_for_chinese(cls, chinese_name: str, timeout: int = 8) -> str:
        """
        Dynamically resolves ANY arbitrary Chinese vernacular plant or animal name
        to its official Latin scientific name using Wikidata's open multilingual
        taxonomy database (P225 property). Ensures the system is NOT limited to hardcoded lists.
        """
        try:
            url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={urllib.parse.quote(chinese_name)}&language=zh&format=json&limit=2"
            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                results = data.get("search", [])
                for item in results:
                    qid = item.get("id")
                    if not qid:
                        continue
                    url_entity = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&props=claims&format=json"
                    req2 = urllib.request.Request(url_entity, headers={"User-Agent": cls.USER_AGENT})
                    with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                        edata = json.loads(resp2.read().decode("utf-8", errors="ignore"))
                        claims = edata.get("entities", {}).get(qid, {}).get("claims", {})
                        if "P225" in claims:  # P225 = Taxon Name / Scientific Name
                            taxon_val = claims["P225"][0].get("mainsnak", {}).get("datavalue", {}).get("value", "")
                            if taxon_val:
                                return taxon_val
        except Exception:
            pass
        return ""

    @classmethod
    def search_ncbi_accession_for_organism_gene(
        cls,
        organism_scientific: str,
        gene_symbol: str,
        timeout: int = 15,
    ) -> tuple[str, str] | None:
        """
        Finds the official RefSeq/GenBank accession for a given organism and gene.
        Checks high-confidence benchmark database first, then queries NCBI Entrez E-Utilities
        using a strict ortholog hierarchy (RefSeq Exact Symbol -> RefSeq Curated -> INSDC Complete CDS).
        Returns: (accession, title_description) or None.
        """
        clean_org = organism_scientific.strip()
        canonical_gene = cls.canonicalize_gene_symbol(gene_symbol)
        clean_gene = canonical_gene or gene_symbol.strip().upper()

        # Try to canonicalize Chinese gene if Chinese characters are present
        if re.search(r"[\u4e00-\u9fff]", clean_gene):
            translated = cls.translate_chinese_gene(clean_gene)
            if translated:
                clean_gene = translated.upper()
            else:
                return None

        # 1. Check known benchmark table (0ms, 100% verified)
        for g_candidate in [clean_gene, gene_symbol.strip().upper(), canonical_gene]:
            cache_key = (clean_org, g_candidate)
            if cache_key in cls.KNOWN_BENCHMARK_ACCESSIONS:
                return (cls.KNOWN_BENCHMARK_ACCESSIONS[cache_key], f"{clean_org} {g_candidate}")

        # 2. Live query to NCBI Entrez E-Search with Strict Ortholog Hierarchy
        try:
            # Query Tier 1: Exact gene symbol match (quoted) with RefSeq filter
            query_exact = f'{clean_org}[Organism] AND "{clean_gene}"[Gene] AND refseq[filter] NOT (pseudogene[All Fields] OR partial[Title])'
            url_esearch1 = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&term={urllib.parse.quote(query_exact)}&retmax=3&retmode=xml"
            req1 = urllib.request.Request(url_esearch1, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req1, timeout=timeout) as resp1:
                tree1 = ET.fromstring(resp1.read())
                uids = [elem.text for elem in tree1.findall(".//IdList/Id") if elem.text]

            # Query Tier 2: RefSeq mRNA with standard gene symbol / short aliases in [Gene]
            if not uids:
                aliases = cls.get_gene_aliases(clean_gene)
                short_aliases = [f'"{a}"[Gene]' for a in aliases if len(a) <= 8]
                alias_part = (" OR " + " OR ".join(short_aliases)) if short_aliases else ""
                query_mrna = f'{clean_org}[Organism] AND ({clean_gene}[Gene]{alias_part}) AND (biomol_mrna[prop] AND refseq[filter]) NOT (pseudogene[All Fields] OR partial[Title])'
                url_esearch2 = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&term={urllib.parse.quote(query_mrna)}&retmax=3&retmode=xml"
                req2 = urllib.request.Request(url_esearch2, headers={"User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                    tree2 = ET.fromstring(resp2.read())
                    uids = [elem.text for elem in tree2.findall(".//IdList/Id") if elem.text]

            # Query Tier 3: Complete RefSeq (e.g. chloroplast/mitochondria NC_ or predicted XM_)
            if not uids:
                query_broad = f'{clean_org}[Organism] AND {clean_gene}[Gene] AND refseq[filter] NOT (pseudogene[All Fields])'
                url_esearch3 = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&term={urllib.parse.quote(query_broad)}&retmax=3&retmode=xml"
                req3 = urllib.request.Request(url_esearch3, headers={"User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(req3, timeout=timeout) as resp3:
                    tree3 = ET.fromstring(resp3.read())
                    uids = [elem.text for elem in tree3.findall(".//IdList/Id") if elem.text]

            # Query Tier 4: INSDC Complete CDS fallback
            if not uids:
                query_insdc = f'{clean_org}[Organism] AND {clean_gene}[Gene] AND complete cds[Title] NOT (pseudogene[All Fields])'
                url_esearch4 = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&term={urllib.parse.quote(query_insdc)}&retmax=3&retmode=xml"
                req4 = urllib.request.Request(url_esearch4, headers={"User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(req4, timeout=timeout) as resp4:
                    tree4 = ET.fromstring(resp4.read())
                    uids = [elem.text for elem in tree4.findall(".//IdList/Id") if elem.text]

            if uids:
                top_uid = uids[0]
                url_sum = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=nuccore&id={top_uid}&retmode=xml"
                req_sum = urllib.request.Request(url_sum, headers={"User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(req_sum, timeout=timeout) as resp_sum:
                    sum_tree = ET.fromstring(resp_sum.read())
                    caption = sum_tree.find(".//DocSum/Item[@Name='Caption']")
                    title = sum_tree.find(".//DocSum/Item[@Name='Title']")
                    acc = caption.text.strip() if caption is not None and caption.text else ""
                    desc = title.text.strip() if title is not None and title.text else ""
                    if acc:
                        return (acc, desc)
        except Exception:
            pass

    @classmethod
    def search_ncbi_clade_multi_species(
        cls,
        organism_or_clade: str,
        gene_symbol: str,
        max_taxa: int = 8,
        refseq_only: bool = True,
        timeout: int = 15,
        query_reporter: Callable[[str], None] | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Explores diverse representative ortholog species across a higher taxonomic clade
        (e.g. Phylum Arthropoda, Order Primates, Family Ursidae) using TaxId deduplication.
        Returns: list of (accession, species_latin_name, full_title).
        """
        clean_org = organism_or_clade.strip()
        canonical_gene = cls.canonicalize_gene_symbol(gene_symbol)
        clean_gene = canonical_gene or gene_symbol.strip().upper()

        if re.search(r"[\u4e00-\u9fff]", clean_gene):
            translated = cls.translate_chinese_gene(clean_gene)
            if translated:
                clean_gene = translated.upper()
            else:
                return []

        # Gather all synonymous gene symbols and aliases
        aliases = cls.get_gene_aliases(clean_gene)
        short_symbols = list(dict.fromkeys([clean_gene, gene_symbol.strip().upper()] + [a for a in aliases if len(a) <= 10]))
        gene_parts = []
        for s in short_symbols:
            gene_parts.append(f'"{s}"[Gene]')
            gene_parts.append(f'{s}[Gene]')
        gene_term = f"({' OR '.join(gene_parts)})"

        # 1. Query NCBI Entrez for curated RefSeq mRNAs across the clade
        query = (
            f'{clean_org}[Organism] AND {gene_term} AND '
            f'(biomol_mrna[prop] AND refseq[filter]) '
            f'NOT (pseudogene[All Fields] OR partial[Title] OR UNVERIFIED[Title])'
        )
        if query_reporter:
            query_reporter(query)

        try:
            url_esearch = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&term={urllib.parse.quote(query)}&retmax=150&retmode=xml"
            req = urllib.request.Request(url_esearch, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                tree = ET.fromstring(resp.read())
                uids = [elem.text for elem in tree.findall(".//IdList/Id") if elem.text]

            # If no mRNA found (e.g. organelle gene like CYTB/rbcL), search general RefSeq
            if not uids:
                query_organelle = (
                    f'{clean_org}[Organism] AND {gene_term} AND refseq[filter] '
                    f'NOT (pseudogene[All Fields] OR partial[Title])'
                )
                if query_reporter:
                    query_reporter(query_organelle)
                url_esearch2 = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&term={urllib.parse.quote(query_organelle)}&retmax=150&retmode=xml"
                req2 = urllib.request.Request(url_esearch2, headers={"User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                    tree2 = ET.fromstring(resp2.read())
                    uids = [elem.text for elem in tree2.findall(".//IdList/Id") if elem.text]

            # Tier 3: Search Title / Protein Name fallback if standard [Gene] query returned empty
            # (mimics NCBI Automatic Term Mapping / EDirect term expansion)
            if not uids:
                title_candidates = [f'"{clean_gene}"[Title]', f'"{clean_gene}"[Protein Name]']
                for a in aliases:
                    if len(a) >= 4 and not a.startswith("LOC") and "\\" not in a:
                        title_candidates.append(f'"{a.lower()}"[Title]')
                title_term = " OR ".join(title_candidates[:6])
                query_title = (
                    f'{clean_org}[Organism] AND ({gene_term} OR {title_term}) '
                    f'AND refseq[filter] NOT (pseudogene[All Fields] OR partial[Title] OR UNVERIFIED[Title])'
                )
                if query_reporter:
                    query_reporter(query_title)
                url_esearch3 = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&term={urllib.parse.quote(query_title)}&retmax=150&retmode=xml"
                req3 = urllib.request.Request(url_esearch3, headers={"User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(req3, timeout=timeout) as resp3:
                    tree3 = ET.fromstring(resp3.read())
                    uids = [elem.text for elem in tree3.findall(".//IdList/Id") if elem.text]

            # Tier 4: Broad INSDC complete cds search if refseq_only is False or no RefSeq found
            if not uids and not refseq_only:
                title_candidates = [f'"{clean_gene}"[Title]', f'"{clean_gene}"[Protein Name]']
                for a in aliases:
                    if len(a) >= 4 and not a.startswith("LOC") and "\\" not in a:
                        title_candidates.append(f'"{a.lower()}"[Title]')
                title_term = " OR ".join(title_candidates[:6])
                query_insdc = (
                    f'{clean_org}[Organism] AND ({gene_term} OR {title_term}) '
                    f'AND complete cds[Title] NOT (pseudogene[All Fields] OR partial[Title])'
                )
                if query_reporter:
                    query_reporter(query_insdc)
                url_esearch4 = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nuccore&term={urllib.parse.quote(query_insdc)}&retmax=150&retmode=xml"
                req4 = urllib.request.Request(url_esearch4, headers={"User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(req4, timeout=timeout) as resp4:
                    tree4 = ET.fromstring(resp4.read())
                    uids = [elem.text for elem in tree4.findall(".//IdList/Id") if elem.text]

            distinct_species: list[tuple[str, str, str]] = []
            if uids:
                # 2. Fetch DocSums to perform distinct species sampling via TaxId
                sample_ids = uids[:100]
                url_sum = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=nuccore&id={','.join(sample_ids)}&retmode=xml"
                req_sum = urllib.request.Request(url_sum, headers={"User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(req_sum, timeout=timeout) as resp_sum:
                    sum_tree = ET.fromstring(resp_sum.read())

                seen_taxids: set[str] = set()

                for doc in sum_tree.findall(".//DocSum"):
                    acc, title, taxid = "", "", ""
                    for item in doc.findall(".//Item"):
                        n = item.get("Name")
                        if n == "Caption":
                            acc = item.text.strip() if item.text else ""
                        elif n == "Title":
                            title = item.text.strip() if item.text else ""
                        elif n == "TaxId":
                            taxid = item.text.strip() if item.text else ""

                    if not acc or not taxid:
                        continue

                    if taxid not in seen_taxids:
                        seen_taxids.add(taxid)
                        clean_title = re.sub(r"^(?:PREDICTED:\s*)?", "", title)
                        m = re.match(r"^([A-Z][a-z]+(?:\s+[a-z]+(?:\s+sp\.)?))", clean_title)
                        org = m.group(1).strip() if m else clean_title.split()[0]
                        distinct_species.append((acc, org, title))
                        if len(distinct_species) >= max_taxa:
                            break

            return distinct_species
        except Exception:
            return []

    @classmethod
    def resolve_taxa_to_accessions(
        cls,
        raw_input: str | list[str],
        target_gene: str,
        max_taxa_per_clade: int = 8,
        refseq_only: bool = True,
        progress_callback: Callable[[int, int, str], None] | None = None,
        query_reporter: Callable[[str], None] | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Resolves arbitrary taxa lines containing Chinese vernacular plant/organism names,
        Latin scientific names, or existing accessions into standardized:
        (accession, organism_display_name, formatted_editor_line).
        Supports Clade Multi-Species Expansion when higher taxa (e.g. Arthropoda, Primates) are entered.
        """
        canonical_gene = cls.canonicalize_gene_symbol(target_gene)
        if isinstance(raw_input, str):
            lines = raw_input.splitlines()
        else:
            lines = raw_input

        resolved_items: list[tuple[str, str, str]] = []
        total = len(lines)

        for idx, raw_line in enumerate(lines):
            line_str = str(raw_line).strip()
            if not line_str:
                continue

            # Strip comments
            line_content = re.split(r"(?:#|(?<!:)//)", line_str)[0].strip()
            if not line_content:
                continue

            if progress_callback:
                progress_callback(idx + 1, total, f"解析物種: {line_content[:20]}...")

            # 1. Check if line already contains an authentic Accession or URL
            parsed_accs = cls.parse_accessions(line_content)
            if parsed_accs:
                acc = parsed_accs[0]
                resolved_items.append((acc, "", line_str))
                continue

            # 2. Check if line is a Chinese vernacular plant or organism name
            org_latin = cls.translate_chinese_organism(line_content)
            org_display = line_content
            if not org_latin:
                # Check if already a Latin scientific name (e.g. 'Arabidopsis thaliana')
                if re.match(r"^[A-Z][a-z]+(\s+[a-z]+)?", line_content):
                    org_latin = line_content
                    org_display = line_content

            if org_latin:
                # A. First check if exact hit in known benchmarks (e.g. ("Homo sapiens", "MB"))
                matched_bench = None
                for g_cand in [canonical_gene, target_gene.strip().upper()]:
                    if (org_latin, g_cand) in cls.KNOWN_BENCHMARK_ACCESSIONS:
                        matched_bench = cls.KNOWN_BENCHMARK_ACCESSIONS[(org_latin, g_cand)]
                        break
                if matched_bench:
                    fmt_line = f"{matched_bench:<16} # {org_display} ({org_latin})"
                    resolved_items.append((matched_bench, org_display, fmt_line))
                    continue

                # B. Clade-wide multi-species search (detects if user entered a higher taxon like 'Arthropoda', 'Primates')
                clade_res = cls.search_ncbi_clade_multi_species(
                    org_latin,
                    canonical_gene,
                    max_taxa=max_taxa_per_clade,
                    refseq_only=refseq_only,
                    query_reporter=query_reporter,
                )
                if len(clade_res) > 1:
                    # Multi-species Clade Expansion!
                    for c_acc, c_sp, c_title in clade_res:
                        fmt_line = f"{c_acc:<16} # {c_sp} ({org_display})"
                        resolved_items.append((c_acc, c_sp, fmt_line))
                elif len(clade_res) == 1:
                    c_acc, c_sp, _ = clade_res[0]
                    fmt_line = f"{c_acc:<16} # {c_sp} ({org_display})"
                    resolved_items.append((c_acc, org_display, fmt_line))
                else:
                    search_res = cls.search_ncbi_accession_for_organism_gene(org_latin, canonical_gene)
                    if search_res:
                        acc, desc = search_res
                        fmt_line = f"{acc:<16} # {org_display} ({org_latin})"
                        resolved_items.append((acc, org_display, fmt_line))
                    else:
                        resolved_items.append(("", org_display, line_str))
            else:
                resolved_items.append(("", line_content, line_str))

        return resolved_items

    @classmethod
    def fetch_genbank_text(cls, accession_or_id: str) -> str:
        """
        Fetches full GenBank record with Feature Table from NCBI E-Utilities.
        Includes automatic version fallback (retries without .X if exact version returns 400).
        """
        clean_id = accession_or_id.strip()
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={clean_id}&rettype=gbwithparts&retmode=text"
        req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            if e.code == 400 and "." in clean_id:
                base_id = clean_id.split(".")[0]
                url_retry = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={base_id}&rettype=gbwithparts&retmode=text"
                req_retry = urllib.request.Request(url_retry, headers={"User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(req_retry, timeout=25) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
            raise

    @classmethod
    def extract_gene_from_record(
        cls,
        record: SeqRecord,
        target_gene: str,
        alias_patterns: list[str] | None = None,
    ) -> ExtractedGeneRecord | None:
        """
        Inspects Feature Table prioritizing actual coding sequences (CDS) for protein-coding genes,
        or rRNA for ribosomal genes, preventing gene boundary markers from shadowing real CDS.
        """
        target_norm = target_gene.strip().upper()
        canonical = cls.canonicalize_gene_symbol(target_gene)
        if canonical:
            target_norm = canonical

        patterns = list(dict.fromkeys(
            [target_norm, target_gene.strip().upper()] +
            cls.get_gene_aliases(target_norm) +
            ([p.strip().upper() for p in alias_patterns] if alias_patterns else [])
        ))

        org_name = record.annotations.get("organism", record.id)

        # TaxID extraction from source feature
        taxid = ""
        for feat in record.features:
            if feat.type == "source":
                for dbx in feat.qualifiers.get("db_xref", []):
                    if dbx.startswith("taxon:"):
                        taxid = dbx.replace("taxon:", "")
                        break
            if taxid:
                break

        # Prioritize CDS for coding genes, or rRNA for RNA genes
        is_rna_target = any(r in target_norm for r in ("16S", "18S", "SSU", "12S", "28S", "RRNA", "RNR"))
        if is_rna_target:
            primary_types = ("rRNA",)
            secondary_types = ("gene", "misc_RNA")
        else:
            primary_types = ("CDS",)
            secondary_types = ("gene", "mRNA")

        # Two-pass feature scanning
        for feature_group in (primary_types, secondary_types):
            for feat in record.features:
                if feat.type not in feature_group:
                    continue

                gene_val = feat.qualifiers.get("gene", [""])[0].upper()
                prod_val = feat.qualifiers.get("product", [""])[0].upper()
                syn_val = " ".join(feat.qualifiers.get("gene_synonym", [])).upper()
                note_val = feat.qualifiers.get("note", [""])[0].upper()

                matched = False
                for pat in patterns:
                    if pat == gene_val:
                        matched = True
                        break
                    # For short symbols (<= 3 chars, e.g. S, CO1), enforce word-boundary matching to prevent substring false-positives
                    if len(pat) <= 3:
                        if (re.search(r'\b' + re.escape(pat) + r'\b', syn_val) or
                            re.search(r'\b' + re.escape(pat) + r'\b', prod_val) or
                            re.search(r'\b' + re.escape(pat) + r'\b', note_val)):
                            matched = True
                            break
                    else:
                        if (pat in prod_val or
                            pat in syn_val or
                            pat in note_val):
                            matched = True
                            break

                # RefSeq mRNA single-CDS fallback: check definition title
                if not matched and feat.type == "CDS":
                    title_upper = (record.description or "").upper()
                    single_cds = len([f for f in record.features if f.type == "CDS"]) == 1
                    if single_cds:
                        for pat in patterns:
                            if len(pat) <= 3:
                                if (re.search(r'\b' + re.escape(pat) + r'\b', title_upper) or
                                    re.search(r'\b' + re.escape(pat) + r'\b', prod_val) or
                                    re.search(r'\b' + re.escape(pat) + r'\b', syn_val)):
                                    matched = True
                                    break
                            else:
                                if pat in title_upper or pat in prod_val or pat in syn_val:
                                    matched = True
                                    break

                if matched:
                    extracted_seq = str(feat.extract(record.seq))
                    clean_org = re.sub(r"[^a-zA-Z0-9_]", "_", org_name.strip()).replace("__", "_")

                    start_1 = int(feat.location.start) + 1
                    end_1 = int(feat.location.end)
                    strand_val = int(feat.location.strand) if feat.location.strand is not None else 1
                    strand_sym = "+" if strand_val == 1 else "-"
                    parts = getattr(feat.location, "parts", [])
                    if len(parts) > 1:
                        coord_str = f"{start_1}..{end_1} ({strand_sym}, {len(parts)} exons)"
                    else:
                        coord_str = f"{start_1}..{end_1} ({strand_sym})"

                    # Digital Checksums for verification
                    sha256 = hashlib.sha256(extracted_seq.encode("utf-8")).hexdigest()
                    md5 = hashlib.md5(extracted_seq.encode("utf-8")).hexdigest()

                    protein_id = feat.qualifiers.get("protein_id", [""])[0]
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Extract amino acid translation if CDS
                    trans_val = feat.qualifiers.get("translation", [""])[0]
                    if not trans_val and feat.type == "CDS" and extracted_seq:
                        try:
                            from Bio.Seq import Seq
                            table_id = feat.qualifiers.get("transl_table", [1])[0]
                            try:
                                table_id = int(table_id)
                            except Exception:
                                table_id = 1
                            trans_val = str(Seq(extracted_seq).translate(table=table_id, to_stop=False)).rstrip("*")
                        except Exception:
                            trans_val = ""

                    prot_len = len(trans_val) if trans_val else 0

                    # Traceable Header: >Organism|Accession:start-end(strand)|Gene
                    header = f"{clean_org}|{record.id}:{start_1}-{end_1}({strand_sym})|{target_norm}"
                    ncbi_url = f"https://www.ncbi.nlm.nih.gov/nuccore/{record.id}"

                    return ExtractedGeneRecord(
                        accession=record.id,
                        organism=org_name,
                        gene_symbol=gene_val or target_norm,
                        product=prod_val,
                        start=start_1,
                        end=end_1,
                        strand=strand_val,
                        seq_length=len(extracted_seq),
                        sequence=extracted_seq,
                        header=header,
                        ncbi_url=ncbi_url,
                        taxid=taxid,
                        protein_id=protein_id,
                        translation=trans_val,
                        protein_length=prot_len,
                        sha256_hash=sha256,
                        md5_hash=md5,
                        coordinates_str=coord_str,
                        retrieved_at=now_str,
                    )

        return None

    @classmethod
    def parse_accessions(cls, raw_input: str | list[str]) -> list[str]:
        """
        Robustly parses and cleans accession inputs from researchers:
        - Accepts newline, comma, semicolon, pipe, tab, or space-delimited text
        - Strips inline comments (#, //)
        - Automatically strips FASTA prefixes (>), brackets ([], (), {}), quotes
        - Automatically resolves and extracts accessions from full NCBI URLs (path or ?term= / ?id=)
        - Filters out database and navigation keywords (nuccore, nucleotide, protein, etc.)
        - De-duplicates while maintaining original input order
        - Validates against official INSDC/RefSeq accession standards or local GenBank file paths
        """
        if isinstance(raw_input, list):
            lines = raw_input
        else:
            lines = str(raw_input).splitlines()

        cleaned_targets = []
        seen = set()

        # Reserved non-accession keywords in URLs or web text
        db_keywords = {
            "nuccore", "nucleotide", "protein", "popset", "nucest", "nucgss",
            "efetch", "esearch", "entrez", "ncbi", "nih", "gov", "eutils", "index"
        }

        # Regex for authentic NCBI accessions: RefSeq, INSDC (1-letter, 2-letter), WGS, or GI digits
        acc_pattern = re.compile(r"^([A-Za-z]{1,6}_?\d+|[A-Za-z]{4,6}\d{8,12}|\d{5,})(\.\d+)?$")

        for raw_line in lines:
            line_str = str(raw_line)
            # Remove comments starting with # or // (not preceded by ':' to avoid splitting http:// or https://)
            line = re.split(r"(?:#|(?<!:)//)", line_str)[0].strip()
            if not line:
                continue

            # Tokenize by comma, semicolon, pipe, tab, or whitespace
            tokens = re.split(r"[,;\t| ]+", line)
            for tok in tokens:
                # Strip common wrappers: quotes, brackets, FASTA identifier marker >
                tok = tok.strip().strip("'\"`<>(){}[]").strip()
                if not tok:
                    continue

                # If token is a URL, extract accession from query params (?term=, ?id=) or URL path
                if tok.startswith("http://") or tok.startswith("https://"):
                    try:
                        parsed_url = urllib.parse.urlparse(tok)
                        query_params = urllib.parse.parse_qs(parsed_url.query)
                        candidate = None
                        if "term" in query_params and query_params["term"]:
                            candidate = query_params["term"][0]
                        elif "id" in query_params and query_params["id"]:
                            candidate = query_params["id"][0]
                        elif "val" in query_params and query_params["val"]:
                            candidate = query_params["val"][0]

                        if not candidate:
                            path_parts = [p.strip() for p in parsed_url.path.split("/") if p.strip()]
                            for part in reversed(path_parts):
                                if part.lower() not in db_keywords:
                                    candidate = part
                                    break

                        if candidate:
                            tok = candidate
                    except Exception:
                        pass

                # Strip query parameters and wrappers if any remain
                tok = tok.split("?")[0].strip()
                tok = tok.strip("'\"`<>(){}[]").strip()

                if not tok or tok.lower() in db_keywords:
                    continue

                # Check for local file path (.gb, .gbk, .genbank) or authentic NCBI Accession
                is_local = Path(tok).suffix.lower() in [".gb", ".gbk", ".genbank"] or Path(tok).exists()
                is_acc = bool(acc_pattern.match(tok)) and 3 <= len(tok) <= 35

                if is_local or is_acc:
                    if tok not in seen:
                        seen.add(tok)
                        cleaned_targets.append(tok)

        return cleaned_targets

    def extract_target_genes(
        self,
        targets: list[str],
        target_gene: str,
        output_fasta: Path | str,
        sequence_type: str = "cds",  # "cds", "protein", "both"
        max_taxa_per_clade: int = 8,
        refseq_only: bool = True,
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        query_reporter: Callable[[str], None] | None = None,
    ) -> GeneExtractionResult:
        """
        Batch extracts target genes from NCBI or local files with full provenance export.
        Supports CDS, translated protein (AA), or both, with customizable clade sampling and RefSeq filters.
        """
        output_p = Path(output_fasta).resolve()
        output_p.parent.mkdir(parents=True, exist_ok=True)

        clean_targets = self.parse_accessions(targets)
        extracted_records: list[ExtractedGeneRecord] = []
        failed: list[tuple[str, str]] = []

        if not clean_targets and targets:
            # Fallback: Check if targets contain Chinese vernacular plant/organism names or Latin names
            resolved_tuples = self.resolve_taxa_to_accessions(
                targets,
                target_gene,
                max_taxa_per_clade=max_taxa_per_clade,
                refseq_only=refseq_only,
                progress_callback=lambda c, t, m: progress_callback(c, t, m) if progress_callback else None,
                query_reporter=query_reporter,
            )
            clean_targets = [acc for acc, _, _ in resolved_tuples if acc]

        if not clean_targets and targets:
            acc_str = ", ".join(targets) if isinstance(targets, list) else str(targets)
            failed.append((acc_str, "無法解析為有效之 NCBI 登錄號或物種名稱 (需符合 RefSeq/INSDC 標準或本機檔案)"))
            return GeneExtractionResult(
                success=False,
                total_requested=len(targets) if isinstance(targets, list) else 1,
                total_extracted=0,
                failed_accessions=failed,
                message="未解析到任何有效之 NCBI 登錄號或已知物種名稱，請確認輸入內容。",
            )

        total = len(clean_targets)
        for idx, item_str in enumerate(clean_targets):
            if cancel_check and cancel_check():
                failed.append(("CANCELLED", "使用者主動中斷擷取流程"))
                break

            if progress_callback:
                progress_callback(idx + 1, total, f"正在檢索特徵表: {item_str}...")

            rec = None
            try:
                local_p = Path(item_str)
                if local_p.exists() and local_p.is_file():
                    with open(local_p, "r", encoding="utf-8", errors="ignore") as handle:
                        rec = SeqIO.read(handle, "genbank")
                else:
                    gb_text = self.fetch_genbank_text(item_str)
                    rec = SeqIO.read(io.StringIO(gb_text), "genbank")

                if rec:
                    extracted = self.extract_gene_from_record(rec, target_gene)
                    if extracted:
                        extracted_records.append(extracted)
                    else:
                        failed.append((item_str, f"特徵表 (Feature Table) 中未標註符合 '{target_gene}' 之 CDS/rRNA"))
                else:
                    failed.append((item_str, "無法解析 GenBank 格式"))
            except Exception as e:
                failed.append((item_str, f"連線或擷取例外: {str(e)}"))

            # Polite rate-limiting delay between NCBI calls (3 requests/sec max)
            if idx + 1 < total and not Path(item_str).exists():
                time.sleep(0.34)

        # 1. Save FASTA according to sequence_type
        prot_path_str = ""
        if extracted_records:
            if sequence_type in ("cds", "both"):
                with open(output_p, "w", encoding="utf-8") as f:
                    for r in extracted_records:
                        f.write(f">{r.header}\n{r.sequence}\n")

            if sequence_type in ("protein", "both"):
                p_target = output_p if sequence_type == "protein" else output_p.with_name(f"{output_p.stem}_protein.fasta")
                prot_path_str = str(p_target)
                with open(p_target, "w", encoding="utf-8") as f:
                    for r in extracted_records:
                        aa_seq = r.translation
                        if not aa_seq and r.sequence:
                            try:
                                from Bio.Seq import Seq
                                aa_seq = str(Seq(r.sequence).translate(to_stop=False)).rstrip("*")
                            except Exception:
                                aa_seq = ""
                        f.write(f">{r.header}|AA_len={len(aa_seq)}\n{aa_seq}\n")

        # 2. Quality Control: Homology & Length Discrepancy Check (Paralog / Domain truncation detection)
        length_warnings: list[str] = []
        if len(extracted_records) >= 3:
            lengths = [r.seq_length for r in extracted_records]
            lengths.sort()
            median_len = lengths[len(lengths) // 2]
            for r in extracted_records:
                diff_ratio = abs(r.seq_length - median_len) / median_len if median_len > 0 else 0
                if diff_ratio > 0.15:
                    status = f"過長 (+{int(diff_ratio*100)}%)" if r.seq_length > median_len else f"過短 (-{int(diff_ratio*100)}%)"
                    r.qc_status = f"⚠️ 疑似長度離群 ({status})"
                    length_warnings.append(
                        f"⚠️ {r.organism} ({r.seq_length} bp vs 中位數 {median_len} bp, {status}): 疑似混入旁系同源基因 (Paralog)、非同源前導序列或結構域缺失！"
                    )
                else:
                    r.qc_status = "正常 (Passed)"
        elif extracted_records:
            for r in extracted_records:
                r.qc_status = "正常 (Passed)"

        # 3. Save Traceability CSV
        csv_path = output_p.with_suffix(".provenance.csv")
        self.export_provenance_csv(extracted_records, csv_path)

        # 4. Save Traceability Markdown
        md_path = output_p.with_suffix(".provenance.md")
        self.export_provenance_markdown(extracted_records, md_path, target_gene)

        success = len(extracted_records) > 0
        msg = f"成功擷取 {len(extracted_records)}/{total} 筆特定基因序列 ({target_gene})。"
        if failed:
            msg += f" {len(failed)} 筆未擷取成功。"
        if length_warnings:
            msg += f"\n⚠️ [演化品管警示] 發現 {len(length_warnings)} 筆序列長度與中位數偏差 >15%，疑似混入旁系同源基因 (Paralog) 或缺失結構域，請檢查審計報告或使用 trimAl 修剪。"

        return GeneExtractionResult(
            success=success,
            total_requested=total,
            total_extracted=len(extracted_records),
            records=extracted_records,
            output_fasta=str(output_p) if success and sequence_type != "protein" else (prot_path_str if success else ""),
            output_protein_fasta=prot_path_str if success else "",
            output_csv=str(csv_path) if success else "",
            output_md=str(md_path) if success else "",
            failed_accessions=failed,
            message=msg,
            qc_warnings=length_warnings,
        )

    @classmethod
    def export_provenance_csv(cls, records: list[ExtractedGeneRecord], csv_path: Path | str):
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "物種學名 (Scientific Name)",
                "NCBI 登錄號 (Accession)",
                "基因代號 (Gene)",
                "產品名稱 (Product)",
                "染色體/基因組座標 (Coordinates)",
                "股向 (Strand)",
                "核酸長度 (bp)",
                "蛋白質長度 (aa)",
                "品管狀態 (QC Status)",
                "蛋白質 ID (Protein ID)",
                "TaxID",
                "SHA-256 數位指紋 (Checksum)",
                "NCBI 官方檢驗連結 (Direct URL)",
                "擷取時間 (Timestamp)"
            ])
            for r in records:
                writer.writerow([
                    r.organism,
                    r.accession,
                    r.gene_symbol,
                    r.product,
                    f"{r.start}..{r.end}",
                    "+" if r.strand == 1 else "-",
                    r.seq_length,
                    r.protein_length,
                    r.qc_status or "正常 (Passed)",
                    r.protein_id,
                    r.taxid,
                    r.sha256_hash,
                    r.ncbi_url,
                    r.retrieved_at
                ])

    @classmethod
    def export_provenance_markdown(cls, records: list[ExtractedGeneRecord], md_path: Path | str, target_gene: str):
        lines = [
            f"# 🧬 基因擷取可溯源審計清單 (Gene Provenance & Traceability Audit)",
            f"**目標基因標的**：`{target_gene}` ｜ **產出時間**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ｜ **總筆數**：{len(records)} 筆\n",
            f"> [!IMPORTANT]",
            f"> 本清單記錄每條序列於 NCBI GenBank 官方資料庫中的原始座標、特徵表位置及 SHA-256 數位指紋，任何研究者皆可點擊連結逐一複驗溯源，消除黑箱序列疑慮。\n",
        ]

        qc_alerts = [r for r in records if "⚠️" in (r.qc_status or "")]
        if qc_alerts:
            lines.append("> [!WARNING]")
            lines.append("> **直系同源長度品管警示 (Orthology & Length Discrepancy QC)**:")
            lines.append("> 系統檢測到下列序列之長度與群體中位數差異超過 15%，強烈建議檢查是否混入旁系同源基因（如 ETR1 混入 ERS1）或非同源前導序列：")
            for r in qc_alerts:
                lines.append(f"> - **{r.organism}** (`{r.accession}`): {r.seq_length} bp — {r.qc_status}")
            lines.append("")

        lines.extend([
            f"| 物種學名 | NCBI 登錄號 | 座標範圍 | 核酸 (bp) | 蛋白 (aa) | 品管狀態 | 蛋白質 ID | SHA-256 數位指紋 (前12碼) | 官方檢驗連結 |",
            f"| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        ])
        for r in records:
            link_md = f"[{r.accession}]({r.ncbi_url})"
            qc_badge = r.qc_status if r.qc_status else "正常"
            lines.append(
                f"| *{r.organism}* | {link_md} | `{r.coordinates_str}` | {r.seq_length} | {r.protein_length or 'N/A'} | {qc_badge} | `{r.protein_id or 'N/A'}` | `{r.sha256_hash[:12]}...` | [查閱 GenBank]({r.ncbi_url}) |"
            )
        lines.append("\n---\n*Report generated automatically by PhyloCraft Gene Extractor.*")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
