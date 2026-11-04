"""Measure a render check for document.text: unexplained ink (DOC-1/DOC-12) and invisible text (DOC-9).

For each page: render it grayscale with pdftoppm, take word boxes from pdftotext -bbox, then
  - unexplained = dark pixels outside every word box (padded) / page pixels
  - hidden      = words whose box has no dark pixel inside it
Usage: python -I ink_measure.py OUT.json PDF...
"""
import json, os, re, subprocess, sys, tempfile, time

DPI, DARK, PAD = 50, 200, 2


def pgm(path):
    data = open(path, "rb").read()
    m = re.match(rb"P5\s+(\d+)\s+(\d+)\s+(\d+)\s", data)
    w, h = int(m.group(1)), int(m.group(2))
    return w, h, data[m.end():m.end() + w * h]


def measure(pdf):
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(["pdftoppm", "-gray", "-r", str(DPI), pdf, os.path.join(tmp, "p")],
                           capture_output=True, timeout=120)
        if r.returncode:
            return {"pdf": pdf, "error": f"pdftoppm {r.returncode}"}
        html = subprocess.run(["pdftotext", "-bbox", "-enc", "UTF-8", "-q", pdf, "-"], capture_output=True,
                              text=True, timeout=120).stdout
        pages = re.findall(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', html, re.S)
        images = sorted(f for f in os.listdir(tmp) if f.endswith(".pgm"))
        out = []
        for (pw, ph, body), img in zip(pages, images):
            w, h, px = pgm(os.path.join(tmp, img))
            sx, sy = w / float(pw), h / float(ph)
            mask = bytearray(w * h)
            hidden = 0
            words = re.findall(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)<', body)
            for x0, y0, x1, y1, _ in words:
                a, b = max(0, int(float(x0) * sx) - PAD), max(0, int(float(y0) * sy) - PAD)
                c, d = min(w, int(float(x1) * sx) + PAD + 1), min(h, int(float(y1) * sy) + PAD + 1)
                ink = False
                for y in range(b, d):
                    row = y * w
                    for x in range(a, c):
                        mask[row + x] = 1
                        if px[row + x] < DARK:
                            ink = True
                if not ink and c > a and d > b:
                    hidden += 1
            dark = sum(1 for i in range(w * h) if px[i] < DARK and not mask[i])
            out.append({"words": len(words), "hidden_words": hidden, "unexplained": round(dark / (w * h), 5)})
    return {"pdf": pdf, "pages": out, "seconds": round(time.perf_counter() - t0, 3)}


if __name__ == "__main__":
    json.dump([measure(p) for p in sys.argv[2:]], open(sys.argv[1], "w"), indent=1)
