"""
scripts/release_notes.py — The release note, from CHANGELOG.md
===============================================================
Writes the "## <version>" section of CHANGELOG.md: the build workflow makes it
the note of the GitHub Release (gh release create --notes-file), which the
update window of Céleste then shows to users.

Usage: python scripts/release_notes.py <version> [file]
       (without a file: on screen; the file is always UTF-8)
Exits with an error (code 1) when the version has no section, or an empty one.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")


def sections(text):
    """[(version, list)] of the "## x.y[.z]" sections, in the order of the file:
    the dashes after the heading, up to the first ordinary paragraph, each on
    one line (the update window does not rewrap lines)."""
    found = []
    for match in re.finditer(r"^## +(\d+(?:\.\d+)+)[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S):
        items = []
        for line in match.group(2).strip("\n").split("\n"):
            if line.startswith("-"):
                items.append(line.rstrip())
            elif line.startswith(" ") and items:
                items[-1] += " " + line.strip()
            elif line.strip():
                break
        found.append((match.group(1), "\n".join(items)))
    return found


def notes(version, text=None):
    """Text of the section of *version*, or None."""
    if text is None:
        with open(CHANGELOG, encoding="utf-8") as f:
            text = f.read()
    return dict(sections(text)).get(version) or None


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(__doc__)
        return 2
    version = argv[1]
    body = notes(version)
    if not body:
        sys.stderr.write(f"CHANGELOG.md: no \"## {version}\" section\n")
        return 1
    data = (body + "\n").encode("utf-8")
    if len(argv) > 2:
        with open(argv[2], "wb") as f:
            f.write(data)
    else:
        sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
