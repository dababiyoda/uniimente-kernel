"""Rebuild ``sndlib_networks.json.gz`` from its public source (candidate natural family F7, graph -> allocate).

Source: the SNDlib 1.0 networks (Orlowski, Wessaely, Pioro, Tomaszewski, "SNDlib 1.0 - Survivable Network
Design Library", Networks 55:276-286, 2010) as converted and bundled by TopoHub 1.5.1 (MIT licence;
https://pypi.org/project/topohub/). Per network TopoHub keeps the real node set with coordinates, the real
links, each link's length (haversine, km), the real demand matrix and the link loads under ECMP shortest-path
routing of that demand (normalised so the busiest link is 100). SNDlib's own pre-installed capacities and
module costs are not in TopoHub and are not reachable from this environment; a family built on this file
declares how it derives capacities and costs.

Terms: TopoHub's code is MIT. SNDlib publishes no open licence; its site states that access is unrestricted
and that the data is meant for research purposes only, and asks users to cite the paper above. This extract is
used for evaluation only (no product or commercial use); redistribution beyond research is a founder decision.

This script reads the TopoHub wheel, checks its sha256, and keeps only what a family needs: per network the
nodes, every link with its length and both directional ECMP loads, and the 20 largest demand pairs.
Networks above the flow genomes' node limit (``brain``, 161 nodes) are left out.

Usage (the output is committed, so evaluation never downloads):

    pip download --no-deps topohub==1.5.1 -d /some/dir
    python -I cortex/evaluation/data/build_sndlib_networks.py /some/dir/topohub-1.5.1-py3-none-any.whl
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sys
import zipfile

SOURCE = "topohub 1.5.1 wheel (PyPI), data/sndlib/*.json"
SOURCE_SHA256 = "331dd0dab419ede67d5a680b724795d2320fb7f45bd8f2cf2281f155a117cdbb"
OUT = Path(__file__).resolve().parent / "sndlib_networks.json.gz"
MAX_NODES = 120                       # greg/cognition/genomes/flow.py MAX_NODES
TOP_DEMANDS = 20


def build(wheel: Path) -> dict:
    raw = wheel.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise SystemExit(f"source sha256 {digest} differs from the recorded {SOURCE_SHA256}")
    networks = {}
    with zipfile.ZipFile(wheel) as zf:
        for name in sorted(n for n in zf.namelist() if n.startswith("topohub/data/sndlib/") and n.endswith(".json")):
            body = zf.read(name)
            topo = json.loads(body)
            if len(topo["nodes"]) > MAX_NODES:
                continue
            key = Path(name).stem
            names = {n["id"]: n["name"] for n in topo["nodes"]}
            links = []
            for e in topo["edges"]:
                fwd, bwd = e.get("ecmp_fwd", {}).get("org"), e.get("ecmp_bwd", {}).get("org")
                if fwd is None or bwd is None:
                    raise SystemExit(f"{key}: a link without ECMP loads")
                links.append([names[e["source"]], names[e["target"]], round(float(e["dist"]), 2),
                              round(float(fwd), 2), round(float(bwd), 2)])
            pairs = [(float(v), names[int(s)], names[int(t)])
                     for s, row in topo["graph"]["demands"].items() for t, v in row.items() if int(s) != int(t)]
            pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
            networks[key] = {"nodes": sorted(names.values()), "links": links,
                             "top_demands": [[s, t, round(v, 4)] for v, s, t in pairs[:TOP_DEMANDS]],
                             "demand_pairs": len(pairs), "file_sha256": hashlib.sha256(body).hexdigest()}
    return {"source": SOURCE, "source_sha256": SOURCE_SHA256, "licence": "TopoHub conversion MIT; SNDlib data: "
            "research use only, no open licence; cite Orlowski et al. 2010", "link_fields": ["u", "v", "km", "ecmp_load_u_to_v", "ecmp_load_v_to_u"],
            "networks": networks}


def main(argv):
    if len(argv) != 1:
        raise SystemExit(__doc__)
    data = build(Path(argv[0]))
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    with open(OUT, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
            gz.write(blob)
    print(json.dumps({"out": str(OUT), "networks": len(data["networks"]),
                      "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main(sys.argv[1:])
