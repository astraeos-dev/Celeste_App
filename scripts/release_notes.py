"""
scripts/release_notes.py — Note de version tirée de CHANGELOG.md
================================================================
Écrit la section « ## <version> » de CHANGELOG.md : le workflow de build en
fait la note de la Release GitHub (gh release create --notes-file), que la
fenêtre de mise à jour de Céleste montre ensuite aux utilisateurs.

Usage : python scripts/release_notes.py <version> [fichier]
        (sans fichier : à l'écran ; le fichier est toujours en UTF-8)
Sort en erreur (code 1) si la version n'a pas de section, ou une section vide.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")


def sections(text):
    """[(version, liste)] des sections « ## x.y[.z] », dans l'ordre du fichier :
    les tirets qui suivent le titre, jusqu'au premier paragraphe ordinaire,
    chacun sur une ligne (la fenêtre de mise à jour ne recoupe pas les lignes)."""
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
    """Texte de la section de *version*, ou None."""
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
        sys.stderr.write(f"CHANGELOG.md : pas de section « ## {version} »\n")
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
