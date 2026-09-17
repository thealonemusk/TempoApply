"""
Tests for resume tailoring.

Runnable script rather than pytest, matching `extension/test/run_tests.py` —
this repo has no pytest setup.

    python backend/resume/test_resume.py            # no API key needed
    python backend/resume/test_resume.py --llm      # also exercises the rewrite call

Everything except `--llm` is deterministic and offline, which is deliberate: the
parts that decide what is true (the parser, the guard) and what matters (the
matcher) must be testable without spending money or depending on a model's mood.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.resume import compile as rc  # noqa: E402
from backend.resume import guard as guard_mod  # noqa: E402
from backend.resume import match, texdoc  # noqa: E402

DATA = Path(__file__).resolve().parent / "testdata"
SAMPLE = DATA / "sample_resume.tex"
TEMPLATE = DATA / "template_style.tex"     # Jake's-Resume shape, the real-world case

failures: list[str] = []


def check(name: str, got, want) -> None:
    ok = (want in got) if isinstance(want, str) and isinstance(got, str) and want else got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name:38} {str(got)[:46]!r}")
    if not ok:
        failures.append(f"{name}: expected {want!r}, got {got!r}")


def section(title: str) -> None:
    print(f"\n{title}")


# ── The parser ───────────────────────────────────────────────────────────────

def test_parser() -> texdoc.TexDoc:
    section("Parser — the document must survive a round trip untouched")
    doc = texdoc.parse_file(SAMPLE)
    check("slots found", len(doc.slots) > 8, True)
    check("round trip is byte-identical", doc.render() == doc.source, True)
    check("sections attributed", any(s.section == "Experience" for s in doc.slots), True)
    check("entries attributed", any(s.entry == "Paytm" for s in doc.slots), True)

    # A bullet containing maths must never be offered for rewriting.
    mathy = [s for s in doc.slots if "$" in s.raw]
    check("maths bullet marked non-editable", all(not s.editable for s in mathy), True)
    check("maths bullet still droppable", all(s.droppable for s in mathy), True)
    return doc


def test_escaping() -> None:
    section("Escaping — LaTeX specials must survive a trip through the model")
    for raw in ("traffic & 40% efficiency", "C++ and C#", "a_b {x} 100%", "cost ~$5"):
        check(f"round trip {raw!r}", texdoc.unescape(texdoc.escape(raw)), raw)
    check("ligature pair is broken", "\\kern0pt" in texdoc.escape("traffic"), True)
    check("harden is idempotent",
          texdoc.harden(texdoc.harden("x\\begin{document}y")).count("ATS hardening"), 1)


def test_drop_and_edit(doc: texdoc.TexDoc) -> None:
    section("Rendering — edits and drops")
    bullets = [s for s in doc.slots if s.kind == "bullet" and s.editable]
    target = bullets[0]
    out = doc.render(edits={target.id: "Rewritten bullet with 40% growth & scale."})
    check("edit is applied", out, "Rewritten bullet")
    check("edit is escaped", out, r"40\%")
    check("preamble untouched", out.split("\\begin{document}")[0],
          doc.source.split("\\begin{document}")[0])

    dropped = doc.render(drop={target.id})
    check("dropped text is gone", target.text[:40] not in dropped, True)
    check("other bullets survive", bullets[1].text[:40] in dropped, True)


# ── The real-world template shape ────────────────────────────────────────────

def test_template_style() -> None:
    """Four bugs that only a Jake's-Resume-shaped document exposes."""
    section("Template shape — macro preamble, nested headings, comments")
    doc = texdoc.parse_file(TEMPLATE)
    body_start = doc.source.index("\\begin{document}")

    # 1. Macro definitions contain a literal \item. Offering those as droppable
    #    bullets means the trimmer can delete \newcommand and break everything.
    preamble = [s for s in doc.slots if s.start < body_start]
    check("no slots inside the preamble", preamble, [])

    # 2. Project names are nested three commands deep.
    entries = {s.entry for s in doc.slots}
    check("ThrottleX heading found", "ThrottleX" in entries, True)
    check("OktaDB heading found", "OktaDB" in entries, True)
    check("heading drops the URL", any("example.com" in e for e in entries), False)

    # 3. An entry must not leak into the next section.
    ach = [s for s in doc.slots if s.section.startswith("Achievements")]
    check("achievements do not inherit education", all(not s.entry for s in ach), True)

    # 4. The summary must be rewritable, and must not swallow the comment
    #    divider that follows it.
    summary = [s for s in doc.slots if s.kind == "summary"]
    check("summary slot exists", len(summary), 1)
    check("summary is editable", summary[0].editable, True)
    check("summary excludes the comment", "%" in summary[0].text, False)
    check("summary excludes the \\small", summary[0].text.startswith("Backend engineer"), True)

    check("round trip is byte-identical", doc.render() == doc.source, True)

    # Re-injecting every bullet must leave the comment a comment. If the span
    # had swallowed it, escaping would have produced "\% ---------- Experience".
    edits = {s.id: s.text for s in doc.editable_slots}
    rendered = doc.render(edits=edits)
    check("comment survives as a comment", "\n% ---------- Experience" in rendered, True)
    check("comment was not escaped", "\\% ---------- Experience" in rendered, False)


