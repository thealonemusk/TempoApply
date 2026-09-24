"""
The fabrication gate.

Prompt instructions are not a control. Told to "optimise for this job
description", a model will eventually write *Built Kafka pipelines* for someone
who has only ever used MQTT, and a resume that wins the keyword scan and loses
the interview is worse than no tailoring at all.

So every rewritten sentence is checked before it is allowed into the PDF. A
rewrite may reorganise, compress and re-word existing facts; it may not
introduce a technology, an organisation or a figure that its source does not
contain. Anything that does is rejected and the original bullet is kept —
silently, so a bad rewrite degrades to no rewrite rather than to a lie.

What "its source" means is the whole point, and the first version got it
wrong. It checked every rewrite against the entire document, and numbers by
substring, so on the real master all of these passed:

  * 40% -> 64% or 97%   ("64" is inside the phone number, "97" in `0.97\\textwidth`)
  * 18 device types -> 8 or 45   (8 and 45 exist elsewhere)
  * 45 changes -> 45M   (the suffix was stripped before comparing)
  * "at Denr Financial Services" on a Paytm bullet
  * "led a team of five", and lowercase "flink" / "bigquery"

So each claim is now checked against the narrowest source that can support it:

  * figures      — the bullet being rewritten, compared as value + unit;
  * number words — the bullet being rewritten ("five", "millions", "dozens");
  * technologies — the bullet's own entry (its heading lists the project's
                   stack), with explicit aliases rather than substrings;
  * names        — the bullet's own entry, including a sentence's first word;
  * job terms    — a capitalised term from the job description that the
                   master never mentions is refused in any casing.

The summary is the one slot allowed to draw on the whole resume, because
summarising the whole resume is its job. Concepts ("distributed systems",
"debugging") are description, not claims, and only need to exist in the master.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from backend.resume import match

# Words that are capitalised for grammar or convention, not because they name
# an organisation or product.
_COMMON_CAPITALS: Set[str] = {
    "i", "a", "the", "an", "and", "or", "but", "for", "with", "from", "to",
    "in", "on", "at", "by", "of", "as", "is", "are", "was", "were", "be",
    "built", "led", "owned", "designed", "developed", "implemented", "created",
    "delivered", "improved", "reduced", "increased", "migrated", "managed",
    "engineered", "architected", "shipped", "drove", "wrote", "added", "fixed",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "present", "current",
    "enabled", "exposed", "measured", "solved", "ranked", "handled", "moved",
    "used", "ran", "set", "made", "cut", "grew", "took", "kept", "brought",
}

# Terms in TECH_VOCAB that describe work rather than name a tool. Saying that
# memory-leak debugging "is debugging" is the rewording the prompt asks for;
# they only have to exist somewhere in the master.
CONCEPTS: Set[str] = {
    "distributed systems", "concurrency", "multithreading", "scalability",
    "high availability", "fault tolerance", "load balancing", "caching",
    "rate limiting", "sharding", "replication", "consistency", "idempotency",
    "observability", "monitoring", "logging", "tracing", "profiling",
    "authentication", "authorization", "encryption", "security", "networking",
    "indexing", "query optimization", "data structures", "algorithms",
    "system design", "design patterns", "oop", "functional programming",
    "unit testing", "integration testing", "tdd", "code review", "agile",
    "scrum", "debugging", "performance tuning", "memory management",
    "microservices", "event-driven", "event driven", "protocol", "embedded",
}

# Names that are the same technology. Explicit, because substring equivalence
# ("known in term") let "javascript" pass for a resume that only says "java".
_ALIASES: Tuple[Set[str], ...] = (
    {"mqtt", "mqtts"},
    {"go", "golang"},
    {"postgres", "postgresql"},
    {"node.js", "nodejs", "node"},
    {"rest", "rest api", "rest apis", "restful"},
    {"event-driven", "event driven"},
    {"b+tree", "btree"},
    {"wal", "write-ahead logging"},
    {"kubernetes", "k8s"},
    {"tls", "ssl"},
    {"ci/cd", "cicd"},
)

# Quantities written as words. "one" is left out: "one of", "one-page".
_NUMBER_WORDS: Set[str] = {
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "hundreds", "thousand",
    "thousands", "million", "millions", "billion", "billions", "dozen",
    "dozens", "lakh", "lakhs", "crore", "crores", "double", "doubled",
    "triple", "tripled", "tenfold",
}

# A figure: digits (with thousands separators or a decimal part) and an
# optional unit. Not preceded by a letter, so S3, EC2 and B+Tree are names.
_FIGURE_RE = re.compile(
    r"(?<![A-Za-z0-9.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
    r"\s*(%|x(?![a-z0-9])|k(?![a-z])|mn(?![a-z])|m(?![a-z])|bn(?![a-z])|b(?![a-z])"
    r"|ms(?![a-z])|s(?![a-z])|gb|mb|kb|tb|million|billion|thousand|lakh|crore)?",
    re.I,
)
_SCALE = {
    "k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9, "lakh": 1e5, "crore": 1e7,
    "ms": 1e-3, "s": 1.0, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12,
}
_UNIT_CLASS = {
    "%": "percent", "x": "multiple",
    "ms": "time", "s": "time",
    "kb": "size", "mb": "size", "gb": "size", "tb": "size",
}


def figures(text: str) -> Set[Tuple[float, str]]:
    """
    Every figure as (value, kind). "1,500" and "1.5k" are the same claim;
    "45" and "45M" are not, and neither are "40%" and "40".
    """
    out: Set[Tuple[float, str]] = set()
    for m in _FIGURE_RE.finditer(text or ""):
        value = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        out.add((round(value * _SCALE.get(unit, 1.0), 6), _UNIT_CLASS.get(unit, "count")))
    return out


def _without_figures(text: str) -> str:
    return _FIGURE_RE.sub(" ", text or "")


def number_words(text: str) -> Set[str]:
    words = re.findall(r"[a-z]+", _without_figures(text).lower())
    return {w for w in words if w in _NUMBER_WORDS}


@dataclass
class Verdict:
    """Why a rewrite was accepted or refused."""

    ok: bool
    new_tech: List[str] = field(default_factory=list)
    new_entities: List[str] = field(default_factory=list)
    new_numbers: List[str] = field(default_factory=list)

    def reason(self) -> str:
        parts = []
        if self.new_tech:
            parts.append(f"technology not in your resume: {', '.join(self.new_tech)}")
        if self.new_entities:
            parts.append(f"name not in your resume: {', '.join(self.new_entities)}")
        if self.new_numbers:
            parts.append(f"figure not in your resume: {', '.join(self.new_numbers)}")
        return "; ".join(parts)


def _looks_like_starter(word: str) -> bool:
    """A sentence's first word that is a verb, not a name: "Reduced", "Scaling"."""
    return bool(re.fullmatch(r"[A-Z][a-z]+(ed|ing|es)", word))


