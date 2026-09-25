/**
 * Paste this into the DevTools console on the application step that is not
 * filling, then paste the output back.
 *
 * It exists because the repeating-section support was built against a fixture
 * written from assumed Workday markup — the real step sits behind a per-employer
 * login, so the automation ids it actually uses have never been observed. This
 * reports exactly what the extension looks for and what is really there, which
 * is the difference between fixing the bug and guessing at it again.
 *
 * It mirrors the label, value and section rules in extension/src/scrape.js, so
 * the "label=" and "value=" it prints are what the backend would be asked
 * about — including the verdict the resolver would reach before any widget is
 * touched (SKIP: already filled / no section / no answer).
 *
 * Despite the filename it is not Workday-specific; run it on any portal.
 *
 * Read-only. It fills nothing, clicks nothing, and sends nothing anywhere.
 */
(() => {
  const out = [];
  const say = (s) => out.push(s);
  const clean = (s) => (s || "").replace(/\s+/g, " ").replace(/\*/g, " ").trim();
  const q = (s, n) => JSON.stringify((s || "").slice(0, n || 44));

  // ── mirrors of scrape.js ───────────────────────────────────────────────────

  const PLACEHOLDER_TEXT = new Set([
    "", "-", "--", "select", "select one", "select...", "select an option",
    "please select", "choose", "choose one", "choose...", "none", "n/a",
    "select a value", "search", "type to search",
  ]);
  const isPlaceholder = (t) => PLACEHOLDER_TEXT.has(clean(t).toLowerCase());

  const WORKDAY_FORM_FIELD = '[data-automation-id*="formField"], [data-automation-id*="FormField"]';

  const SECTION_PATTERNS = [
    [/^workExperience-(\d+)$/i, "experience"],
    [/^work-experience-(\d+)$/i, "experience"],
    [/^education-(\d+)$/i, "education"],
    [/^websitePanelSet-(\d+)$/i, "website"],
    [/^website-(\d+)$/i, "website"],
    [/^websiteSection-(\d+)$/i, "website"],
  ];

  const REPEATING_LABELS = [
    [/^job\s*title$/i, "experience"],
    [/^company$/i, "experience"],
    [/^role\s*description$/i, "experience"],
    [/^(work\s*)?location$/i, "experience"],
    [/^from$/i, "experience"],
    [/^to$/i, "experience"],
    [/currently\s+work\s+here/i, "experience"],
    [/^school(\s+or\s+university)?$/i, "education"],
    [/^degree$/i, "education"],
    [/^field\s*of\s*study$/i, "education"],
    [/^overall\s+result/i, "education"],
    [/^url$/i, "website"],
    [/^website$/i, "website"],
  ];

  function labelFromAria(el) {
    const aria = el.getAttribute("aria-label");
    if (aria) return aria;
    const ref = el.getAttribute("aria-labelledby");
    if (ref) {
      const text = ref
        .split(/\s+/)
        .map((id) => {
          const node = document.getElementById(id);
          return node ? node.innerText : "";
        })
        .filter(Boolean)
        .join(" ");
      if (text) return text;
    }
    return "";
  }

  function wrapperFor(el) {
    return el.closest(
      [
        WORKDAY_FORM_FIELD, "fieldset", ".field", ".form-field",
        ".application-question", '[class*="question"]', '[class*="FormField"]',
        '[data-test*="question"]', '[class*="form-group"]', "label",
      ].join(", ")
    );
  }

  const BARE_DATE_LABEL = /^(month|year|day|mm|yy|yyyy)$/i;
  const DATE_GROUP_RE = /\b(from|to|start|end|through)\b/i;

  function qualifyDateLabel(el, label) {
    if (!BARE_DATE_LABEL.test(clean(label))) return label;
    let node = el.parentElement;
    for (let i = 0; i < 6 && node; i += 1) {
      const heading = node.querySelector(
        "legend, [data-automation-id$='label'], [data-automation-id$='Label'], label"
      );
      for (const text of [heading ? clean(heading.innerText) : "", clean(labelFromAria(node))]) {
        if (text && !BARE_DATE_LABEL.test(text) && DATE_GROUP_RE.test(text)) {
          return `${text} ${clean(label)}`;
        }
      }
      node = node.parentElement;
    }
    return label;
  }

  function baseLabelFor(el) {
    const aria = labelFromAria(el);
    if (clean(aria)) return clean(aria);
    if (el.labels && el.labels.length) {
      const text = clean(el.labels[0].innerText);
      if (text) return text;
    }
    if (el.id) {
      let node = null;
      try {
        node = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      } catch (e) {
        node = null;
      }
      if (node) {
        const text = clean(node.innerText);
        if (text) return text;
      }
    }
    const wrap = wrapperFor(el);
    if (wrap) {
      const node = wrap.querySelector(
        'label, legend, [data-automation-id$="label"], [data-automation-id$="Label"], [class*="label"]'
      );
      if (node && node !== el && !node.contains(el)) {
        const text = clean(node.innerText);
        if (text) return text;
      }
      const first = clean((wrap.innerText || "").split("\n")[0]);
      if (first) return first.slice(0, 180);
    }
    return clean(el.placeholder || el.getAttribute("data-automation-id") || el.name || "");
  }

  const labelFor = (el) => qualifyDateLabel(el, baseLabelFor(el));

  function groupLabelFor(el) {
    const fieldset = el.closest("fieldset");
    if (fieldset) {
      const legend = fieldset.querySelector("legend");
      if (legend) {
        const text = clean(legend.innerText);
        if (text) return text;
      }
    }
    const group = el.closest('[role="radiogroup"], [role="group"]');
    if (group) {
      const aria = clean(labelFromAria(group));
      if (aria) return aria;
    }
    const wrap = el.closest(
      `${WORKDAY_FORM_FIELD}, .application-question, [class*="question"], .field, .form-field`
    );
    if (wrap) {
      const node = wrap.querySelector('label, legend, [data-automation-id$="label"]');
      if (node && !node.contains(el)) {
        const text = clean(node.innerText);
        if (text) return text;
      }
      const first = clean((wrap.innerText || "").split("\n")[0]);
      if (first) return first.slice(0, 180);
    }
    return "";
  }

  function optionLabelFor(el) {
    if (el.labels && el.labels.length) {
      const text = clean(el.labels[0].innerText);
      if (text) return text;
    }
    if (el.id) {
      try {
        const node = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
        if (node) {
          const text = clean(node.innerText);
          if (text) return text;
        }
      } catch (e) {
        /* ignore malformed ids */
      }
    }
    const aria = clean(labelFromAria(el));
    if (aria) return aria;
    const parent = el.closest("label");
    if (parent) {
      const text = clean(parent.innerText);
      if (text) return text;
    }
    return "";
  }

  function sectionFor(el) {
    let node = el;
    while (node && node !== document.documentElement) {
      const auto = node.getAttribute && node.getAttribute("data-automation-id");
      if (auto) {
        for (const [pattern, kind] of SECTION_PATTERNS) {
          const m = auto.match(pattern);
          if (m) return { kind, index: parseInt(m[1], 10) || 1, via: auto };
        }
      }
      node = node.parentElement;
    }
    return { kind: "", index: 0, via: "" };
  }

  function repeatingKind(label) {
    const text = clean(label);
    for (const [pattern, kind] of REPEATING_LABELS) {
      if (pattern.test(text)) return kind;
    }
    return "";
  }

  const isVisible = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  // ── report ─────────────────────────────────────────────────────────────────

  const ids = [...document.querySelectorAll("[data-automation-id]")].map((el) =>
    el.getAttribute("data-automation-id")
  );
  const unique = [...new Set(ids)];

  say(`URL: ${location.href.slice(0, 120)}`);
  say(`title: ${document.title.slice(0, 90)}`);
  say(`frames: ${window.top === window ? "top" : "IFRAME"} | distinct data-automation-id: ${unique.length}`);

  say("\n--- ENTRY CONTAINERS the extension looks for ---");
  let matched = 0;
  for (const [re, kind] of SECTION_PATTERNS) {
    const hits = unique.filter((id) => re.test(id));
    if (hits.length) {
      matched += hits.length;
      say(`  MATCH ${kind}: ${hits.join(", ")}`);
    }
  }
  if (!matched) say("  none matched — entry numbering falls back to page order");

  say("\n--- ids that look like repeating entries (name + number) ---");
  const numbered = unique.filter((id) => /[-_]\d+$/.test(id));
  say(numbered.length ? "  " + numbered.slice(0, 40).join("\n  ") : "  none");

  say("\n--- section / panel ids ---");
  say(
    "  " +
      (unique.filter((id) => /section|panel|group/i.test(id)).slice(0, 30).join("\n  ") || "none")
  );

  say("\n--- Add buttons (nothing can be filled in a block that is not open) ---");
  const buttons = [...document.querySelectorAll('button, [role="button"], a[role="button"]')]
    .filter((b) => /add/i.test(clean(b.innerText) + " " + (b.getAttribute("aria-label") || "")))
    .slice(0, 12);
  buttons.forEach((b) =>
    say(
      `  vis=${isVisible(b) ? "y" : "n"} text=${q(clean(b.innerText), 26)} ` +
        `aria=${q(b.getAttribute("aria-label") || "", 26)} auto=${q(b.getAttribute("data-automation-id") || "", 30)}`
    )
  );
  if (!buttons.length) say("  none found");

  // Every control, with the label AND value the scraper would send, the entry
  // it would be tagged with, and the verdict the resolver would reach. A field
  // whose value is read as already-set is skipped before any widget opens —
  // that is invisible from the page, and is what this line is for.
  say("\n--- CONTROLS: what the extension would send, and what it would do ---");
  const controls = [
    ...document.querySelectorAll(
      'input:not([type="hidden"]), textarea, select, [role="combobox"],' +
        ' [data-automation-id="multiSelectContainer"], [data-automation-id="selectWidget"],' +
        ' button[aria-haspopup="listbox"], button[aria-haspopup="true"], .select__control'
    ),
  ].filter(isVisible);

  const orderCounts = new Map();
  controls.forEach((el, i) => {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute("type") || (tag === "select" ? "select-one" : tag) || "").toLowerCase();
    const isChoice = type === "radio" || type === "checkbox";
    const isNative = tag === "input" || tag === "textarea" || tag === "select";

    const label = isChoice ? groupLabelFor(el) || optionLabelFor(el) : labelFor(el);
    const optLabel = isChoice ? optionLabelFor(el) : "";
    const grpLabel = isChoice ? groupLabelFor(el) : "";
    const rawValue = isNative ? clean(el.value || "") : clean(el.innerText || el.textContent || "");
    const value = isChoice ? "" : isNative ? rawValue : isPlaceholder(rawValue) ? "" : rawValue;

    let sec = sectionFor(el);
    let via = sec.kind ? `id:${sec.via}` : "";
    if (!sec.kind) {
      const kind = repeatingKind(label);
      if (kind) {
        const key = `${kind}|${clean(label).toLowerCase()}`;
        const seen = (orderCounts.get(key) || 0) + 1;
        orderCounts.set(key, seen);
        sec = { kind, index: seen };
        via = "order";
      }
    }

    let verdict = "resolve";
    if (value && !isChoice) verdict = "SKIP: already filled";
    else if (isChoice && el.checked) verdict = "SKIP: already checked";

    say(
      `  [${String(i).padStart(2)}] ${tag}/${type} auto=${q(el.getAttribute("data-automation-id") || "", 30)}`
    );
    say(
      `       label=${q(label)} value=${q(value, 30)} placeholder=${q(el.getAttribute("placeholder") || "", 20)}`
    );
    if (isChoice) say(`       checked=${!!el.checked} optionLabel=${q(optLabel)} groupLabel=${q(grpLabel)}`);
    say(
      `       section=${sec.kind ? `${sec.kind}#${sec.index} (${via})` : "NONE — flat resolver"}` +
        ` role=${q(el.getAttribute("role") || "", 14)} -> ${verdict}`
    );
  });
  if (!controls.length) say("  no visible controls found — wrong frame?");

  // The three widgets that are reported as not working, in detail.
  say("\n--- SKILLS widget ---");
  const skillHosts = [...document.querySelectorAll("*")].filter((el) => {
    const blob = `${el.getAttribute && el.getAttribute("data-automation-id")} ${el.id}`.toLowerCase();
    return /skill/.test(blob);
  });
  if (!skillHosts.length) say("  nothing with 'skill' in its id/automation-id");
  skillHosts.slice(0, 8).forEach((el) =>
    say(
      `  <${el.tagName.toLowerCase()}> auto=${q(el.getAttribute("data-automation-id") || "", 34)} ` +
        `id=${q(el.id, 24)} role=${q(el.getAttribute("role") || "", 12)} ` +
        `haspopup=${q(el.getAttribute("aria-haspopup") || "", 10)} vis=${isVisible(el) ? "y" : "n"}\n` +
        `       text=${q(clean(el.innerText), 60)} inputs-inside=${el.querySelectorAll("input").length}`
    )
  );

  say("\n--- DATE inputs (From / To) ---");
  const dateHosts = controls.filter((el) => {
    const blob = `${labelFor(el)} ${el.getAttribute("data-automation-id") || ""} ${el.getAttribute("placeholder") || ""}`;
    return /from|to\b|date|month|year|mm|yyyy/i.test(blob);
  });
  if (!dateHosts.length) say("  none matched");
  dateHosts.slice(0, 12).forEach((el) =>
    say(
      `  <${el.tagName.toLowerCase()}/${el.getAttribute("type") || ""}> label=${q(labelFor(el), 34)} ` +
        `value=${q(el.value !== undefined ? el.value : clean(el.innerText), 18)} ` +
        `placeholder=${q(el.getAttribute("placeholder") || "", 14)} ` +
        `auto=${q(el.getAttribute("data-automation-id") || "", 30)} ` +
        `role=${q(el.getAttribute("role") || "", 12)} maxlen=${el.maxLength}`
    )
  );

  say("\n--- 'I currently work here' candidates ---");
  const hereNodes = [...document.querySelectorAll('input[type="checkbox"], [role="checkbox"], [role="switch"]')];
  if (!hereNodes.length) say("  no checkbox-like controls at all");
  hereNodes.slice(0, 10).forEach((el) =>
    say(
      `  <${el.tagName.toLowerCase()}> auto=${q(el.getAttribute("data-automation-id") || "", 30)} ` +
        `role=${q(el.getAttribute("role") || "", 12)} checked=${el.checked !== undefined ? el.checked : el.getAttribute("aria-checked")} ` +
        `vis=${isVisible(el) ? "y" : "n"}\n` +
        `       SENT label=${q(groupLabelFor(el) || optionLabelFor(el))}\n` +
        `       optionLabel=${q(optionLabelFor(el))} groupLabel=${q(groupLabelFor(el))}`
    )
  );

  const text = out.join("\n");
  console.log(text);
  try {
    copy(text);
    console.log("\n^ copied to clipboard — paste it back");
  } catch (e) {
    console.log("\n(select the output above and copy it)");
  }
  return `${unique.length} ids, ${matched} entry containers matched, ${controls.length} controls, ${buttons.length} add buttons`;
})();
