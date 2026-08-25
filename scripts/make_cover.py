"""Generate podcast cover art without image libraries.

Hand-writes a minimal PDF (base-14 Helvetica, no embedding needed), then lets
macOS `sips` rasterise it. Apple Podcasts requires square art of at least
1400x1400, so the page is laid out at 1600pt and rendered 1:1.
"""

import subprocess
import sys
from pathlib import Path

SIZE = 1600
BG = (0.043, 0.075, 0.145)      # deep navy
ACCENT = (0.180, 0.788, 0.647)  # teal pulse
WHITE = (1, 1, 1)
MUTED = (0.62, 0.68, 0.78)


def esc(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def centred(text: str, font: str, size: float, y: float, rgb) -> str:
    # Helvetica average advance ~0.55em; good enough to centre a short title.
    width = len(text) * size * 0.55
    x = (SIZE - width) / 2
    r, g, b = rgb
    return (
        f"BT /{font} {size} Tf {r} {g} {b} rg "
        f"1 0 0 1 {x:.1f} {y:.1f} Tm ({esc(text)}) Tj ET\n"
    )


def build_content() -> str:
    r, g, b = BG
    ops = [f"{r} {g} {b} rg 0 0 {SIZE} {SIZE} re f\n"]

    # Pulse line across the middle — a stylised ECG/market tick.
    ar, ag, ab = ACCENT
    ops.append(f"{ar} {ag} {ab} RG 18 w 1 J 1 j\n")
    baseline = 1080
    pts = [(180, baseline), (430, baseline), (520, baseline + 150),
           (610, baseline - 190), (700, baseline + 90), (790, baseline),
           (1420, baseline)]
    ops.append(f"{pts[0][0]} {pts[0][1]} m\n")
    ops.extend(f"{x} {y} l\n" for x, y in pts[1:])
    ops.append("S\n")

    ops.append(centred("FINTECH", "F1", 210, 640, WHITE))
    ops.append(centred("PULSE", "F1", 210, 430, ACCENT))
    ops.append(centred("DAILY BRIEFING", "F2", 62, 300, MUTED))
    return "".join(ops)


def build_pdf() -> bytes:
    content = build_content().encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {SIZE} {SIZE}] "
         f"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> "
         f"/Contents 4 0 R >>").encode("latin-1"),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
        + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


if __name__ == "__main__":
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "cover.jpg")
    pdf = dest.with_suffix(".pdf")
    pdf.write_bytes(build_pdf())

    subprocess.run(
        ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90",
         "-z", str(SIZE), str(SIZE), str(pdf), "--out", str(dest)],
        check=True, capture_output=True,
    )
    pdf.unlink()
    print(f"wrote {dest}")