def _entities(text: str) -> Set[str]:
    """Capitalised words that look like a product, company or technology."""
    out: Set[str] = set()
    for sentence in re.split(r"(?<=[.!?;:])\s+", text or ""):
        words = re.findall(r"\b[A-Za-z][A-Za-z0-9+#.&/-]*\b", sentence)
        for i, word in enumerate(words):
            if not word[:1].isupper():
                continue
            if word.lower() in _COMMON_CAPITALS:
                continue
            # The first word of a sentence used to be skipped outright, which
            # let "Stripe integrations shipped…" and "Google-scale…" through.
            # It is skipped only when it reads as a verb.
            if i == 0 and _looks_like_starter(word):
                continue
            out.add(word.strip(".-/").lower())
    return out


def _alias_group(term: str) -> Set[str]:
    group = next((g for g in _ALIASES if term in g), {term})
    # "distributed-systems engineer" evidences "distributed systems".
    return group | {t.replace(" ", "-") for t in group} | {t.replace("-", " ") for t in group}


def jd_terms(jd_text: str) -> Set[str]:
    """
    Proper names in a job description: capitalised mid-sentence, CamelCase or
    ALLCAPS. The model's usual invention is a term copied from the posting, so
    such a term is refused in any casing if the master never mentions it.
    """
    out: Set[str] = set()
    # A product is capitalised every time; "Platform" in a title-cased heading
    # is ordinary English if the posting also says "platform" somewhere.
    lowercase_uses = set(re.findall(r"\b[a-z][a-z0-9+#.-]*\b", jd_text or ""))
    for sentence in re.split(r"(?<=[.!?;:\n])\s+", jd_text or ""):
        words = re.findall(r"\b[A-Za-z][A-Za-z0-9+#.-]*\b", sentence)
        for i, word in enumerate(words):
            camel = bool(re.search(r"[a-z][A-Z]", word))
            caps = len(word) >= 2 and word.isupper()
            if camel or caps or (i > 0 and word[:1].isupper()):
                w = word.strip(".-").lower()
                if w not in _COMMON_CAPITALS and len(w) > 1 and w not in lowercase_uses:
                    out.add(w)
    return out