def test_engine_compat() -> None:
    """pdfTeX-only primitives must not stop XeTeX."""
    section("Engine compatibility — a pdfLaTeX file under Tectonic")
    src = TEMPLATE.read_text(encoding="utf-8")
    check("fixture really uses pdfgentounicode", "\\pdfgentounicode" in src, True)

    prepared = texdoc.harden(src)
    check("compat shim injected", "engine compatibility" in prepared, True)
    check("shim lands after documentclass",
          prepared.index("engine compatibility") > prepared.index("\\documentclass"), True)
    check("harden is idempotent",
          texdoc.harden(prepared).count("engine compatibility"), 1)

    if not rc.is_available():
        print("  SKIP  tectonic not installed")
        return
    audit = rc.compile_tex(prepared, DATA / "template_out.pdf")
    check("pdfLaTeX-targeted file compiles", audit.pages, 1)
    check("text is extractable", audit.chars > 800, True)
    flat = " ".join(audit.text.split())
    check("comment divider is not printed", "---------- Experience" in flat, False)
    check("project name survives", "ThrottleX" in flat, True)


# ── The matcher ──────────────────────────────────────────────────────────────

def test_matching() -> None:
    section("Matching — word boundaries, coverage, ranking")
    check("'go' does not match inside 'google'", match.contains("google cloud", "go"), False)
    check("'go' matches standalone", match.contains("we use go and rust", "go"), True)
    check("'c++' matches", match.contains("strong c++ skills", "c++"), True)
    check("'spring boot' beats 'spring'", "spring boot" in match.find_tech("We use Spring Boot"), True)

    resume = "Built Spring Boot services on AWS with Docker and MySQL."
    cov = match.coverage(resume, ["spring boot", "aws", "kafka", "docker"])
    check("coverage counts matches", len(cov.matched), 3)
    check("coverage counts gaps", cov.missing, ["kafka"])
    check("coverage score", cov.score, 75.0)

    doc = texdoc.parse_file(SAMPLE)
    ranks = match.rank_slots(doc.slots, ["mqtt", "ci/cd", "jenkins"])
    top = max(ranks, key=ranks.get)
    check("most relevant bullet ranks top", ranks[top] > 0, True)
    check("summary is protected from trimming",
          all(ranks[s.id] >= 5.0 for s in doc.slots if s.kind == "summary"), True)


# ── The guard ────────────────────────────────────────────────────────────────

def test_guard() -> None:
    section("Guard — rewrites may reword facts, never add them")
    master = texdoc.plain_text(texdoc.parse_file(SAMPLE))
    gate = guard_mod.Guard(master)

    # Every one of these is a rewording of something the fixture already says.
    allowed = [
        "Migrated device connectivity to TLS over HTTPS/MQTTS for the Indonesia launch.",
        "Improved API response times by 40% through asynchronous processing and caching.",
        "Reduced latency by fixing a memory leak in the messaging client.",
    ]
    refused = [
        ("Built Kafka streaming pipelines.", "technology"),
        ("Led backend development at Google.", "company"),
        ("Enabled 450 production changes.", "inflated number"),
        ("Deployed with Terraform and Helm.", "technology"),
    ]
    for text in allowed:
        check(f"accepts: {text[:34]}", gate.check(text).ok, True)
    for text, why in refused:
        v = gate.check(text)
        check(f"refuses {why}: {text[:26]}", v.ok, False)
        if v.ok:
            failures.append(f"guard let through: {text}")

    accepted, rejected = gate.filter({"b01": allowed[1], "b02": refused[0][0]})
    check("filter keeps the good one", list(accepted), ["b01"])
    check("filter reports the bad one", len(rejected), 1)


