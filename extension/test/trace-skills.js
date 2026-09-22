/**
 * Paste this into the DevTools console on the step whose Skills picker will
 * not fill, then paste the output back.
 *
 * diagnose-workday.js reports a page at rest. A picker failure is not visible
 * at rest: the widget opens, a box takes the text, a menu renders, a row is
 * clicked, a chip appears — and any one of those five can be the one that
 * breaks. This walks the same path extension/src/fill.js walks and says which
 * step failed and what was really on screen when it did.
 *
 * The decisive line is OPTION SCAN. It counts what fill.js's OPTION_SELECTOR
 * matches, and separately counts everything that *looks* like an option by any
 * reasonable reading. If the second number is non-zero while the first is
 * zero, the menu is rendering fine and the extension simply cannot see it —
 * which is a one-line fix to the selector rather than anything to do with
 * timing.
 *
 * It types one word ("Java") into the Skills box and clears it again. It
 * touches no other field, clicks no button outside the picker, and submits
 * nothing.
 */
(async () => {
  const out = [];
  const say = (s) => out.push(s);
  const clean = (s) => (s || "").replace(/\s+/g, " ").trim();
  const q = (s, n) => JSON.stringify(clean(s).slice(0, n || 50));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // ── mirrors of extension/src/fill.js ──────────────────────────────────────
  const OPTION_SELECTOR = [
    '[data-automation-id="promptOption"]',
    '[data-automation-id="promptLeafNode"]',
    '[data-automation-id="selectWidget-option"]',
    '[role="option"]',
    ".select__option",
    '[class*="select__option"]',
    "li[data-value]",
  ].join(", ");

  const SEARCH_BOX_SELECTOR =
    '[data-automation-id="searchBox"], input[placeholder*="Search" i],' +
    ' input[role="combobox"], .select__input input, input[id*="react-select"]';

  const CHIP_SELECTOR = [
    '[data-automation-id="selectedItem"]',
    '[data-automation-id*="selectedItem"]',
    '[data-automation-id="pill"]',
    '[class*="multi-value"]',
    '[class*="chip"]',
    '[class*="pill"]',
    '[class*="token"]',
  ].join(", ");

  const isVisible = (el) => {
    if (!el || !el.isConnected) return false;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    const st = getComputedStyle(el);
    return st.display !== "none" && st.visibility !== "hidden";
  };

  const widgetScope = (el) =>
    el.closest(
      '[data-automation-id="multiSelectContainer"], [data-automation-id*="formField"],' +
        ' [class*="select__control"], [class*="select__value-container"], fieldset,' +
        " .field, .form-field"
    ) || el;

  function searchBoxFor(el) {
    const scope = widgetScope(el);
    const inner = [...scope.querySelectorAll(SEARCH_BOX_SELECTOR)].filter(isVisible);
    if (inner.length) return { box: inner[inner.length - 1], where: "inside the widget" };
    try {
      if (el.matches(SEARCH_BOX_SELECTOR) && isVisible(el)) return { box: el, where: "the widget itself" };
    } catch (e) {
      /* el may not support matches */
    }
    const outer = [...document.querySelectorAll(SEARCH_BOX_SELECTOR)].filter(isVisible);
    return outer.length
      ? { box: outer[outer.length - 1], where: "PAGE-WIDE fallback (may be another control's box)" }
      : { box: null, where: "nowhere" };
  }

  const matched = () => [...document.querySelectorAll(OPTION_SELECTOR)]
    .filter((o) => isVisible(o) && !o.closest(".iti__country-list"));

  // Anything that could plausibly be a menu row, however the tenant renders it.
  function optionish() {
    const wide =
      '[role="option"], [role="listbox"] > *, [role="menuitem"], li,' +
      ' [data-automation-id*="prompt" i], [data-automation-id*="option" i],' +
      ' [data-automation-id*="menuItem" i], [class*="option" i], [class*="menu-item" i]';
    return [...document.querySelectorAll(wide)].filter((o) => {
      if (!isVisible(o) || o.closest(".iti__country-list")) return false;
      const t = clean(o.innerText);
      return t && t.length < 90 && o.querySelectorAll("input, textarea").length === 0;
    });
  }

  function setNativeValue(el, value) {
    const proto = Object.getPrototypeOf(el);
    const desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) desc.set.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  const describe = (el) =>
    `<${el.tagName.toLowerCase()}> auto=${q(el.getAttribute("data-automation-id") || "", 34)} ` +
    `role=${q(el.getAttribute("role") || "", 14)} id=${q(el.id, 24)} ` +
    `class=${q((el.getAttribute("class") || "").slice(0, 60), 60)}`;

  // ── 1. find the widget ────────────────────────────────────────────────────
  say("=== 1. LOCATING THE SKILLS WIDGET ===");
  const labelNode = [...document.querySelectorAll("label, legend, h2, h3, h4, [id*='label' i]")].find(
    (n) => /^skills?\b/i.test(clean(n.innerText))
  );
  say(`  label node: ${labelNode ? describe(labelNode) + ` text=${q(labelNode.innerText, 40)}` : "NOT FOUND"}`);

  let widget = null;
  const strategies = [
    ["formField-skills container", () =>
      document.querySelector('[data-automation-id*="skill" i] [data-automation-id="multiSelectContainer"]')],
    ["any multiSelectContainer near a Skills label", () => {
      if (!labelNode) return null;
      const form = labelNode.closest('[data-automation-id*="formField"], .field, fieldset, div');
      return form && form.querySelector('[data-automation-id="multiSelectContainer"], [role="combobox"], input');
    }],
    ["aria-labelledby pointing at the Skills label", () => {
      if (!labelNode || !labelNode.id) return null;
      return document.querySelector(`[aria-labelledby~="${CSS.escape(labelNode.id)}"]`);
    }],
    ["any element with skill in its automation-id", () =>
      [...document.querySelectorAll('[data-automation-id*="skill" i]')]
        .find((el) => el.matches('[role="combobox"], input, [data-automation-id="multiSelectContainer"]'))],
  ];
  for (const [name, fn] of strategies) {
    let hit = null;
    try {
      hit = fn();
    } catch (e) {
      hit = null;
    }
    say(`  ${hit ? "HIT " : "miss"} ${name}${hit ? ": " + describe(hit) : ""}`);
    if (hit && !widget) widget = hit;
  }
  if (!widget) {
    say("\n  No skills widget found at all. Paste the diagnose-workday.js output instead.");
    console.log(out.join("\n"));
    try { copy(out.join("\n")); } catch (e) { /* not in DevTools */ }
    return "no widget";
  }
  say(`\n  USING: ${describe(widget)}`);
  say(`  innerText now: ${q(widget.innerText, 60)}`);
  say(`  would the backend call it a multiselect? role=combobox:${widget.getAttribute("role") === "combobox"} ` +
      `tag-not-input:${!["input", "textarea"].includes(widget.tagName.toLowerCase())} ` +
      `automation-says-multiselect:${/multiselect/i.test(widget.getAttribute("data-automation-id") || "")}`);

  // ── 2. open it ────────────────────────────────────────────────────────────
  say("\n=== 2. OPENING THE WIDGET (click, as fill.js does) ===");
  const beforeNodes = document.querySelectorAll("*").length;
  widget.scrollIntoView({ block: "center" });
  try { widget.focus({ preventScroll: true }); } catch (e) { /* refuses focus */ }
  widget.click();
  await sleep(600);
  say(`  DOM nodes ${beforeNodes} -> ${document.querySelectorAll("*").length} (a jump means a popup rendered)`);
  say(`  document.activeElement: ${describe(document.activeElement)}`);
  say(`  options matching fill.js OPTION_SELECTOR right now: ${matched().length}`);
  say(`  option-like nodes by any reading: ${optionish().length}`);

  // ── 3. find the box to type into ──────────────────────────────────────────
  say("\n=== 3. THE BOX fill.js WOULD TYPE INTO ===");
  const found = searchBoxFor(widget);
  say(`  found ${found.box ? "yes" : "NO"} — ${found.where}`);
  if (found.box) {
    say(`  ${describe(found.box)} placeholder=${q(found.box.getAttribute("placeholder") || "", 30)}`);
    const owner = widgetScope(found.box);
    say(`  belongs to the skills widget? ${widgetScope(widget) === owner || widgetScope(widget).contains(found.box)}`);
  } else {
    say("  fill.js falls back to the widget itself only if it is an <input>;");
    say(`  this widget is a <${widget.tagName.toLowerCase()}>, so the value has nowhere to go.`);
  }
  const box = found.box || (widget.tagName === "INPUT" ? widget : null);

  // ── 4. type, and watch the menu ───────────────────────────────────────────
  say("\n=== 4. OPTION SCAN after typing 'Java' ===");
  if (!box) {
    say("  skipped: no box to type into — this is the failure.");
  } else {
    const typedAt = Date.now();
    setNativeValue(box, "Java");
    for (let i = 0; i < 12; i += 1) {
      await sleep(i === 0 ? 60 : 240);
      const m = matched();
      const any = optionish();
      say(
        `  t+${String(Date.now() - typedAt).padStart(4)}ms  OPTION_SELECTOR=${String(m.length).padStart(3)}` +
          `  option-like=${String(any.length).padStart(3)}` +
          (m.length
            ? `  first=${q(m[0].innerText, 30)}`
            : any.length
            ? `  first-unseen=${q(any[0].innerText, 30)}`
            : "")
      );
    }

    const m = matched();
    const any = optionish();
    if (!m.length && any.length) {
      say("\n  >>> THE MENU RENDERS BUT fill.js CANNOT SEE IT. Rows actually used:");
      any.slice(0, 8).forEach((o) => say(`      ${describe(o)} text=${q(o.innerText, 40)}`));
      const parent = any[0].parentElement;
      say(`      their container: ${parent ? describe(parent) : "?"}`);
    } else if (m.length) {
      say("\n  Rows fill.js can see:");
      m.slice(0, 8).forEach((o) => say(`      ${describe(o)} text=${q(o.innerText, 40)}`));
      const target = m.find((o) => /java/i.test(o.innerText));
      say(`\n  a row matching "Java": ${target ? q(target.innerText, 30) : "NONE — the taxonomy may name it differently"}`);
      if (target) {
        const chipsBefore = widgetScope(widget).querySelectorAll(CHIP_SELECTOR).length;
        target.click();
        await sleep(800);
        const chipsAfter = widgetScope(widget).querySelectorAll(CHIP_SELECTOR).length;
        say(`  clicked it — chips matching CHIP_SELECTOR ${chipsBefore} -> ${chipsAfter}`);
        if (chipsAfter === chipsBefore) {
          say("  >>> THE CLICK LANDED BUT NO CHIP WAS COUNTED. What the widget holds now:");
          say(`      widget text: ${q(widgetScope(widget).innerText, 80)}`);
          [...widgetScope(widget).children].slice(0, 6).forEach((c) =>
            say(`      child ${describe(c)} text=${q(c.innerText, 34)}`)
          );
        }
      }
    } else {
      say("\n  >>> NO MENU RENDERED AT ALL within 2.8s.");
      say("      Either the click did not open the picker, or the text did not");
      say("      reach the box it listens to.");
      say(`      box value now: ${q(box.value, 30)}`);
    }

    // Leave nothing typed behind.
    setNativeValue(box, "");
  }

  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  say("\n(search box cleared, menu closed — nothing was submitted)");

  const text = out.join("\n");
  console.log(text);
  try {
    copy(text);
    console.log("\n^ copied to clipboard — paste it back");
  } catch (e) {
    console.log("\n(select the output above and copy it)");
  }
  return "trace complete";
})();
