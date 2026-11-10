# Ingesting a source

How a book, paper or transcript becomes notes. Pick one short slug for the source (`smil`) and use it throughout: the profile is `sources/source-smil.md`, the scratch folder is `work/smil/`, and the notes are `notes/smil-*.md`.

```
text → split → extract → file → embed → dedup → synthesize → cross-link
```

## 1. Text

Get the source as clean text or markdown. From a PDF, strip what would otherwise become false headings and junk notes: table-of-contents lines (dot leaders), running headers and footers (they repeat on every page), and bare page numbers. Mark chapter titles as `#` headings if you can, since the splitter breaks there.

## 2. Split

```
zkb.py split book.md smil      →  work/smil/chunk-01.md …
```

Chunks are at most 24,000 characters and break at headings where possible, otherwise at paragraphs, without overlap. Larger chunks make extraction time out or go shallow, and overlap only produces duplicate notes.

## 3. Extract

One sub-agent per chunk reads `work/smil/chunk-NN.md` and writes `work/smil/raw-NN.md`. Run a few at a time. Give each only the ability to read its chunk and write its file. A sub-agent that produces nothing after several minutes is stuck: start it again. If sub-agents keep failing, extract chunk by chunk yourself with the same prompt.

A raw file holds several notes, each beginning with a `## Title` line:

```markdown
## Energy transitions take generations
[model] [ECON] [TECH]
- Each new prime mover took 50–70 years to go from 5% to 50% of supply, because …
- **Scope:** …  **Boundary:** …
**Related:** [[energy-density-sets-the-ceiling]]
```

Links in `Related` name other notes by their title in lowercase with hyphens. They are guesses, and filing resolves them.

Choose one of two modes.

**Contribution** (the default). Keep the author's own arguments, models, causal chains and new data. Skip anything an encyclopedia would tell you. Put supporting numbers inside the argument they support, not in notes of their own. State each idea once.

**Attribution**, for sources whose claims you are documenting, not endorsing. Type the notes `claim` and attribute every bullet ("the author argues…"). Write one note per argument, scene or system, with several bullets, not one note per sentence. Quote only where the exact wording matters. Apply the contribution filter too.

Prompt skeleton:

```
Read work/<slug>/chunk-NN.md, part of <source>. Write notes to work/<slug>/raw-NN.md.
Each note: "## Title", then "[type] [DOMAIN]", then bullets, then "**Related:** [[guesses]]".
Types: hypothesis, observation, model, concept, claim. Domains: <the tags in about.md>.
Keep only the author's own contributions: arguments, models, causal chains, new data.
Skip background an encyclopedia would give. Put data inside the argument it supports.
One note per distinct idea, each stated once. Distill: the output must be far smaller than the chunk.
```

What fails: asking it to "be exhaustive" (it transcribes), giving it a compression ratio to hit (the ratio is a result, not a target), and "one idea per note, no bundling" on narrative sources (one scene becomes five notes).

## 4. File

When every chunk is extracted, and not before:

```
zkb.py file smil               →  notes/smil-<title>.md
```

This writes one note per `## Title`, adds `**Source:** [[source-smil]]` to each, and resolves the guessed links against the vault and the new notes. Guesses that match nothing become plain text. It refuses to run twice for the same slug.

Write `sources/source-smil.md`: author, year, tier, the source's incentives, its main contributions.

## 5. Embed and dedup

```
zkb.py embed
zkb.py check 'smil-*'
```

Work through the near-duplicates. Two new notes saying the same thing: merge into the broader one. A new note repeating an idea the vault already has under another name: delete it and, if it adds an angle, fold that into the existing note. A new note on a distinct sub-topic: keep it and link the two. Fix links to anything deleted, then `embed` again. Skipping this step is how a vault fills with the same concept under ten names.

## 6. Synthesize

Write `notes/smil-synthesis.md`, at most 4,000 characters. The source is the subject and the vault is context. State its overall contribution in two or three sentences, trace how the argument builds, name three to seven themes, and close on its deepest unresolved tension. It is not a chapter summary and not a list of notes. Read at most five raw files per pass, because beyond that the themes blur.

## 7. Cross-link

For the new notes that matter, run `zkb.py near <slug>` and add links, with a sentence of context, to related notes outside the source. A source from a new domain will have few, which is normal. Update the hub, delete `work/smil/`, and log the ingest in `_current.md`.
