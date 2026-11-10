#!/usr/bin/env python3
"""zkb: tools for a Zettelkasten knowledge base kept as plain markdown.

Run from the vault directory, or set ZKB_DIR.

  zkb.py embed                  bring the embedding index up to date with notes/
  zkb.py search "query" [-n N]  notes closest in meaning to a query
  zkb.py near SLUG [-n N]       notes closest in meaning to an existing note
  zkb.py check [PATTERN]        audit format, links, duplicates, missing links and orphans
  zkb.py graph                  draw the vault to graph.png
  zkb.py split FILE SLUG        cut a source text into work/SLUG/chunk-NN.md
  zkb.py file SLUG              file extracted notes from work/SLUG/raw-*.md into notes/

Embeddings come from an OpenAI-compatible endpoint. Set ZKB_EMBED_KEY, plus
ZKB_EMBED_URL and ZKB_EMBED_MODEL to use another provider or model.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import textwrap
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from fnmatch import fnmatch
from pathlib import Path
from typing import NamedTuple

import numpy as np

VAULT = Path(os.environ.get("ZKB_DIR", "."))
NOTES = VAULT / "notes"
INDEX = VAULT / "index.npz"
EMBED_URL = os.environ.get("ZKB_EMBED_URL", "https://api.fireworks.ai/inference/v1/embeddings")
EMBED_MODEL = os.environ.get("ZKB_EMBED_MODEL", "fireworks/qwen3-embedding-8b")

# Each note type, and the fields a note of that type must carry.
TYPES = {
    "hypothesis": ("Falsification", "Status"),
    "observation": ("Source",),
    "model": ("Scope", "Boundary"),
    "concept": ("Scope",),
    "claim": ("Source",),
}

# Cosine similarities, calibrated on qwen3-embedding-8b. Recalibrate for another model.
DUPLICATE = 0.80  # above this, two notes state the same idea
RELATED = 0.60  # above this, two notes should link to each other

CHUNK = 24_000  # characters per extraction chunk; larger ones time out or lose detail
EMBED_CHARS = 20_000  # embed at most this much of a note, inside every model's input limit
BATCH = 32  # notes per embedding request


class Note(NamedTuple):
    slug: str
    title: str
    type: str
    domains: list
    links: set  # slugs this note points to
    text: str


def link_slug(target):
    return target.strip().lower().replace(" ", "-")


def read_note(path):
    text = path.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    title = next((line.lstrip("# ").strip() for line in lines if line.startswith("#")), path.stem)
    tag_line = next((line for line in lines[:3] if re.fullmatch(r"\s*(\[[^\[\]]+\]\s*)+", line)), "")
    kind, *rest = re.findall(r"[^\[\]\s,/]+", tag_line) or [""]
    domains = [tag for tag in rest if re.fullmatch(r"[A-Z]{2,6}", tag)]
    links = {link_slug(target) for target in re.findall(r"\[\[([^\]|#]+)", text)}
    return Note(path.stem, title, kind.lower(), domains, links, text)


def load_notes():
    if not NOTES.is_dir():
        sys.exit(f"no notes/ in {VAULT.resolve()}: run from the vault directory or set ZKB_DIR")
    return [read_note(path) for path in sorted(NOTES.glob("*.md"))]


# ── Index: slug → (digest of the embedded text, unit vector) ──────────────────


def digest(note):
    return hashlib.sha256(f"{EMBED_MODEL}\n{note.text}".encode()).hexdigest()[:16]


def load_index():
    if not INDEX.exists():
        return {}
    with np.load(INDEX) as stored:
        return {str(slug): (str(mark), vector) for slug, mark, vector in zip(stored["slugs"], stored["digests"], stored["vectors"])}


def save_index(index):
    slugs = sorted(index)
    scratch = INDEX.with_name("index.tmp.npz")
    np.savez(
        scratch,
        slugs=np.array(slugs),
        digests=np.array([index[slug][0] for slug in slugs]),
        vectors=np.array([index[slug][1] for slug in slugs], dtype=np.float32),
    )
    scratch.replace(INDEX)


def embed_texts(texts):
    """Unit vectors for texts, from the embeddings endpoint."""
    key = os.environ.get("ZKB_EMBED_KEY") or sys.exit("set ZKB_EMBED_KEY to an API key for " + EMBED_URL)
    request = urllib.request.Request(
        EMBED_URL,
        json.dumps({"model": EMBED_MODEL, "input": texts}).encode(),
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "zkb"},
    )
    for wait in (2, 10, 40, None):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                rows = json.load(response)["data"]
            break
        except urllib.error.HTTPError as error:
            if wait is None or error.code not in (429, 500, 502, 503):
                sys.exit(f"embedding request failed ({error.code}): {error.read().decode(errors='replace')[:300]}")
            time.sleep(wait)
    vectors = np.array([row["embedding"] for row in sorted(rows, key=lambda row: row["index"])], dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def indexed():
    """Every note and its vector, as (notes, matrix) in the same order."""
    notes, index = load_notes(), load_index()
    stale = sum(index.get(note.slug, ("",))[0] != digest(note) for note in notes)
    if stale:
        sys.exit(f"the index is out of date for {stale} of {len(notes)} notes: run `zkb.py embed`")
    return notes, np.array([index[note.slug][1] for note in notes])


# ── Commands ──────────────────────────────────────────────────────────────────


def embed():
    notes, old = load_notes(), load_index()
    index = {note.slug: old[note.slug] for note in notes if old.get(note.slug, ("",))[0] == digest(note)}
    stale = [note for note in notes if note.slug not in index]
    try:
        for start in range(0, len(stale), BATCH):
            batch = stale[start : start + BATCH]
            vectors = embed_texts([note.text[:EMBED_CHARS] for note in batch])
            index.update({note.slug: (digest(note), vector) for note, vector in zip(batch, vectors)})
            print(f"  embedded {start + len(batch)}/{len(stale)}")
    finally:  # keep what was embedded even if a request fails
        save_index(index)
    print(f"{len(notes)} notes indexed, {len(stale)} embedded")


def show(notes, scores, n):
    for i in np.argsort(-scores)[:n]:
        tags = " ".join([notes[i].type, *notes[i].domains])
        print(f"{scores[i]:.3f}  {notes[i].slug}  [{tags}]  {notes[i].title}")


def search(query, n):
    notes, matrix = indexed()
    show(notes, matrix @ embed_texts([query])[0], n)


def near(slug, n):
    notes, matrix = indexed()
    row = next((i for i, note in enumerate(notes) if note.slug == slug), None)
    if row is None:
        sys.exit(f"no note named {slug}")
    scores = matrix @ matrix[row]
    scores[row] = -1
    show(notes, scores, n)


def check(pattern):
    notes, matrix = indexed()
    position = {note.slug.lower(): i for i, note in enumerate(notes)}
    hubs = [read_note(path) for path in sorted((VAULT / "hubs").glob("*.md"))]
    known = set(position) | {hub.slug.lower() for hub in hubs} | {path.stem.lower() for path in (VAULT / "sources").glob("*.md")}
    cited = {link for note in [*notes, *hubs] for link in note.links - {note.slug.lower()}}
    chosen = np.array([fnmatch(note.slug, pattern) for note in notes])

    similarity = matrix @ matrix.T
    np.fill_diagonal(similarity, 0)
    linked = np.zeros_like(similarity, dtype=bool)
    for i, note in enumerate(notes):
        for j in (position[link] for link in note.links if link in position):
            linked[i, j] = linked[j, i] = True

    def pairs(mask):
        rows, cols = np.nonzero(np.triu(mask, 1) & (chosen[:, None] | chosen[None, :]))
        order = np.argsort(-similarity[rows, cols])
        return [f"{similarity[i, j]:.3f}  {notes[i].slug}  {notes[j].slug}" for i, j in zip(rows[order], cols[order])]

    untyped, incomplete, dangling, orphans, misfiled = [], [], [], [], []
    for i in np.nonzero(chosen)[0]:
        note = notes[i]
        if note.type not in TYPES:
            untyped.append(f"{note.slug}  [{note.type or 'no type line'}]")
        missing = [field for field in TYPES.get(note.type, ()) if not re.search(rf"^\W*{field}", note.text, re.M | re.I)]
        if missing:
            incomplete.append(f"{note.slug}  {note.type} without {', '.join(missing)}")
        dangling += [f"{note.slug}  [[{link}]]" for link in sorted(note.links - known)]
        nearest = np.argsort(-similarity[i])[:10]
        if note.slug.lower() not in cited:
            orphans.append(f"{note.slug}  (nearest: {notes[nearest[0]].slug} {similarity[i, nearest[0]]:.3f})")
        around = Counter(domain for j in nearest for domain in set(notes[j].domains))
        misfiled += [f"{note.slug}  [{' '.join(note.domains)}] but {count}/10 neighbours are {domain}" for domain, count in around.items() if count >= 7 and domain not in note.domains]

    for heading, lines in (
        ("Unknown type", untyped),
        ("Missing required fields", incomplete),
        ("Dangling links", dangling),
        (f"Near-duplicates (over {DUPLICATE})", pairs(similarity > DUPLICATE)),
        (f"Related but unlinked ({RELATED} to {DUPLICATE})", pairs((similarity > RELATED) & (similarity <= DUPLICATE) & ~linked)),
        ("Orphans (nothing links to them)", orphans),
        ("Domain differs from neighbours", misfiled),
    ):
        print(f"\n{heading}: {len(lines)}")
        print("".join(f"  {line}\n" for line in lines[:25]), end="")
        if len(lines) > 25:
            print(f"  … and {len(lines) - 25} more; narrow with a slug pattern")

    def tally(counter):
        return ", ".join(f"{name} {count}" for name, count in counter.most_common())

    print(f"\n{len(notes)} notes")
    print("types: " + tally(Counter(note.type or "none" for note in notes)))
    print("domains: " + tally(Counter(domain for note in notes for domain in note.domains)))


def cluster(matrix, k):
    """Spherical k-means: each row's cluster, and the unit centroids."""
    rng = np.random.default_rng(0)
    centroids = matrix[[rng.integers(len(matrix))]]
    while len(centroids) < k:  # seed each new centroid far from the ones already chosen
        distance = np.clip(1 - (matrix @ centroids.T).max(axis=1), 0, None).astype(float) ** 2
        centroids = np.vstack([centroids, matrix[rng.choice(len(matrix), p=distance / distance.sum())]])
    for _ in range(50):
        labels = (matrix @ centroids.T).argmax(axis=1)
        sums = np.array([matrix[labels == c].sum(axis=0) for c in range(k)])
        norms = np.linalg.norm(sums, axis=1, keepdims=True)
        centroids = np.where(norms > 0, sums / np.maximum(norms, 1e-12), centroids)
    return labels, centroids


