/**
 * Paste this into the DevTools console while the Workday "My Experience" step
 * is open, then paste the output back.
 *
 * It exists because the repeating-section support was built against a fixture
 * written from assumed Workday markup — the real step sits behind a per-employer
 * login, so the automation ids it actually uses have never been observed. This
 * reports exactly what the extension looks for and what is really there, which
 * is the difference between fixing the bug and guessing at it again.
 *
 * Read-only. It fills nothing, clicks nothing, and sends nothing anywhere.
 */
(() => {
  const out = [];
  const say = (s) => out.push(s);
  const clean = (s) => (s || "").replace(/\s+/g, " ").trim();

  // What the extension currently matches on.
  const PATTERNS = [
    [/^workExperience-(\d+)$/i, "experience"],
    [/^work-experience-(\d+)$/i, "experience"],
    [/^education-(\d+)$/i, "education"],
    [/^websitePanelSet-(\d+)$/i, "website"],
    [/^website-(\d+)$/i, "website"],
    [/^websiteSection-(\d+)$/i, "website"],
  ];

  const ids = [...document.querySelectorAll("[data-automation-id]")].map((el) =>
    el.getAttribute("data-automation-id")
  );
  const unique = [...new Set(ids)];

  say(`URL: ${location.href.slice(0, 110)}`);
  say(`distinct data-automation-id values: ${unique.length}`);

  // 1. Do the entry containers the code expects actually exist?
  say("\n--- ENTRY CONTAINERS the extension looks for ---");
  let matched = 0;
  for (const [re, kind] of PATTERNS) {
    const hits = unique.filter((id) => re.test(id));
    if (hits.length) {
      matched += hits.length;
      say(`  MATCH ${kind}: ${hits.join(", ")}`);
    }
  }
  if (!matched) say("  none matched — this is the likely cause");

  // 2. What repeating-looking ids DO exist?
  say("\n--- ids that look like repeating entries (name + number) ---");
  const numbered = unique.filter((id) => /[-_]\d+$/.test(id));
  say(numbered.length ? "  " + numbered.slice(0, 40).join("\n  ") : "  none");

  // 3. Section-level ids.
  say("\n--- section / panel ids ---");
  say(
    "  " +
      (unique.filter((id) => /section|panel|group/i.test(id)).slice(0, 30).join("\n  ") || "none")
  );

  // 4. Anything mentioning the things that are not filling.
  say("\n--- ids mentioning the missing fields ---");
  for (const word of ["skill", "company", "description", "date", "website", "title", "school", "degree"]) {
    const hits = unique.filter((id) => id.toLowerCase().includes(word));
    if (hits.length) say(`  ${word}: ${hits.slice(0, 10).join(", ")}`);
  }

  // 5. Add buttons — the step that must happen before anything can be filled.
  say("\n--- Add buttons ---");
  const buttons = [...document.querySelectorAll('button, [role="button"], a[role="button"]')]
    .filter((b) => /add/i.test(clean(b.innerText) + " " + (b.getAttribute("aria-label") || "")))
    .slice(0, 12);
  buttons.forEach((b) =>
    say(
      `  text=${JSON.stringify(clean(b.innerText).slice(0, 26))} ` +
        `aria=${JSON.stringify(b.getAttribute("aria-label") || "")} ` +
        `auto=${JSON.stringify(b.getAttribute("data-automation-id") || "")}`
    )
  );
  if (!buttons.length) say("  none found");

  // 6. Every visible control, with the label the scraper would derive.
  say("\n--- visible controls and their labels ---");
  const controls = [...document.querySelectorAll('input,textarea,select,[role="combobox"],button[aria-haspopup]')]
    .filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && (el.getAttribute("type") || "") !== "hidden";
    })
    .slice(0, 45);
  controls.forEach((el) => {
    const auto = el.getAttribute("data-automation-id") || "";
    const label =
      clean(el.labels && el.labels[0] ? el.labels[0].innerText : "") ||
      clean(el.getAttribute("aria-label") || "");
    const wrap = el.closest('[data-automation-id*="formField"]');
    const wrapId = wrap ? wrap.getAttribute("data-automation-id") : "";
    say(
      `  ${el.tagName.toLowerCase()}/${el.getAttribute("type") || ""} ` +
        `auto=${JSON.stringify(auto.slice(0, 30))} wrap=${JSON.stringify((wrapId || "").slice(0, 34))} ` +
        `label=${JSON.stringify(label.slice(0, 40))}`
    );
  });

  const text = out.join("\n");
  console.log(text);
  try {
    copy(text);
    console.log("\n^ copied to clipboard — paste it back");
  } catch (e) {
    console.log("\n(select the output above and copy it)");
  }
  return `${unique.length} ids, ${matched} entry containers matched, ${buttons.length} add buttons`;
})();
