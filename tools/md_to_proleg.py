#!/usr/bin/env python3
"""Generate a PROLEG skeleton from one houritsu law markdown file.

The skeleton has one block per article (条). Each block records where the
article comes from and leaves the rule (要件と効果) for a person to write.
The article text is not copied into the .pl file; read it in the .md file.

Usage:
    python3 tools/md_to_proleg.py laws/act/129/129AC0000000089.md proleg/act/129/129AC0000000089.pl
"""

import re
import sys
from pathlib import Path

ARTICLE_HEADING = re.compile(r"^#{2,6}\s+(第[^\s（]+条)(?:（([^）]*)）)?\s*$")
TOP_HEADING = re.compile(r"^##\s+(.+?)\s*$")
FRONTMATTER_TITLE = re.compile(r'^title:\s*"(.+)"\s*$')

HEADER = """\
% PROLEG skeleton generated from {source}
% 法令: {title}
%
% PROLEG の書き方（参考: Sato, PROLEG）
%   ルール:  効果 <= 要件1, 要件2.
%   例外:    exception(効果, 例外).
%   事実:    allege(事実, 当事者).  provide_evidence(事実, 当事者).  plausible(事実).
%
% 各条の下には要件と効果が未記述のブロックだけがあります。
% 条文の本文は {source} を参照してください。
"""


def parse_articles(lines):
    """Yield (section_label, article_label, article_title) in file order."""
    section = ""
    for line in lines:
        top = TOP_HEADING.match(line)
        if top and not line.startswith("###"):
            section = top.group(1)
            continue
        m = ARTICLE_HEADING.match(line)
        if m:
            article = m.group(1)
            title = m.group(2) or ""
            yield section, article, title


def build(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    title = md_path.stem
    for line in lines[:20]:
        t = FRONTMATTER_TITLE.match(line)
        if t:
            title = t.group(1)
            break

    source = str(md_path)
    out = [HEADER.format(source=source, title=title)]

    current_section = None
    for section, article, article_title in parse_articles(lines):
        if section != current_section:
            out.append(f"\n% ===== {section} =====\n")
            current_section = section
        label = f"{article}（{article_title}）" if article_title else article
        out.append(f"% --- {label} ---")
        out.append("% TODO: 要件と効果を記述")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    src = Path(argv[1])
    dst = Path(argv[2])
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(build(src), encoding="utf-8")
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
