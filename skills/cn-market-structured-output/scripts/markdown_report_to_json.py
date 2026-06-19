#!/usr/bin/env python3
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
REPORT_FORMAT = "markdown-heading-tree-v1"


def normalize_title(raw_title):
    return re.sub(r"\s+#+\s*$", "", raw_title).strip()


def make_anchor(title, used):
    lowered = title.strip().lower()
    chars = []
    last_dash = False
    for char in lowered:
        if char.isalnum():
            chars.append(char)
            last_dash = False
        elif not last_dash:
            chars.append("-")
            last_dash = True
    anchor = "".join(chars).strip("-") or "section"
    base = anchor
    suffix = 2
    while anchor in used:
        anchor = f"{base}-{suffix}"
        suffix += 1
    used.add(anchor)
    return anchor


def parse_markdown_report(markdown):
    lines = markdown.splitlines()
    headings = []
    used_anchors = set()

    for idx, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        title = normalize_title(match.group(2))
        headings.append(
            {
                "order": len(headings) + 1,
                "id": f"s{len(headings) + 1:03d}",
                "level": level,
                "title": title,
                "headingMarkdown": line,
                "anchor": make_anchor(title, used_anchors),
                "startLine": idx + 1,
                "contentStartLine": idx + 2,
                "parentId": None,
                "childrenIds": [],
            }
        )

    if not headings:
        content = markdown.strip()
        return {
            "reportFormat": REPORT_FORMAT,
            "reportTitle": "",
            "reportMarkdown": markdown,
            "reportSections": [
                {
                    "order": 1,
                    "id": "s001",
                    "level": 1,
                    "title": "",
                    "headingMarkdown": "",
                    "anchor": "section",
                    "headingPath": [],
                    "parentId": None,
                    "childrenIds": [],
                    "contentMarkdown": content,
                    "content": content,
                    "startLine": 1,
                    "contentStartLine": 1,
                    "contentEndLine": len(lines),
                    "blockEndLine": len(lines),
                }
            ],
            "reportSectionTree": [],
        }

    stack = []
    by_id = {}
    for section in headings:
        while stack and stack[-1]["level"] >= section["level"]:
            stack.pop()
        if stack:
            parent = stack[-1]
            section["parentId"] = parent["id"]
            parent["childrenIds"].append(section["id"])
            section["headingPath"] = parent["headingPath"] + [section["title"]]
        else:
            section["headingPath"] = [section["title"]]
        stack.append(section)
        by_id[section["id"]] = section

    for idx, section in enumerate(headings):
        next_start = headings[idx + 1]["startLine"] if idx + 1 < len(headings) else len(lines) + 1
        content_lines = lines[section["startLine"] : next_start - 1]
        content_markdown = "\n".join(content_lines).strip()
        section["contentMarkdown"] = content_markdown
        section["content"] = content_markdown
        section["contentEndLine"] = max(section["contentStartLine"] - 1, next_start - 1)

        block_end = len(lines)
        for later in headings[idx + 1 :]:
            if later["level"] <= section["level"]:
                block_end = later["startLine"] - 1
                break
        section["blockEndLine"] = block_end

    tree_nodes = {section["id"]: {**deepcopy(section), "children": []} for section in headings}
    roots = []
    for section in headings:
        node = tree_nodes[section["id"]]
        parent_id = section["parentId"]
        if parent_id:
            tree_nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)

    return {
        "reportFormat": REPORT_FORMAT,
        "reportTitle": headings[0]["title"],
        "reportMarkdown": markdown,
        "reportSections": headings,
        "reportSectionTree": roots,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert a Markdown report into heading-based JSON fields."
    )
    parser.add_argument("markdown_file", help="Markdown report file")
    parser.add_argument("--base-json", help="Existing market JSON to patch")
    parser.add_argument("--output", "-o", help="Output JSON path")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON instead of indented JSON",
    )
    args = parser.parse_args()

    markdown_path = Path(args.markdown_file)
    markdown = markdown_path.read_text(encoding="utf-8").strip() + "\n"
    report_fields = parse_markdown_report(markdown)

    if args.base_json:
        doc = json.loads(Path(args.base_json).read_text(encoding="utf-8"))
        doc.update(report_fields)
    else:
        doc = report_fields

    text = json.dumps(
        doc,
        ensure_ascii=False,
        separators=(",", ":") if args.compact else None,
        indent=None if args.compact else 2,
    )
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    raise SystemExit(main())
