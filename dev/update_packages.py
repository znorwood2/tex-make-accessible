#!/usr/bin/env python3
"""Regenerate skills/tex-make-accessible/data/packages.json from the LaTeX
tagging project's status list.

Developer tool only (needs PyYAML). Usage:

    git clone --depth 1 https://github.com/latex3/tagging-project /tmp/tp
    python3 dev/update_packages.py /tmp/tp

The status list is maintained by the LaTeX Project at
https://github.com/latex3/tagging-project/blob/main/_data/tagging-status.yml
under the LaTeX Project Public License. This script keeps only the fields the
checker uses.
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

KEEP = ("status", "comments", "luatex-only", "supported-through", "updated")


def main() -> None:
    repo = Path(sys.argv[1])
    data = yaml.safe_load((repo / "_data" / "tagging-status.yml").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%H %cs"],
                            capture_output=True, text=True, check=True).stdout.split()
    out = {
        "source": {
            "url": "https://github.com/latex3/tagging-project/blob/main/_data/tagging-status.yml",
            "commit": commit[0],
            "date": commit[1],
            "licence": "LPPL 1.3c (The LaTeX Project); fields trimmed by dev/update_packages.py",
        },
        "package": {},
        "class": {},
    }
    for entry in data:
        kind = entry.get("type")
        if kind not in ("package", "class"):
            continue
        rec = {}
        for k in KEEP:
            if k in entry and entry[k] not in (None, ""):
                v = entry[k]
                if k == "comments":
                    v = " ".join(str(v).split())
                if k == "updated":
                    v = str(v)
                rec[k] = v
        out[kind][entry["name"]] = rec
        for sub in entry.get("subpackages") or []:
            out["package"].setdefault(sub, {"status": rec.get("status"), "comments": f"Part of {entry['name']}."})
    dest = Path(__file__).resolve().parents[1] / "skills" / "tex-make-accessible" / "data" / "packages.json"
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {dest}: {len(out['package'])} packages, {len(out['class'])} classes")


if __name__ == "__main__":
    main()