# ── Compilation ──────────────────────────────────────────────────────────────

def test_compile() -> None:
    section("Compilation — the PDF an ATS actually reads")
    if not rc.is_available():
        print("  SKIP  tectonic not installed (run scripts/install_tectonic.py)")
        return

    doc = texdoc.parse_file(SAMPLE)
    edits = {
        s.id: s.text for s in doc.editable_slots
    }
    # Words chosen because every one of them contains a ligature pair.
    bullets = [s for s in doc.slots if s.kind == "bullet" and s.editable]
    edits[bullets[0].id] = (
        "Fixed traffic efficiency for the offline fleet, notification workflows "
        "and difficult staff profiling, at 40% lower latency."
    )
    source = texdoc.harden(doc.render(edits=edits))
    audit = rc.compile_tex(source, DATA / "test_out.pdf")

    check("compiles to one page", audit.pages, 1)
    check("text is extractable", audit.chars > 1200, True)
    check("no ligature glyphs", audit.ligatures, [])
    check("no words split by hyphenation", audit.hyphen_splits, [])
    check("no images", audit.images, 0)
    check("no tables", audit.tables, 0)
    check("audit reports it clean", audit.problems(), [])

    flat = " ".join(audit.text.split())
    for word in ("traffic", "efficiency", "offline", "notification", "workflows", "difficult", "staff"):
        check(f"{word!r} extracts as plain ASCII", word in flat, True)

    # A document that cannot build must raise, not return a broken PDF.
    try:
        rc.compile_tex("\\documentclass{article}\\begin{document}\\undefinedmacro\\end{document}",
                       DATA / "broken.pdf")
        failures.append("compile_tex accepted a broken document")
        print("  FAIL  broken LaTeX raises CompileError")
    except rc.CompileError as exc:
        check("broken LaTeX raises CompileError", bool(str(exc)), True)


def test_one_page_fitter() -> None:
    section("One-page fitter — trims the least relevant bullet until it fits")
    if not rc.is_available():
        print("  SKIP  tectonic not installed")
        return
    from backend.resume import tailor

    doc = texdoc.parse_file(SAMPLE)
    # Bloat every bullet so the document cannot possibly fit on one page.
    bloat = {s.id: (s.text + " ") * 6 for s in doc.editable_slots}
    ranks = match.rank_slots(doc.slots, ["mqtt", "jenkins", "ci/cd"])

    audit, dropped, _ = tailor._fit_to_one_page(
        doc, bloat, ranks, DATA / "fitted.pdf", "", max_pages=1
    )
    check("converges to one page", audit.pages, 1)
    check("something was dropped", len(dropped) > 0, True)
    check("summary was not sacrificed",
          all(doc.slot(d).kind != "summary" for d in dropped), True)


# ── Optional: the model ──────────────────────────────────────────────────────

def test_llm() -> None:
    section("Rewrite call (--llm)")
    from backend.resume import llm

    if not llm.is_available():
        print("  SKIP  no usable API key")
        return
    try:
        data = llm.ask_json(
            "You answer with JSON only.",
            'Return {"ok": true, "word": "tailoring"} exactly.',
        )
        check("model returns JSON", data.get("ok"), True)
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL  model call: {str(exc)[:120]}")
        failures.append(f"llm: {exc}")


def main() -> None:
    doc = test_parser()
    test_template_style()
    test_engine_compat()
    test_escaping()
    test_drop_and_edit(doc)
    test_matching()
    test_guard()
    test_compile()
    test_one_page_fitter()
    if "--llm" in sys.argv:
        test_llm()

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S):")
        for line in failures:
            print(f"  - {line}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
