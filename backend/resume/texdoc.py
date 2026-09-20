"""
LaTeX resume as a frozen document plus a handful of editable text spans.

This is the piece that makes tailoring safe. The previous attempt at this
feature (`backend/ai/resume_tailor.py`, deleted in a680b93) asked the model to
emit an entire `.tex` document as a JSON string; the output could not be trusted
to compile and there was no compiler to check it with.

Here the model never sees or writes LaTeX. The source is kept verbatim and only
*spans* of plain prose inside it are replaced, so:

  * the preamble, document class, custom macros and section scaffolding are
    untouched by construction — the PDF keeps the author's exact design;
  * rendering with no edits returns the input byte for byte;
  * a span is only offered for rewriting when it is plain text. A bullet holding
    maths or nested commands can still be reordered or dropped, just not reworded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

# Characters that must be escaped when plain text goes back into LaTeX.
# Order matters: the backslash has to be replaced first or it would corrupt the
# replacements made for the other characters.
_ESCAPES: Sequence[tuple[str, str]] = (
    ("\\", r"\textbackslash{}"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
)

# The only backslash sequences a span may contain and still count as plain text.
_ALLOWED_ESCAPE_RE = re.compile(r"\\[%&$#_{}]")

# Anything else beginning with a backslash means the span carries markup.
_ANY_COMMAND_RE = re.compile(r"\\[A-Za-z@]+|\\\\")

_SECTION_RE = re.compile(r"\\(?:section|subsection)\*?\{([^{}]*)\}")

# Entry headings: the company/project line a bullet belongs under. Covers the
# common resume-template spellings plus a bare \textbf{...} lead-in.
_ENTRY_MACRO_RE = re.compile(
    r"\\(?:role|resumeSubheading|resumeProjectHeading|resumeSubItem|cventry|entry|textbf)\s*\{"
)

_ITEM_RE = re.compile(r"\\item\b")

# Macro-style bullets: \resumeItem{...}, \cvitem{...}. The editable part is the
# final brace group.
_MACRO_ITEM_RE = re.compile(r"\\(resumeItem|cvitem|achievement)\s*\{")


# Letter pairs TeX fuses into a single ligature glyph. XeTeX writes that glyph to
# the PDF as U+FB00-FB04, so extracting the text yields "traﬃc" and an ATS
# searching for "traffic" finds nothing.
#
# The usual `f{}f` idiom does NOT help here: XeTeX shapes through empty groups,
# so the ligature still forms. A zero-width kern does break the shaping run —
# measured 10/10 words extracting as plain ASCII versus 6/10 with `{}`.
_LIGATURE_PAIRS = ("ffi", "ffl", "ff", "fi", "fl")
_LIGATURE_BREAK = "\\kern0pt "


def break_ligatures(text: str) -> str:
    """Split ligature-forming letter runs so the PDF stays greppable."""
    out = text
    for pair in _LIGATURE_PAIRS:
        out = out.replace(pair, pair[0] + _LIGATURE_BREAK + pair[1:])
    return out


def escape(text: str) -> str:
    """Plain text -> LaTeX-safe text, with ligatures defused."""
    out = text
    for raw, rep in _ESCAPES:
        out = out.replace(raw, rep)
    return break_ligatures(out)


# Injected just before \begin{document}. Handles the frozen parts of the
# document, which `escape()` never sees.
HARDENING = r"""
%% --- ATS hardening (injected by TempoApply) ---------------------------------
%% Suppress OpenType ligatures so extracted text stays plain ASCII, and stop
%% hyphenation splitting a keyword across two lines.
\usepackage{fontspec}
\defaultfontfeatures{RawFeature={-liga;-clig;-rlig;-dlig;-hlig}}
\hyphenpenalty=10000
\exhyphenpenalty=10000
\sloppy
%% ---------------------------------------------------------------------------
"""


# Injected immediately after \documentclass, before anything else can run.
#
# Resume templates are written for pdfLaTeX and commonly `\input{glyphtounicode}`
# then set `\pdfgentounicode=1` to get a proper ToUnicode map. Those are pdfTeX
# primitives; Tectonic runs XeTeX, where they are undefined and the file will not
# compile at all. Declaring no-op equivalents lets the author's file build
# unchanged — XeTeX writes its own ToUnicode map, so nothing is lost.
ENGINE_COMPAT = r"""
%% --- engine compatibility (injected by TempoApply) --------------------------
\makeatletter
\ifdefined\pdfglyphtounicode\else\def\pdfglyphtounicode#1#2{}\fi
\ifdefined\pdfgentounicode\else\newcount\pdfgentounicode\fi
\ifdefined\pdfcompresslevel\else\newcount\pdfcompresslevel\fi
\ifdefined\pdfobjcompresslevel\else\newcount\pdfobjcompresslevel\fi
\makeatother
%% ---------------------------------------------------------------------------
"""

_DOCUMENTCLASS_RE = re.compile(r"\\documentclass\s*(\[[^\]]*\])?\s*\{[^{}]*\}")


def engine_compat(source: str) -> str:
    """Make a pdfLaTeX-targeted preamble survive XeTeX. Idempotent."""
    if "engine compatibility (injected by TempoApply)" in source:
        return source
    m = _DOCUMENTCLASS_RE.search(source)
    if not m:
        return ENGINE_COMPAT + source
    return source[: m.end()] + "\n" + ENGINE_COMPAT + source[m.end():]


def harden(source: str) -> str:
    """
    Make a document ready to compile under Tectonic and to be read by an ATS.

    Engine compatibility is applied here rather than left to the caller: the
    author's file will not compile at all without it, and a separate step is a
    step someone forgets.

    Idempotent, so it is safe to call on every recompile of the trim loop.
    """
    source = engine_compat(source)
    if "ATS hardening (injected by TempoApply)" in source:
        return source
    marker = r"\begin{document}"
    if marker not in source:
        return source
    return source.replace(marker, HARDENING + marker, 1)


# What a ligature glyph should have been, for auditing a compiled PDF.
LIGATURE_GLYPHS = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st",
}


def normalise_ligatures(text: str) -> str:
    """Undo ligature glyphs in text extracted from a PDF, for keyword matching."""
    for glyph, plain in LIGATURE_GLYPHS.items():
        text = text.replace(glyph, plain)
    return text


def unescape(tex: str) -> str:
    """LaTeX-safe text -> plain text, for the escape-only subset."""
    out = tex
    out = out.replace(r"\textbackslash{}", "\\")
    out = out.replace(r"\textasciitilde{}", "~").replace(r"\textasciicircum{}", "^")
    for raw, rep in _ESCAPES:
        if rep.startswith("\\") and len(rep) == 2:
            out = out.replace(rep, raw)
    # Ligature breaks and empty groups are typesetting artefacts, not part of the
    # sentence the model should see.
    out = out.replace(_LIGATURE_BREAK, "").replace("\\kern0pt", "")
    return out.replace("{}", "")


def is_plain(tex: str) -> bool:
    """True when a span holds prose only, so it is safe to reword."""
    if "$" in tex:                       # inline maths, e.g. $O(\log n)$
        return False
    stripped = _ALLOWED_ESCAPE_RE.sub("", tex)
    return not _ANY_COMMAND_RE.search(stripped)


@dataclass
class Slot:
    """One editable run of prose inside the document."""

    id: str
    kind: str                # bullet | summary | skills
    section: str             # nearest preceding \section
    entry: str               # nearest preceding company/project heading
    text: str                # plain-text form, what the model sees
    raw: str                 # the original LaTeX span
    start: int               # span of the text itself
    end: int
    outer_start: int         # span including \item, so the bullet can be dropped
    outer_end: int
    editable: bool

    @property
    def droppable(self) -> bool:
        return self.kind == "bullet"


@dataclass
class TexDoc:
    source: str
    slots: List[Slot] = field(default_factory=list)

    def slot(self, slot_id: str) -> Optional[Slot]:
        return next((s for s in self.slots if s.id == slot_id), None)

    @property
    def editable_slots(self) -> List[Slot]:
        return [s for s in self.slots if s.editable]

    def render(
        self,
        edits: Optional[Dict[str, str]] = None,
        drop: Optional[Iterable[str]] = None,
    ) -> str:
        """
        Rebuild the document.

        `edits` maps slot id -> new plain text; `drop` removes whole bullets.
        With neither, the result is the original source byte for byte.
        """
        edits = edits or {}
        dropped: Set[str] = set(drop or ())

        # Work through the spans left to right, copying the untouched source
        # between them. Splicing by offset is what guarantees the round trip.
        pieces: List[str] = []
        cursor = 0
        for slot in sorted(self.slots, key=lambda s: s.outer_start):
            if slot.id in dropped and slot.droppable:
                pieces.append(self.source[cursor:slot.outer_start])
                cursor = slot.outer_end
                continue
            if slot.id in edits and slot.editable:
                pieces.append(self.source[cursor:slot.start])
                pieces.append(escape(edits[slot.id]))
                cursor = slot.end
        pieces.append(self.source[cursor:])
        return "".join(pieces)


def _context_at(pos: int, marks: List[tuple[int, str]], after: int = -1) -> str:
    """
    The nearest heading at or before `pos`.

    `after` scopes the search, so an entry heading cannot leak across a section
    boundary — otherwise the Achievements bullets inherit "National Institute of
    Technology" from the Education block above them.
    """
    found = ""
    for at, label in marks:
        if at > pos:
            break
        if at >= after:
            found = label
    return found


# Commands that decorate an entry label rather than name it.
_LABEL_NOISE_RE = re.compile(
    r"\\(?:textbf|textit|emph|underline|texttt|small|large|href|url|textsc)\s*"
)


def label_text(tex: str) -> str:
    """
    Readable name from a heading argument.

    Project headings nest several commands deep —
    `\\textbf{\\href{url}{\\underline{ThrottleX}}} $-$ API Rate Limiting Service` —
    so the URL is dropped and the remaining prose kept.
    """
    out = re.sub(r"\\href\s*\{[^{}]*\}", "", tex)          # drop the URL argument
    out = _LABEL_NOISE_RE.sub(" ", out)
    out = re.sub(r"\\[A-Za-z@]+\s*", " ", out)             # any other command
    out = out.replace("$-$", "-").replace("$", " ")
    out = out.replace("{", " ").replace("}", " ")
    out = re.sub(r"\s+", " ", out).strip(" -")
    return out[:80]


def _find_entries(source: str, in_body) -> List[tuple[int, str]]:
    """Company/project headings, read with brace matching rather than a regex."""
    entries: List[tuple[int, str]] = []
    for m in _ENTRY_MACRO_RE.finditer(source):
        if not in_body(m.start()):
            continue
        open_idx = m.end() - 1
        close_idx = _matching_brace(source, open_idx)
        if close_idx < 0:
            continue
        label = label_text(source[open_idx + 1:close_idx])
        if label:
            entries.append((m.start(), label))
    entries.sort()
    return entries


def _matching_brace(src: str, open_idx: int) -> int:
    """Index just past the brace group opening at `open_idx`, or -1."""
    depth = 0
    i = open_idx
    while i < len(src):
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


_COMMENT_LINE_RE = re.compile(r"(?m)^[ \t]*%[^\n]*\n?")


def _trim_trailing_comments(src: str, start: int, end: int) -> int:
    """Pull `end` back past any whole comment lines at the tail of the span."""
    while end > start:
        tail = src[start:end]
        stripped = tail.rstrip()
        if stripped != tail:                      # drop trailing whitespace first
            end = start + len(stripped)
            continue
        line_start = src.rfind("\n", start, end) + 1
        if line_start <= start:
            break
        line = src[line_start:end]
        if _COMMENT_LINE_RE.fullmatch(line) or line.lstrip().startswith("%"):
            end = line_start
            continue
        break
    return end


def _body_end(src: str, start: int) -> int:
    """
    Where a `\\item` body stops: at the next \\item, the end of the list, or a
    following structural command.
    """
    stops = []
    for pattern in (r"\\item\b", r"\\end\s*\{", r"\\section\b", r"\\subsection\b",
                    r"\\resumeSubheading\b", r"\\role\b", r"\\textbf\b"):
        m = re.search(pattern, src[start:])
        if m:
            stops.append(start + m.start())
    return min(stops) if stops else len(src)


def body_span(source: str) -> tuple[int, int]:
    """
    Where the document's content lives.

    Everything before `\\begin{document}` is preamble, and resume templates
    define their bullet macros there — `\\newcommand{\\resumeItem}[1]{\\item...}`
    contains a literal `\\item`. Scanning the whole file would offer those macro
    definitions up as droppable bullets, and trimming one to save space would
    destroy the document.
    """
    start_marker = "\\begin{document}"
    end_marker = "\\end{document}"
    start = source.find(start_marker)
    if start < 0:
        return 0, len(source)
    start += len(start_marker)
    end = source.find(end_marker, start)
    return start, (end if end >= 0 else len(source))


def parse(source: str) -> TexDoc:
    """Locate the editable prose spans in a LaTeX resume."""
    body_start, body_end = body_span(source)

    def in_body(pos: int) -> bool:
        return body_start <= pos < body_end

    sections = [
        (m.start(), m.group(1).strip())
        for m in _SECTION_RE.finditer(source)
        if in_body(m.start())
    ]
    entries = _find_entries(source, in_body)

    slots: List[Slot] = []
    seen_spans: Set[tuple[int, int]] = set()

    def add(kind: str, outer_start: int, outer_end: int, start: int, end: int) -> None:
        raw = source[start:end]
        if not raw.strip():
            return
        if (start, end) in seen_spans:
            return
        seen_spans.add((start, end))
        # Trailing comment lines must stay outside the span. A slot that runs to
        # the next \section swallows the "% ---- Experience ----" divider above
        # it, and escaping that on re-injection turns `%` into `\%` — printing
        # the comment onto the page as if it were content.
        end = _trim_trailing_comments(source, start, end)
        raw = source[start:end]
        # Keep surrounding whitespace out of the editable span so re-rendering
        # preserves the file's indentation exactly.
        lead = len(raw) - len(raw.lstrip())
        trail = len(raw) - len(raw.rstrip())
        start, end = start + lead, end - trail
        raw = source[start:end]
        if not raw.strip():
            seen_spans.discard((start, end))
            return
        section_at = max((at for at, _ in sections if at <= start), default=-1)
        slots.append(
            Slot(
                id=f"{kind[0]}{len(slots):02d}",
                kind=kind,
                section=_context_at(start, sections),
                entry=_context_at(start, entries, after=section_at),
                text=unescape(raw),
                raw=raw,
                start=start,
                end=end,
                outer_start=outer_start,
                outer_end=outer_end,
                editable=is_plain(raw),
            )
        )

    # Macro bullets first. They are more specific than a bare \item, and the
    # macro expands to one, so claiming their span stops the same bullet being
    # captured twice.
    macro_spans: List[tuple[int, int]] = []
    for m in _MACRO_ITEM_RE.finditer(source):
        if not in_body(m.start()):
            continue
        open_idx = m.end() - 1
        close_idx = _matching_brace(source, open_idx)
        if close_idx < 0:
            continue
        macro_spans.append((m.start(), close_idx + 1))
        add("bullet", m.start(), close_idx + 1, open_idx + 1, close_idx)

    # Plain \item bullets, skipping any span a macro already claimed.
    for m in _ITEM_RE.finditer(source):
        if not in_body(m.start()):
            continue
        if any(a <= m.start() < b for a, b in macro_spans):
            continue
        text_start = m.end()
        text_end = _body_end(source, text_start)
        add("bullet", m.start(), text_end, text_start, text_end)

    # The prose paragraph under a Summary/Objective/Profile section. Leading
    # size commands (`\small`, `\vspace{..}`) belong to the layout, not the
    # sentence — skipping them is what keeps the summary rewritable, and the
    # summary is where transferable framing is allowed to happen.
    for at, title in sections:
        if not re.match(r"(summary|objective|profile|about)", title, re.I):
            continue
        after = source.index("}", at) + 1
        stop = _body_end(source, after)
        # No \A here: `pattern.match(s, pos)` already anchors at pos, whereas \A
        # would anchor to the start of the whole file and never match.
        prose = re.compile(r"(?:\s|\\[A-Za-z@]+\s*(?:\{[^{}]*\})?|%[^\n]*\n)*")
        lead = prose.match(source, after, stop)
        text_start = lead.end() if lead else after
        add("summary", after, stop, text_start, stop)

    slots.sort(key=lambda s: s.start)
    for i, slot in enumerate(slots):
        slot.id = f"{slot.kind[0]}{i:02d}"
    return TexDoc(source=source, slots=slots)


def parse_file(path) -> TexDoc:
    from pathlib import Path

    return parse(Path(path).read_text(encoding="utf-8"))


def plain_text(doc: TexDoc) -> str:
    """Everything the document says, for keyword matching and the guard."""
    body = doc.source
    body = re.sub(r"(?m)^\s*%.*$", " ", body)          # comments
    body = re.sub(r"\\[A-Za-z@]+\s*(\[[^\]]*\])?", " ", body)  # commands
    body = body.replace("{", " ").replace("}", " ").replace("$", " ")
    body = body.replace("\\", " ")
    return re.sub(r"\s+", " ", body).strip()
