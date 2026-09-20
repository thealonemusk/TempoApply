"""
Keyword extraction and coverage scoring — the deterministic half of tailoring.

Everything here runs without an API key, which is deliberate: the gap report is
the part the user acts on, so it must be explainable and reproducible rather
than whatever a model felt like saying. The LLM only rewrites sentences; the
decisions about *what* is missing and *which* bullets matter are made here.

Word-boundary matching reuses the idea already proven in
`backend/scrapers/filter_utils.py:_contains_marker` — a plain `in` test matches
"go" inside "google" and "R" inside every sentence, which wrecks skill matching.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# Technologies worth matching on. Ordered longest-first at match time so
# "spring boot" wins over "spring" and "ci/cd" is not split.
TECH_VOCAB: Tuple[str, ...] = (
    # languages
    "java", "python", "c++", "c#", "golang", "go", "rust", "kotlin", "scala",
    "javascript", "typescript", "sql", "bash", "shell", "c",
    # backend / frameworks
    "spring boot", "spring", "hibernate", "jpa", "node.js", "express", "django",
    "flask", "fastapi", "grpc", "graphql", "rest api", "rest apis", "rest",
    "microservices", "soa", "api gateway", "event-driven", "event driven",
    # data
    "mysql", "postgresql", "postgres", "mongodb", "redis", "cassandra",
    "dynamodb", "elasticsearch", "kafka", "rabbitmq", "mqtt", "mqtts",
    "sqlite", "oracle", "snowflake", "spark", "hadoop", "airflow",
    # cloud / infra
    "aws", "azure", "gcp", "ec2", "s3", "lambda", "eks", "ecs", "iot core",
    "docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins",
    "ci/cd", "github actions", "gitlab", "linux", "unix", "nginx",
    "prometheus", "grafana", "kibana", "datadog", "helm",
    # concepts
    "distributed systems", "concurrency", "multithreading", "scalability",
    "high availability", "fault tolerance", "load balancing", "caching",
    "rate limiting", "sharding", "replication", "consistency", "idempotency",
    "observability", "monitoring", "logging", "tracing", "profiling",
    "tls", "ssl", "oauth", "jwt", "authentication", "authorization",
    "encryption", "security", "networking", "tcp", "http", "https",
    "websocket", "b+tree", "btree", "write-ahead logging", "wal",
    "indexing", "query optimization", "data structures", "algorithms",
    "system design", "design patterns", "oop", "functional programming",
    "unit testing", "integration testing", "tdd", "code review", "agile",
    "scrum", "git", "debugging", "performance tuning", "memory management",
    "firmware", "embedded", "rtos", "ota", "protocol",
    # ai
    "machine learning", "llm", "rag", "mcp", "openai", "pytorch", "tensorflow",
)

_VOCAB_BY_LENGTH: Tuple[str, ...] = tuple(sorted(TECH_VOCAB, key=len, reverse=True))

# Words that look like requirements but carry no signal for matching.
STOPWORDS: Set[str] = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "have",
    "this", "that", "from", "they", "their", "them", "has", "had", "been",
    "were", "was", "who", "what", "when", "where", "which", "while", "would",
    "should", "could", "can", "may", "must", "into", "over", "under", "about",
    "across", "within", "using", "work", "working", "team", "teams", "role",
    "job", "company", "candidate", "candidates", "experience", "experienced",
    "years", "year", "strong", "good", "great", "excellent", "ability", "able",
    "knowledge", "skills", "skill", "required", "requirements", "preferred",
    "plus", "bonus", "responsibilities", "qualifications", "including",
    "etc", "new", "well", "help", "build", "building", "develop", "developing",
    "please", "apply", "opportunity", "benefits", "salary", "position",
}


# Job descriptions arrive from the scrapers with markup residue in them — the
# LinkedIn guest API returns escaped HTML. Left in, "div", "nbsp" and "href"
# rank as some of the employer's most frequent words.
_HTML_TAG_RE = re.compile(r"<[^>]{0,200}>")
_HTML_ENTITY_RE = re.compile(r"&(?:[a-z]{2,10}|#\d{1,5}|#x[0-9a-f]{1,4});", re.I)
_MARKUP_WORDS = {
    "div", "span", "href", "nbsp", "amp", "quot", "apos", "lt", "gt", "br",
    "ul", "li", "ol", "strong", "em", "class", "style", "rel", "nofollow",
    "target", "blank", "http", "https", "www", "com", "html", "utm",
}

# Markup residue must never surface as a "keyword the employer used". This only
# affects the frequency list; TECH_VOCAB matching is unaffected, so a genuine
# mention of HTTPS in a resume still counts as a technology.
STOPWORDS |= _MARKUP_WORDS


def strip_markup(text: str) -> str:
    """Remove HTML tags and entities left behind by the scrapers."""
    text = _HTML_TAG_RE.sub(" ", text or "")
    return _HTML_ENTITY_RE.sub(" ", text)


def normalise(text: str) -> str:
    """Lowercase, collapse whitespace, and undo PDF ligature glyphs."""
    from backend.resume.texdoc import normalise_ligatures

    text = normalise_ligatures(strip_markup(text or ""))
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = text.replace("˜", "~").replace("’", "'")
    return re.sub(r"\s+", " ", text).strip().lower()


def contains(haystack: str, needle: str) -> bool:
    """
    Word-boundary containment that survives '+' and '.' in technology names.

    `"go" in "google"` is True and useless; this is not.
    """
    if not needle:
        return False
    pattern = re.escape(needle)
    return bool(re.search(rf"(?<![a-z0-9+#.]){pattern}(?![a-z0-9+#])", haystack))


def find_tech(text: str) -> List[str]:
    """Technologies from the vocabulary that genuinely appear in `text`."""
    blob = normalise(text)
    found: List[str] = []
    claimed = ""
    for term in _VOCAB_BY_LENGTH:
        if contains(blob, term):
            # Skip a term already covered by a longer one ("spring" inside
            # "spring boot") so the report does not double-count.
            if any(term in longer and term != longer for longer in found):
                continue
            found.append(term)
    return sorted(found)


def keywords(text: str, limit: int = 40) -> List[str]:
    """
    Salient non-vocabulary terms, for JD language the vocabulary does not cover.

    Frequency-ranked, stopword-filtered, capped.
    """
    blob = normalise(text)
    tokens = re.findall(r"[a-z][a-z0-9+#./-]{2,}", blob)
    counts = Counter(t.strip(".-/") for t in tokens if t not in STOPWORDS)
    return [w for w, _ in counts.most_common(limit) if len(w) > 2 and w not in STOPWORDS]


@dataclass
class Coverage:
    """How well a document answers a job description."""

    matched: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    score: float = 0.0

    @property
    def total(self) -> int:
        return len(self.matched) + len(self.missing)

    def as_dict(self) -> Dict[str, object]:
        return {
            "score": self.score,
            "matched": self.matched,
            "missing": self.missing,
            "total": self.total,
        }


def coverage(resume_text: str, required: Sequence[str]) -> Coverage:
    """Which of the JD's requirements the resume actually evidences."""
    blob = normalise(resume_text)
    matched = [term for term in required if contains(blob, normalise(term))]
    missing = [term for term in required if term not in matched]
    score = round(100.0 * len(matched) / len(required), 1) if required else 0.0
    return Coverage(matched=matched, missing=missing, score=score)


