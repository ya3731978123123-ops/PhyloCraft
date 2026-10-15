"""
Generate Side-by-Side Visual Comparisons: Original Literature Figures vs PhyloCraft Reconstructed Trees
"""

import sys
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE_DIR = Path(r"C:\Users\Alan\.gemini\antigravity\brain\b252e923-3bcb-4e1f-b6b5-41ade74e0f9b\screens\paper_trees")

def create_comparison_banner(img_left, img_right, title_left, title_right, header_text):
    # Resize to have same height
    target_h = 700
    w_l = int(img_left.width * target_h / img_left.height)
    left_resized = img_left.resize((w_l, target_h), Image.Resampling.LANCZOS)

    w_r = int(img_right.width * target_h / img_right.height)
    right_resized = img_right.resize((w_r, target_h), Image.Resampling.LANCZOS)

    header_h = 100
    banner_w = w_l + w_r + 40
    total_h = target_h + header_h + 40

    canvas = Image.new("RGB", (banner_w, total_h), "#ffffff")
    draw = ImageDraw.Draw(canvas)

    # Header background
    draw.rectangle([(0, 0), (banner_w, 60)], fill="#0f172a")
    # Subheaders
    draw.rectangle([(10, 65), (w_l + 10, 95)], fill="#f1f5f9", outline="#cbd5e1")
    draw.rectangle([(w_l + 30, 65), (banner_w - 10, 95)], fill="#eff6ff", outline="#93c5fd")

    # Paste images
    canvas.paste(left_resized, (10, header_h))
    canvas.paste(right_resized, (w_l + 30, header_h))

    # Borders
    draw.rectangle([(10, header_h), (w_l + 10, header_h + target_h)], outline="#cbd5e1", width=2)
    draw.rectangle([(w_l + 30, header_h), (banner_w - 10, header_h + target_h)], outline="#93c5fd", width=2)

    # Text
    draw.text((20, 18), header_text, fill="#ffffff")
    draw.text((20, 72), title_left, fill="#334155")
    draw.text((w_l + 40, 72), title_right, fill="#1d4ed8")

    return canvas

def build_comparisons():
    print("Building Side-by-Side Visual Comparison Gallery...")

    # 1. Nature 2020 Coronavirus
    nature_orig = Image.open(BASE_DIR / "nature_zhou2020_fig1.jpg")
    # Crop panel d (the tree part on the right side)
    # Original is ~685 wide, panel d starts around x=480
    w, h = nature_orig.size
    nature_tree = nature_orig.crop((int(w * 0.65), 0, w, h))
    phylocraft_corona = Image.open(BASE_DIR / "sarbecovirus_publication_tree.png")
    # Trim white margins of phylocraft tree
    comp1 = create_comparison_banner(
        nature_tree, phylocraft_corona,
        "Original: Nature 579, 270-273 (2020) Fig 1d (Zhou et al.)",
        "PhyloCraft: Reconstructed Tree from NCBI Authentic Sequences",
        "BENCHMARK 1: Coronavirus Evolution & SARS-CoV-2 (Nature IF: 50.5)"
    )
    comp1.save(BASE_DIR / "comparison_nature_sarbecovirus.png")
    print("  ✓ Saved comparison_nature_sarbecovirus.png")

    # 2. BMC Evol Biol 2008 Ursidae
    bmc_orig = Image.open(BASE_DIR / "krause2008_fig1.jpg")
    phylocraft_ursidae = Image.open(BASE_DIR / "ursidae_publication_tree.png")
    comp2 = create_comparison_banner(
        bmc_orig, phylocraft_ursidae,
        "Original: BMC Evol Biol 8, 220 (2008) Fig 1 (Krause et al.)",
        "PhyloCraft: Reconstructed Tree from NCBI Authentic Sequences",
        "BENCHMARK 2: Bear Family Adaptive Radiation & Giant Panda (BMC Evol Biol)"
    )
    comp2.save(BASE_DIR / "comparison_bmc_ursidae.png")
    print("  ✓ Saved comparison_bmc_ursidae.png")

    # 3. PLoS Genetics 2011 Primates
    plos_orig = Image.open(BASE_DIR / "perelman2011_fig1.jpg")
    # Crop top part showing Hominidae (Pan, Homo, Gorilla, Pongo, Macaca)
    w_p, h_p = plos_orig.size
    plos_tree = plos_orig.crop((int(w_p * 0.2), int(h_p * 0.0), int(w_p * 0.8), int(h_p * 0.5)))
    phylocraft_primates = Image.open(BASE_DIR / "primates_publication_tree.png")
    comp3 = create_comparison_banner(
        plos_tree, phylocraft_primates,
        "Original: PLoS Genet 7, e1001342 (2011) Fig 1 (Perelman et al.)",
        "PhyloCraft: Reconstructed Tree from NCBI Authentic Sequences",
        "BENCHMARK 3: Primate Phylogeny & Great Apes (PLoS Genetics IF: 5.5)"
    )
    comp3.save(BASE_DIR / "comparison_plos_primates.png")
    print("  ✓ Saved comparison_plos_primates.png")

    print("\n🎉 All 3 Side-by-Side Comparison Banners successfully generated!")

if __name__ == "__main__":
    build_comparisons()