class Guard:
    """Holds everything the master document is allowed to say."""

    def __init__(
        self,
        master_text: str,
        extra_allowed: Iterable[str] = (),
        jd_text: str = "",
        master_figures_text: Optional[str] = None,
    ) -> None:
        self.master_text = master_text
        self._blob = match.normalise(master_text)
        self._tech = set(match.find_tech(master_text))
        self._entities = _entities(master_text)
        # Figures the summary may draw on. The caller passes the prose only —
        # the whole source also holds the phone number and layout lengths.
        self._figures = figures(master_figures_text if master_figures_text is not None else master_text)
        self._number_words = number_words(master_figures_text or master_text)
        self._extra = {t.lower() for t in extra_allowed}
        self._jd_terms = {t for t in jd_terms(jd_text) if not match.contains(self._blob, t)}

    # ── scope-aware membership ──────────────────────────────────────────────

    @staticmethod
    def _tech_in(term: str, blob: str, known: Set[str]) -> bool:
        return any(alias in known or match.contains(blob, alias) for alias in _alias_group(term))

    def check(
        self,
        rewritten: str,
        source: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Verdict:
        """
        Is this sentence supported?

        `source` is the text being rewritten and `context` the entry it sits in
        (its heading and sibling bullets). Without them the check is against
        the whole master — right for the summary, and for callers that have
        no slot to scope to.
        """
        scoped = source is not None
        ctx_text = context if context is not None else (source if scoped else self.master_text)
        ctx_blob = match.normalise(ctx_text)
        ctx_tech = set(match.find_tech(ctx_text))
        ctx_entities = _entities(ctx_text)

        new_tech: List[str] = []
        for term in match.find_tech(rewritten):
            if term.lower() in self._extra:
                continue
            if term in CONCEPTS:
                if not self._tech_in(term, self._blob, self._tech):
                    new_tech.append(term)
            elif not self._tech_in(term, ctx_blob, ctx_tech):
                new_tech.append(term)

        tech_words = {w for term in new_tech for w in term.split()}
        new_entities = sorted(
            e for e in _entities(rewritten)
            if e not in self._extra and e not in tech_words and e not in new_tech
            and not (e in ctx_entities or match.contains(ctx_blob, e))
        )
        # A term lifted from the posting, in whatever casing the model chose.
        words = {w.strip(".-").lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]*", rewritten)}
        new_entities += sorted(w for w in words & self._jd_terms
                               if w not in new_entities and w not in self._extra)

        allowed_figures = figures(source) if scoped else self._figures
        allowed_words = number_words(source) if scoped else self._number_words
        new_numbers = sorted(
            _describe(f) for f in figures(rewritten) if f not in allowed_figures
        ) + sorted(w for w in number_words(rewritten) if w not in allowed_words)

        return Verdict(
            ok=not (new_tech or new_entities or new_numbers),
            new_tech=sorted(set(new_tech)),
            new_entities=new_entities,
            new_numbers=new_numbers,
        )

    def filter(
        self,
        rewrites: Dict[str, str],
        scopes: Optional[Dict[str, Tuple[Optional[str], Optional[str]]]] = None,
    ) -> tuple[Dict[str, str], List[Dict[str, str]]]:
        """
        Split proposed rewrites into the accepted ones and the refusals.
        `scopes` maps slot id -> (source, context); a slot absent from it is
        checked against the whole master.
        """
        scopes = scopes or {}
        accepted: Dict[str, str] = {}
        rejected: List[Dict[str, str]] = []
        for slot_id, text in rewrites.items():
            source, context = scopes.get(slot_id, (None, None))
            verdict = self.check(text, source=source, context=context)
            if verdict.ok:
                accepted[slot_id] = text
            else:
                rejected.append({
                    "slot": slot_id,
                    "text": text,
                    "reason": verdict.reason(),
                })
        return accepted, rejected


def _describe(fig: Tuple[float, str]) -> str:
    value, kind = fig
    shown = f"{value:g}"
    return {"percent": f"{shown}%", "multiple": f"{shown}x"}.get(kind, shown)