def rank_slots(
    slots: Iterable,
    required: Sequence[str],
    nice_to_have: Sequence[str] = (),
) -> Dict[str, float]:
    """
    Score each slot by how much JD-relevant evidence it carries.

    Drives two things: the order bullets are offered to the model, and which
    bullet is sacrificed first when the resume overflows one page.
    """
    scores: Dict[str, float] = {}
    for slot in slots:
        blob = normalise(slot.text)
        hits = sum(3.0 for term in required if contains(blob, normalise(term)))
        hits += sum(1.0 for term in nice_to_have if contains(blob, normalise(term)))
        # A bullet carrying a measured outcome is worth keeping over one that does not.
        if re.search(r"\d+\s*(%|x\b|million|m\b|k\b|ms\b|s\b|gb|mb)", blob):
            hits += 1.5
        if slot.kind == "summary":
            hits += 5.0          # never the first thing dropped
        scores[slot.id] = round(hits, 2)
    return scores


def gap_report(
    before_text: str,
    after_text: str,
    required: Sequence[str],
    nice_to_have: Sequence[str] = (),
) -> Dict[str, object]:
    """Before/after coverage, which is the number the user actually cares about."""
    before = coverage(before_text, required)
    after = coverage(after_text, required)
    before_nice = coverage(before_text, nice_to_have) if nice_to_have else Coverage()
    after_nice = coverage(after_text, nice_to_have) if nice_to_have else Coverage()
    return {
        "required": {
            "before": before.as_dict(),
            "after": after.as_dict(),
            "gained": [t for t in after.matched if t not in before.matched],
            "still_missing": after.missing,
        },
        "nice_to_have": {
            "before": before_nice.as_dict(),
            "after": after_nice.as_dict(),
            "gained": [t for t in after_nice.matched if t not in before_nice.matched],
        },
        "delta": round(after.score - before.score, 1),
    }
