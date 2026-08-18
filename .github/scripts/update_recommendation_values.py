#!/usr/bin/env python3

"""Update the Recommendation image in the local Helm values file."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SHA = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")


def update_values(path: Path, repository: str, tag: str) -> None:
    if not REPOSITORY.fullmatch(repository):
        raise ValueError(f"Invalid image repository: {repository}")
    if not SHA.fullmatch(tag):
        raise ValueError("Image tag must be a full, lowercase 40-character Git SHA.")

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    recommendation_start = _unique_line(lines, "  recommendation:")
    recommendation_end = _block_end(lines, recommendation_start, 2)
    image_start = _unique_line(
        lines,
        "    imageOverride:",
        recommendation_start + 1,
        recommendation_end,
    )
    image_end = _block_end(lines, image_start, 4)
    repository_line = _unique_key(
        lines, "repository", 6, image_start + 1, image_end
    )
    tag_line = _unique_key(lines, "tag", 6, image_start + 1, image_end)

    lines[repository_line] = _replace_value(
        lines[repository_line], "repository", repository
    )
    lines[tag_line] = _replace_value(lines[tag_line], "tag", tag)
    path.write_text("".join(lines), encoding="utf-8")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _block_end(lines: list[str], start: int, indent: int) -> int:
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped and not stripped.startswith("#") and _indent(lines[index]) <= indent:
            return index
    return len(lines)


def _unique_line(
    lines: list[str], value: str, start: int = 0, end: int | None = None
) -> int:
    stop = len(lines) if end is None else end
    matches = [
        index
        for index in range(start, stop)
        if lines[index].rstrip("\r\n") == value
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {value!r}; found {len(matches)}.")
    return matches[0]


def _unique_key(
    lines: list[str], key: str, indent: int, start: int, end: int
) -> int:
    matches = [
        index
        for index in range(start, end)
        if _indent(lines[index]) == indent
        and lines[index].strip().startswith(f"{key}:")
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one Recommendation {key}; found {len(matches)}."
        )
    return matches[0]


def _replace_value(line: str, key: str, value: str) -> str:
    newline = "\n" if line.endswith("\n") else ""
    return f"      {key}: {value}{newline}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    arguments = parser.parse_args()
    update_values(arguments.file, arguments.repository, arguments.tag)


if __name__ == "__main__":
    main()
