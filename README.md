# Knowledge Tools

Tools for building knowledge: a method for finding out what is true, and a tool for keeping the records the method runs on.

## [Layered Coherence](layered-coherence.md)

A framework for turning records into knowledge. Claims are stacked in layers, each answerable to the layers beneath it, with confidence highest at the base and earned at every step above. It comes with a starting model of reality built the same way, from physics up to culture.

## [zkb](zkb/)

A Zettelkasten knowledge base for AI agents: durable, graph-structured memory in plain markdown. Each note holds one idea, declares its type (hypothesis, observation, model, concept or claim) and domain, and links to other notes. An embedding index finds notes by meaning, so the agent checks what it already knows before writing anything new, and the vault gets simpler as it learns instead of larger.

It is three files:

- [SKILL.md](zkb/SKILL.md): how the agent uses the vault. Note format, search, and the ingest, test, synthesize and maintain routines.
- [ingest.md](zkb/ingest.md): how a book, paper or transcript becomes notes.
- [zkb.py](zkb/zkb.py): the tool. Semantic search, vault audit, graph drawing, and source splitting and filing.

### Setup

Copy the `zkb/` folder into your agent's skills directory (for Claude Code, `~/.claude/skills/`).

```bash
pip install numpy
```

```bash
pip install matplotlib networkx scipy   # only for `zkb.py graph`
```

Embeddings come from any OpenAI-compatible endpoint. The default is `qwen3-embedding-8b` on Fireworks, which the similarity thresholds are calibrated for.

```bash
export ZKB_EMBED_KEY=...        # required
export ZKB_EMBED_URL=...        # optional: another provider's /embeddings endpoint
export ZKB_EMBED_MODEL=...      # optional: another model; recalibrate the thresholds in zkb.py
```

Then, from the directory that holds your vault's `notes/` folder:

```bash
python3 path/to/zkb.py embed
python3 path/to/zkb.py search "what do I know about energy transitions"
python3 path/to/zkb.py check
```

`check` holds all pairwise similarities in memory, which is comfortable to roughly ten thousand notes.
