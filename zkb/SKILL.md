---
name: zkb
description: Zettelkasten knowledge base. Durable, graph-structured agent memory in plain markdown, made of typed notes (hypothesis, observation, model, concept, claim) joined by wikilinks and found by semantic search. Use to record what you learn, to check what is already known before acting, to ingest books and papers, and to compress or audit the vault.
---

# ZKB

A knowledge base that models reality instead of collecting information. Each note holds one idea in plain markdown, declares its type and domain, and links to other notes. Progress is explanatory power per note, not note count: as understanding deepens, notes merge and the vault gets simpler.

## The vault

```
notes/        the knowledge graph, one note per file
hubs/         hub-<domain>.md: a narrative map of one domain, linking into notes/
sources/      source-<slug>.md: one profile per source, with raw texts alongside
primer.md     the vault compressed to its load-bearing claims
about.md      what each domain tag means, which domains are adjacent, open questions
_current.md   session journal, under 50 lines
index.npz     embedding index, derived from notes/
work/         scratch space while ingesting a source
```

The notes are the asset. Everything else can be rebuilt from them. Any file can be wrong or missing without breaking the rest.

## A note

```markdown
# Niche construction
[concept] [EVO] [ECON]
- Organisms change their environments, and the changed environments change what is selected for.
- **Scope:** includes built artifacts and institutions; excludes by-products with no effect on selection.
**Related:** [[gene-culture-coevolution]], [[selection-keeps-what-persists]]
**Source:** [[source-odling-smee-2003]]
```

The title comes first, then the tag line with the type followed by one or more domains (2–6 capital letters, the primary domain first). There is no frontmatter. The filename is a lowercase slug. A link is `[[slug]]`, and the prose around it says how the two notes relate. Every note links to at least one other. Backlinks are found by grep, never declared.

The type sets what a note must contain. A note that cannot supply it is not ready to store.

| Type | What it is | Must contain |
|---|---|---|
| hypothesis | a testable claim | **Falsification:** what would refute it. **Status:** open, confirmed or refuted |
| observation | an empirical finding | **Source:**, with method, sample, effect size and replication in the body |
| model | a compression of observations and hypotheses | **Scope:** what it explains. **Boundary:** where it breaks |
| concept | a definition | **Scope:** what it includes and excludes |
| claim | an assertion documented from a source, not endorsed | **Source:**, with every bullet attributed ("the author argues…") |

A source profile in `sources/` records author, year, tier, the source's incentives, and its main contributions. Tiers weight authority: **L0** is the user's own work, **L1** is books and papers, **L2** is articles, posts and podcasts.

## Tools

Run `zkb.py` (next to this file) from the vault directory.

```
zkb.py search "query" [-n N]   notes closest in meaning to a query
zkb.py near SLUG [-n N]        notes closest in meaning to an existing note
zkb.py embed                   index new and changed notes; run after every write
zkb.py check [PATTERN]         audit the vault, or only the notes matching a slug pattern
zkb.py graph                   draw the vault to graph.png
zkb.py split FILE SLUG         cut a source text into chunks  (see ingest.md)
zkb.py file SLUG               file extracted notes into notes/  (see ingest.md)
```

**Search by meaning to discover; grep to retrieve.** Grep finds only the words you guessed, and the same idea is often stored under different words. Use `search` with three or more different phrasings whenever you are exploring a topic, checking whether a note already exists, or looking for connections. Use grep when you know the exact slug, author or term, and for counting and backlinks.

Scores are cosine similarity:

| Score | Meaning |
|---|---|
| over 0.80 | the same idea twice: merge |
| over 0.60 | closely related: read it before writing, and link |
| over 0.50 | worth a look |

## Primitives

**Read `primer.md` before any work in the vault.** It carries the integrated view that individual notes assume.

**ingest**: new material becomes notes. Search three or more phrasings first; if a note above 0.60 already covers the idea, extend or link it instead of writing a new one. Write only what the vault does not already model as well. Search adjacent domains (see `about.md`) for a cross-domain link. Record the source's incentives in its profile. Then `embed`, update the hub, and log in `_current.md`.

**test**: ask the vault a question. Search, then grep for known terms, then read the hub. Look for contradicting notes as hard as for supporting ones. State a prior from established facts before updating on new evidence. Verdict: confirmed, refuted, partial or underdetermined, plus the gaps.

**synthesize**: change the graph's shape. *Bridge:* link two domains into a claim neither note makes alone. *Compress:* replace several related notes with one model that subsumes them. *Elevate:* observations into a model, models into a theory.

**maintain**: run `check` and work through it: unknown types, missing required fields, dangling links, near-duplicates, related notes that do not link, orphans, and notes whose domain differs from their neighbours'. For each near-duplicate pair, read both and either merge into the more complete note (redirect links to the retired slug) or keep both and link them. Merging notes derived from the user's own work needs the user's approval. Regenerate `primer.md` when the vault's shape has changed.

## Programs

**investigate** *question*: test → name the gaps → ingest to fill them → synthesize → test again. Report after at most three cycles. Before the verdict, audit yourself: did you search both sides equally, and does the verdict merely restate the consensus?

**develop** *domain*: ingest where the domain is thin, test where it is thick, compress where it is redundant, bridge where it is isolated. The hub is the deliverable. One domain per run.

**ingest a source** (book, paper, transcript): follow [ingest.md](ingest.md).

## Reasoning rules

- **All evidence arrives through filters.** Funding, publication incentives, career consequences and social pressure shape which findings exist and how they are framed. Reason about the process that produced the evidence as well as the evidence.
- **Numbers beat narratives.** Effect sizes, sample sizes and replication status are harder to distort than framing.
- **Consensus is not evidence.** Cite the studies, not the position statement. Apply the same methodological scrutiny to both sides.
- **A logical gap is not a refutation.** "X does not prove Y" blocks a deduction. It does not make Y false. Where deduction stops, reason probabilistically from established facts.
- **Decompose contested questions** into independent factual parts, answer each, then combine. A question answered whole inherits the framing of whoever posed it.

When sending sub-agents to search or read: ask what a named source found ("What did Author, Year report?") instead of what "the evidence says"; require them to actually search or read; run several with different framings and compare; and take data from them, not evaluations.

## Retiring notes

A refuted hypothesis becomes `refuted-<slug>.md`, recording the claim, the refuting evidence and the date. A superseded note keeps its content and gains `**Superseded by:** [[new-note]]`. Neither is deleted. They map where the vault has already been, and a refuted claim is not re-tested without new evidence.

## Sessions

Start by reading `_current.md` and `primer.md`. Write notes as you learn things, and `embed` after writing. After about twenty new notes, synthesize before ingesting more. End by running one search for a cross-domain link from what you touched, and log the session in `_current.md`.

## Starting a vault

Create `notes/`, `hubs/` and `sources/`. Write `about.md` with three to five domain tags and what each covers. Write five to ten seed notes. Set `ZKB_EMBED_KEY` and run `zkb.py embed`. Write `primer.md` once there is enough to compress.