def graph():
    """Position notes by their links, group them by meaning, and label each group by its most central note."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    notes, matrix = indexed()
    n = len(notes)
    position = {note.slug.lower(): i for i, note in enumerate(notes)}
    links = sorted({(min(i, position[link]), max(i, position[link])) for i, note in enumerate(notes) for link in note.links if position.get(link, i) != i})
    links = np.array(links, dtype=int).reshape(-1, 2)
    degree = np.bincount(links.ravel(), minlength=n)

    similarity = matrix @ matrix.T
    np.fill_diagonal(similarity, 0)
    web = nx.Graph()
    web.add_weighted_edges_from((i, int(j), 0.5) for i, row in enumerate(similarity) for j in np.argsort(-row)[:5])  # pull toward the nearest notes
    web.add_weighted_edges_from((int(i), int(j), 1.0) for i, j in links)  # stronger pull along links
    layout = nx.spring_layout(web, k=3 / np.sqrt(n), iterations=200, seed=0)
    xy = np.array([layout[i] for i in range(n)])

    k = max(2, min(24, round(np.sqrt(n / 2))))
    labels, centroids = cluster(matrix, k)

    ground, ink = "#0a0a14", "#f0f0f8"
    domains = Counter(note.domains[0] for note in notes if note.domains)
    colour = {domain: plt.cm.tab20.colors[rank] for rank, (domain, _) in enumerate(domains.most_common(20))}  # rarer domains stay grey
    figure, axes = plt.subplots(figsize=(32, 24), facecolor=ground)
    axes.axis("off")

    crossing = labels[links[:, 0]] != labels[links[:, 1]]
    axes.add_collection(LineCollection(xy[links[~crossing]], colors="#5a5a8e", alpha=0.15, linewidths=0.8))
    axes.add_collection(LineCollection(xy[links[crossing]], colors="#c8a030", alpha=0.25, linewidths=1.2))
    axes.scatter(*xy.T, c=[colour.get(note.domains[0], "#888888") if note.domains else "#888888" for note in notes], s=np.clip(30 + 6 * degree, 30, 240), alpha=0.8, linewidths=0, zorder=2)

    captions = []
    for c in np.argsort(-np.bincount(labels, minlength=k)):  # larger groups claim their spot first
        members = np.nonzero(labels == c)[0]
        if len(members):
            central = notes[members[(matrix[members] @ centroids[c]).argmax()]]
            caption = textwrap.fill(central.title, 28, max_lines=2, placeholder="…") + f"\n({len(members)})"
            box = dict(boxstyle="round,pad=0.4", facecolor="#1c1c30", edgecolor=colour.get(central.domains[0], ink) if central.domains else ink, alpha=0.92)
            captions.append(axes.text(*np.median(xy[members], axis=0), caption, fontsize=15, color=ink, fontweight="bold", ha="center", va="center", zorder=3, bbox=box))
    figure.canvas.draw()
    placed = []
    for caption in captions:  # slide a caption upward until it clears the ones already placed
        box = caption.get_window_extent().expanded(1.15, 1.4)
        while any(box.overlaps(other) for other in placed):
            box = box.translated(0, box.height / 4)
        placed.append(box)
        caption.set_position(axes.transData.inverted().transform(((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2)))

    handles = [Line2D([], [], marker="o", linestyle="", color=colour[domain], markersize=14, label=f"{domain} ({domains[domain]})") for domain in colour]
    axes.legend(handles=handles, loc="lower left", fontsize=14, ncol=2, facecolor="#15152a", edgecolor="#3a3a5a", labelcolor="#cccccc")
    axes.set_title(f"{n} notes · {len(links)} links · {k} groups · gold links cross groups", fontsize=24, color="#8b8bd4", loc="left")
    figure.savefig(VAULT / "graph.png", dpi=100, facecolor=ground, bbox_inches="tight", pad_inches=0.4)
    print(f"wrote {VAULT / 'graph.png'}")


def pieces(text, separators=("\n\n", "\n", ". ")):
    """Text as pieces no longer than CHUNK, cut at the coarsest separator that manages it."""
    if len(text) <= CHUNK or not separators:
        return [text]
    return [piece for part in text.split(separators[0]) for piece in pieces(part + separators[0], separators[1:])]


def split(source, slug):
    """Cut a source text into chunks, breaking at headings where possible and paragraphs otherwise."""
    text = unicodedata.normalize("NFC", Path(source).read_text(encoding="utf-8"))
    chunks = [""]
    for piece in pieces(text):
        at_heading = piece.lstrip().startswith("#") and len(chunks[-1]) > CHUNK / 2
        if chunks[-1] and (at_heading or len(chunks[-1]) + len(piece) > CHUNK):
            chunks.append("")
        chunks[-1] += piece
    folder = VAULT / "work" / slug
    folder.mkdir(parents=True, exist_ok=True)
    for number, chunk in enumerate(chunks, 1):
        (folder / f"chunk-{number:02d}.md").write_text(chunk.strip() + "\n", encoding="utf-8")
    print(f"{len(text)} characters → {len(chunks)} chunks in {folder}")


def file(slug):
    """File the notes in work/SLUG/raw-*.md (each starting `## Title`) as notes/SLUG-<title>.md."""
    if any(NOTES.glob(f"{slug}-*.md")):
        sys.exit(f"notes/{slug}-*.md already exist: {slug} has been filed")
    raw = [path.read_text(encoding="utf-8") for path in sorted((VAULT / "work" / slug).glob("raw-*.md"))]
    filed, uses = {}, Counter()
    for block in (block for text in raw for block in re.split(r"^## +", text, flags=re.M)[1:]):
        title, _, body = block.partition("\n")
        ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
        name = f"{slug}-{re.sub(r'[^a-z0-9]+', '-', ascii_title).strip('-')[:60]}"
        uses[name] += 1
        if uses[name] > 1:  # a second note with the same title
            name += f"-{uses[name]}"
        body = re.sub(r"^\*\*Source:.*\n?|^-{3,}\s*$", "", body, flags=re.M).strip()
        filed[name] = f"# {title.strip()}\n{body}\n**Source:** [[source-{slug}]]\n"

    known = {path.stem.lower() for folder in ("notes", "hubs", "sources") for path in (VAULT / folder).glob("*.md")} | set(filed) | {f"source-{slug}"}
    dropped = 0

    def resolve(match):
        nonlocal dropped
        target = link_slug(match[1])
        for candidate in (target, f"{slug}-{target}"):
            if candidate in known:
                return f"[[{candidate}]]"
        dropped += 1
        return match[1]  # a guess that matches no note stays as plain text

    for name, text in filed.items():
        (NOTES / f"{name}.md").write_text(re.sub(r"\[\[([^\]|#]+)\]\]", resolve, text), encoding="utf-8")
    print(f"filed {len(filed)} notes as notes/{slug}-*.md; {dropped} links matched no note and became plain text")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    def command(function, *arguments):
        sub = commands.add_parser(function.__name__)
        sub.set_defaults(run=function)
        for name, options in arguments:
            sub.add_argument(name, **options)

    count = ("-n", dict(type=int, default=10))
    command(embed)
    command(search, ("query", {}), count)
    command(near, ("slug", {}), count)
    command(check, ("pattern", dict(nargs="?", default="*")))
    command(graph)
    command(split, ("source", {}), ("slug", {}))
    command(file, ("slug", {}))

    arguments = vars(parser.parse_args())
    del arguments["command"]
    arguments.pop("run")(**arguments)


if __name__ == "__main__":
    main()
