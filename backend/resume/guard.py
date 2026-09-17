"""
The fabrication gate.

Prompt instructions are not a control. Told to "optimise for this job
description", a model will eventually write *Built Kafka pipelines* for someone
who has only ever used MQTT, and a resume that wins the keyword scan and loses
the interview is worse than no tailoring at all.

So every rewritten sentence is checked against the master document before it is
allowed into the PDF. A rewrite may reorganise, compress and re-word existing
facts; it may not introduce a technology, an organisation or a number that the
master does not contain. Anything that does is rejected and the original bullet
is kept — silently, so a bad rewrite degrades to no rewrite rather than to a
lie.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Set

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
}

# Number-like tokens that are units or ordinals rather than claims.
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*\s*(?:%|k|m|b|x|ms|s|gb|mb|kb)?", re.I)


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


def _entities(text: str) -> Set[str]:
    """Capitalised words that look like a product, company or technology."""
    out: Set[str] = set()
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        words = re.findall(r"\b[A-Za-z][A-Za-z0-9+#.&/-]*\b", sentence)
        for i, word in enumerate(words):
            if not word[:1].isupper():
                continue
            if i == 0:                        # sentence-initial capital proves nothing
                continue
            if word.lower() in _COMMON_CAPITALS:
                continue
            out.add(word.strip(".-/").lower())
    return out


def _numbers(text: str) -> Set[str]:
    return {
        m.group(0).replace(" ", "").lower().rstrip(".")
        for m in _NUMBER_RE.finditer(text)
    }


class Guard:
    """Holds everything the master document is allowed to say."""

    def __init__(self, master_text: str, extra_allowed: Iterable[str] = ()) -> None:
        self.master_text = master_text
        self._blob = match.normalise(master_text)
        self._tech = set(match.find_tech(master_text))
        self._entities = _entities(master_text)
        self._numbers = _numbers(master_text)
        self._extra = {t.lower() for t in extra_allowed}

    def _known_tech(self, term: str) -> bool:
        term = term.lower()
        if term in self._tech or term in self._extra or match.contains(self._blob, term):
            return True
        # A resume saying "MQTTS" evidences "MQTT"; "golang" evidences "go".
        # Word-boundary matching alone would treat the shorter name as invented.
        return any(
            term in known or known in term
            for known in self._tech
            if len(known) > 2 and len(term) > 2
        )

    def _known_entity(self, word: str) -> bool:
        return (
            word in self._entities
            or word in self._extra
            or match.contains(self._blob, word)
        )

    def _known_number(self, num: str) -> bool:
        if num in self._numbers:
            return True
        # "25M" and "25 million" are the same claim; so are "40%" and "40".
        bare = num.rstrip("%kmbxs").rstrip()
        return any(bare and bare in known for known in self._numbers)

    def check(self, rewritten: str) -> Verdict:
        """Is this sentence supported by the master document?"""
        new_tech = sorted(t for t in match.find_tech(rewritten) if not self._known_tech(t))
        # A term already reported as an unknown technology should not be listed
        # again as an unknown name.
        tech_words = {w for term in new_tech for w in term.split()}
        new_entities = sorted(
            e for e in _entities(rewritten)
            if not self._known_entity(e) and e not in tech_words and e not in new_tech
        )
        new_numbers = sorted(n for n in _numbers(rewritten) if not self._known_number(n))
        return Verdict(
            ok=not (new_tech or new_entities or new_numbers),
            new_tech=new_tech,
            new_entities=new_entities,
            new_numbers=new_numbers,
        )

    def filter(self, rewrites: Dict[str, str]) -> tuple[Dict[str, str], List[Dict[str, str]]]:
        """Split proposed rewrites into the accepted ones and the refusals."""
        accepted: Dict[str, str] = {}
        rejected: List[Dict[str, str]] = []
        for slot_id, text in rewrites.items():
            verdict = self.check(text)
            if verdict.ok:
                accepted[slot_id] = text
            else:
                rejected.append({
                    "slot": slot_id,
                    "text": text,
                    "reason": verdict.reason(),
                })
        return accepted, rejected
