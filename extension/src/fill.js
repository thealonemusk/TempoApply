/**
 * Fills -> DOM.
 *
 * Two things make this harder than `el.value = x`:
 *
 *   1. React (Greenhouse, Lever, Ashby, Workday, Glassdoor's smartapply) tracks
 *      input values on the node itself. Assigning `.value` bypasses the tracker
 *      and the framework reverts the field on the next render, so every write
 *      goes through the native prototype setter and then fires input+change.
 *   2. Workday has no <select>. Picking an option means: click the button, wait
 *      for the listbox to render, type into its searchBox if there is one, then
 *      click the matching [data-automation-id="promptOption"]. That is inherently
 *      async, so the whole filler is sequential and awaited.
 */
(function () {
  const TA = (window.__TA = window.__TA || {});

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
    '[data-automation-id="searchBox"], input[placeholder*="Search" i], input[role="combobox"], .select__input input, input[id*="react-select"]';

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const norm = (s) => (s || "").replace(/\s+/g, " ").trim().toLowerCase();

  function isVisible(el) {
    if (!el || !el.isConnected) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    const style = window.getComputedStyle(el);
    return style.display !== "none" && style.visibility !== "hidden";
  }

  /** Write a value the way a user would, so React's value tracker stays in sync. */
  function setNativeValue(el, value) {
    const proto =
      el instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : el instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    if (descriptor && descriptor.set) {
      descriptor.set.call(el, value);
    } else {
      el.value = value;
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  /**
   * Type into a field.
   *
   * `keepFocus` matters more than it looks. A plain text input wants the blur:
   * that is what makes a portal run its validation. A dropdown's search box
   * does not — Workday closes the listbox on blur, so blurring straight after
   * typing tore the menu down before the option could be clicked, and every
   * skill silently went nowhere.
   */
  function fillText(el, value, keepFocus) {
    if (!isVisible(el) || el.disabled || el.readOnly) return false;
    try {
      el.focus({ preventScroll: true });
    } catch (e) {
      /* some widgets refuse focus */
    }
    if (el.isContentEditable) {
      el.textContent = value;
      el.dispatchEvent(new InputEvent("input", { bubbles: true }));
      if (!keepFocus) el.blur();
      return true;
    }
    setNativeValue(el, "");
    setNativeValue(el, value);
    if (!keepFocus) el.dispatchEvent(new Event("blur", { bubbles: true }));
    return norm(el.value) === norm(value) || el.value.length > 0;
  }

  /**
   * Press Enter on a field, the way a person commits a typed value.
   *
   * `keyCode`/`which` are legacy and read-only, so they cannot be passed
   * through the constructor — but plenty of widgets still read them, so they
   * are defined onto the event by hand.
   */
  function pressEnter(el) {
    for (const type of ["keydown", "keypress", "keyup"]) {
      const ev = new KeyboardEvent(type, {
        key: "Enter",
        code: "Enter",
        bubbles: true,
        cancelable: true,
      });
      try {
        Object.defineProperty(ev, "keyCode", { get: () => 13 });
        Object.defineProperty(ev, "which", { get: () => 13 });
      } catch (e) {
        /* non-configurable in some engines; key/code still carry it */
      }
      el.dispatchEvent(ev);
    }
  }

  // A committed entry in a multi-value picker, however the portal renders it.
  const CHIP_SELECTOR = [
    '[data-automation-id="selectedItem"]',
    '[data-automation-id*="selectedItem"]',
    '[data-automation-id="pill"]',
    '[class*="multi-value"]',
    '[class*="chip"]',
    '[class*="pill"]',
    '[class*="token"]',
  ].join(", ");

  /** How many values this picker currently holds. */
  function chipCount(el) {
    try {
      return widgetScope(el).querySelectorAll(CHIP_SELECTOR).length;
    } catch (e) {
      return 0;
    }
  }

  function fillSelect(el, label) {
    if (!isVisible(el) || el.disabled) return false;
    const options = Array.from(el.options);
    const want = norm(label);
    let match =
      options.find((o) => norm(o.text) === want) ||
      options.find((o) => norm(o.value) === want) ||
      options.find((o) => norm(o.text).includes(want) && want) ||
      options.find((o) => want.includes(norm(o.text)) && norm(o.text));
    if (!match) return false;
    el.focus({ preventScroll: true });
    setNativeValue(el, match.value);
    return true;
  }

  function fillCheckbox(el) {
    if (!isVisible(el) || el.disabled) return false;
    if (el.checked) return true;
    el.click();
    if (!el.checked) {
      setNativeValue(el, el.value || "on");
      el.checked = true;
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }
    return el.checked;
  }

  function fillRadio(el) {
    if (!isVisible(el) || el.disabled) return false;
    if (el.checked) return true;
    el.click();
    if (!el.checked) {
      el.checked = true;
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }
    return el.checked;
  }

  /** Click the option whose text best matches `want`, from an open listbox. */
  async function pickOpenOption(want, deadlineMs) {
    const target = norm(want);
    const deadline = Date.now() + (deadlineMs || 2500);
    while (Date.now() < deadline) {
      const options = Array.from(document.querySelectorAll(OPTION_SELECTOR)).filter(
        (o) => isVisible(o) && !o.closest(".iti__country-list")
      );
      if (options.length) {
        const texts = options.map((o) => norm(o.innerText || o.textContent));
        let i = texts.findIndex((t) => t === target);
        if (i < 0) i = texts.findIndex((t) => t && (t.includes(target) || target.includes(t)));
        // "Yes"/"No" must not fuzzy-match into "Yes, I require sponsorship".
        if (i < 0 && (target === "yes" || target === "no")) {
          i = texts.findIndex((t) => t.startsWith(target));
        }
        if (i >= 0) {
          options[i].scrollIntoView({ block: "nearest" });
          options[i].click();
          return true;
        }
        if (options.length === 1) {
          options[0].click();
          return true;
        }
        return false;
      }
      await sleep(120);
    }
    return false;
  }

  /** Is any listbox rendered right now? Distinguishes "no match" from "no menu". */
  function anyOptionsVisible() {
    return Array.from(document.querySelectorAll(OPTION_SELECTOR)).some(
      (o) => isVisible(o) && !o.closest(".iti__country-list")
    );
  }

  function closeListbox() {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    document.body.click();
  }

  /** The container this widget owns, so a search box can be scoped to it. */
  function widgetScope(el) {
    return (
      el.closest(
        '[data-automation-id="multiSelectContainer"], [data-automation-id*="formField"],' +
          ' [class*="select__control"], [class*="select__value-container"], fieldset,' +
          " .field, .form-field"
      ) || el
    );
  }

  /**
   * The box to type into for THIS widget.
   *
   * Scoped to the widget first, and that is the whole point: a page-wide
   * `querySelectorAll(SEARCH_BOX_SELECTOR).pop()` happily returns a search box
   * belonging to some other control — Workday usually has one on screen — and
   * then every value is typed into the wrong field and matches nothing.
   */
  function searchBoxFor(el) {
    const scope = widgetScope(el);
    const inner = Array.from(scope.querySelectorAll(SEARCH_BOX_SELECTOR)).filter(isVisible);
    if (inner.length) return inner[inner.length - 1];
    try {
      if (el.matches(SEARCH_BOX_SELECTOR) && isVisible(el)) return el;
    } catch (e) {
      /* el may not support matches */
    }
    // Only now consider a portal-rendered box, which Workday uses for prompts.
    const outer = Array.from(document.querySelectorAll(SEARCH_BOX_SELECTOR)).filter(isVisible);
    return outer.length ? outer[outer.length - 1] : null;
  }

  async function openWidget(el) {
    try {
      el.scrollIntoView({ block: "center" });
      el.focus({ preventScroll: true });
      el.click();
    } catch (e) {
      return false;
    }
    await sleep(350);
    return true;
  }

  /**
   * Drive a non-native dropdown: Workday's listbox button, react-select, or any
   * [role="combobox"]. Returns true only if an option was actually chosen.
   *
   * `value` may be a single string or a list of acceptable answers, best
   * first. The list matters because these options do not exist in the DOM
   * until the listbox opens, so the backend cannot know that this tenant
   * offers "Phone" and "Main" but no "Mobile".
   */
  async function fillCombobox(el, value) {
    if (!isVisible(el)) return false;
    const candidates = (Array.isArray(value) ? value : [value]).filter(Boolean);
    if (!candidates.length) return false;
    if (!(await openWidget(el))) return false;

    for (const candidate of candidates) {
      const search = searchBoxFor(el);
      if (search) {
        fillText(search, candidate, true);
        await sleep(450);
      } else if (el.tagName === "INPUT") {
        fillText(el, candidate, true);
        await sleep(450);
      }
      if (await pickOpenOption(candidate, 2500)) {
        await sleep(150);
        return true;
      }
      // Re-open if rejecting the last attempt collapsed the listbox.
      if (!searchBoxFor(el)) await openWidget(el);
    }

    closeListbox();
    await sleep(150);
    return false;
  }

  /**
   * Feed several values into one picker (Workday's Skills field).
   * Each value is typed, matched and committed before the next one starts.
   */
  async function fillMultiselect(el, values) {
    let picked = 0;
    // Some pickers have no listbox at all — they are tag inputs that commit on
    // Enter. Waiting 1.5s for a menu that will never render costs 15 seconds
    // across ten skills, so once we have established there is no menu we stop
    // waiting for one.
    let hasListbox = true;
    for (const value of values) {
      // The box is resolved against this widget every round. Taking the last
      // search box on the page — computed before the picker was even opened —
      // meant that whenever another control had one visible, every skill was
      // typed into the wrong input.
      let box = searchBoxFor(el);
      if (!box) {
        await openWidget(el);
        box = searchBoxFor(el);
      }
      if (!box && el.tagName === "INPUT") box = el;
      if (!box) continue;

      const before = chipCount(el);
      fillText(box, value, true);          // never blur: that closes the menu
      await sleep(450);

      // Prefer the portal's own taxonomy entry when it offers one...
      let ok = false;
      if (hasListbox) {
        ok = await pickOpenOption(value, picked === 0 ? 1500 : 800);
        if (!ok && !anyOptionsVisible()) hasListbox = false;
      }

      // ...otherwise commit the typed text with Enter, which is how a person
      // adds a skill: type it, press Enter, type the next one.
      if (!ok) {
        pressEnter(box);
        await sleep(400);
        ok = chipCount(el) > before;
      }
      if (!ok) ok = chipCount(el) > before;

      if (ok) {
        picked += 1;
      } else {
        // Leave nothing half-typed — a stray value commits itself on blur.
        fillText(box, "", true);
      }
      await sleep(200);
    }

    const box = searchBoxFor(el);
    if (box) fillText(box, "", true);
    closeListbox();
    return picked > 0;
  }

  /** Put the resume bytes into a file input the way a file picker would. */
  function fillFile(el, file) {
    if (!file) return false;
    try {
      const dt = new DataTransfer();
      dt.items.add(file);
      el.files = dt.files;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      // Some boards listen for a drop on the dropzone rather than on the input.
      const zone = el.closest('[class*="dropzone" i], [class*="drop-zone" i], [data-automation-id*="attachment" i]');
      if (zone) {
        zone.dispatchEvent(new DragEvent("drop", { bubbles: true, dataTransfer: dt }));
      }
      return el.files && el.files.length > 0;
    } catch (e) {
      return false;
    }
  }

  function base64ToFile(b64, filename, mime) {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return new File([bytes], filename, { type: mime || "application/pdf" });
  }

  TA.base64ToFile = base64ToFile;

  /** Answers this dropdown will accept, best first. `values` is optional. */
  function comboCandidates(fill) {
    if (Array.isArray(fill.values) && fill.values.length) return fill.values;
    return [fill.value];
  }

  /**
   * Apply every fill in order. `resumeFile` may be null — file fills are then
   * reported as failures so the widget can tell the user to attach it by hand.
   */
  TA.applyFills = async function applyFills(fills, elements, resumeFile, onProgress) {
    const applied = [];
    const failed = [];

    for (const fill of fills) {
      if (fill.action === "skip") continue;
      const el = elements.get(String(fill.idx));
      if (!el || !el.isConnected) {
        failed.push({ ...fill, why: "element gone" });
        continue;
      }

      let ok = false;
      try {
        switch (fill.action) {
          case "text":
            ok = fillText(el, fill.value);
            break;
          case "select":
            ok = fillSelect(el, fill.value);
            if (!ok) ok = await fillCombobox(el, comboCandidates(fill));
            break;
          case "combobox":
            ok = await fillCombobox(el, comboCandidates(fill));
            break;
          case "multiselect":
            ok = await fillMultiselect(el, fill.values && fill.values.length ? fill.values : [fill.value]);
            break;
          case "checkbox":
            ok = fillCheckbox(el);
            break;
          case "radio":
            ok = fillRadio(el);
            break;
          case "file":
            ok = fillFile(el, resumeFile);
            break;
          default:
            ok = false;
        }
      } catch (e) {
        ok = false;
      }

      if (ok) {
        TA.mark(el, fill.confidence === "low" ? "low" : "ok");
        applied.push(fill);
      } else {
        TA.mark(el, "fail");
        failed.push({ ...fill, why: "could not set" });
      }
      if (onProgress) onProgress(applied.length, failed.length);
      await sleep(fill.action === "combobox" || fill.action === "select" || fill.action === "multiselect" ? 60 : 25);
    }

    return { applied, failed };
  };

  // Repeating sections start collapsed behind an Add button. Each kind is
  // matched by its Workday container id first, then by the section heading, so
  // a portal that does not use those ids still works.
  const SECTION_SPECS = {
    experience: {
      entry: '[data-automation-id^="workExperience-"], [data-automation-id^="work-experience-"]',
      section: '[data-automation-id="workExperienceSection"], [data-automation-id*="workExperience"]',
      heading: /work experience|employment/i,
    },
    education: {
      entry: '[data-automation-id^="education-"]',
      section: '[data-automation-id="educationSection"], [data-automation-id*="education"]',
      heading: /education|qualification/i,
    },
    website: {
      entry: '[data-automation-id^="websitePanelSet-"], [data-automation-id^="website-"]',
      section: '[data-automation-id="websiteSection"], [data-automation-id*="website"]',
      heading: /websites?|social|links?/i,
    },
  };

  // A label that appears exactly once per entry, used to count entries on a
  // tenant whose container ids we do not recognise.
  const ENTRY_ANCHORS = {
    experience: /^(job\s*title|company|employer)$/i,
    education: /^(school(\s+or\s+university)?|university|institution)$/i,
    website: /^(url|website)$/i,
  };

  function anchorCount(kind) {
    const pattern = ENTRY_ANCHORS[kind];
    if (!pattern || typeof TA.scrape !== "function") return 0;
    try {
      return TA.scrape().fields.filter((f) =>
        pattern.test(norm(f.label || f.group_label || ""))
      ).length;
    } catch (e) {
      return 0;
    }
  }

  /**
   * How many entries of this section are on the page.
   *
   * The id-based count is the accurate one, but it returns 0 on any tenant
   * that does not use `workExperience-N`. That zero used to make
   * `expandSections` click Add once and then break on its own runaway guard
   * (`countEntries(spec) <= i` is `0 <= 0`), so a second employer was never
   * opened and the profile's entry 2 silently vanished from the application.
   * Counting the per-entry anchor label recovers the real number.
   */
  function countEntries(spec, kind) {
    const byId = document.querySelectorAll(spec.entry).length;
    if (byId) return byId;
    return anchorCount(kind);
  }

  /** The Add / Add Another button that belongs to this section. */
  /** The accessible name of a control, however the page chose to provide it. */
  function buttonName(el) {
    const aria = el.getAttribute("aria-label") || "";
    const auto = el.getAttribute("data-automation-id") || "";
    return norm([el.innerText, aria, auto].filter(Boolean).join(" "));
  }

  function sectionContainer(spec) {
    // An entry id like workExperience-1 also matches a loose *="workExperience"
    // selector, so a naive querySelector can return a single entry and the Add
    // button search is then scoped inside it, where no Add button exists.
    const candidates = Array.from(document.querySelectorAll(spec.section))
      .filter((node) => !node.matches(spec.entry));
    if (candidates.length) {
      // Outermost wins, so the section is not confused with a panel inside it.
      return candidates.reduce((a, b) => (a.contains(b) ? a : b));
    }
    return (
      Array.from(document.querySelectorAll("section, div, fieldset")).find((node) => {
        const head = node.querySelector("h2, h3, h4, legend, [role='heading']");
        return head && spec.heading.test(head.innerText || "");
      }) || null
    );
  }

  function addButtonFor(spec) {
    const scope = sectionContainer(spec) || document;
    const buttons = Array.from(
      scope.querySelectorAll(
        'button, [role="button"], a[role="button"], [data-automation-id="Add"]'
      )
    ).filter(isVisible);
    // Exact match first, so "Add Another" wins over an unrelated "Add to list".
    return (
      buttons.find((b) => /^add( another)?$/.test(buttonName(b))) ||
      buttons.find((b) => /(^| )add( |$)/.test(buttonName(b))) ||
      null
    );
  }

  /**
   * Open as many entries as the profile can fill. Returns how many were added,
   * so the caller knows whether to re-scrape.
   */
  TA.expandSections = async function expandSections(needed) {
    let added = 0;
    for (const [kind, want] of Object.entries(needed || {})) {
      const spec = SECTION_SPECS[kind];
      if (!spec || !want) continue;
      let have = countEntries(spec, kind);
      let guard = 0;
      while (have < want && guard < want + 2) {
        guard += 1;
        const button = addButtonFor(spec);
        if (!button) break;
        button.click();
        added += 1;
        await sleep(700);
        const now = countEntries(spec, kind);
        // Stop only if the click genuinely opened nothing — measured against
        // the count before the click, not against the loop index.
        if (now <= have) break;
        have = now;
      }
    }
    if (added) await sleep(600);
    return added;
  };

  // ── Section picking ────────────────────────────────────────────────────────
  //
  // Filling one part of a long form at a time. Workday's My Experience step is
  // the case that needs it: the user wants to deal with Work Experience, check
  // it, then move on to Education — rather than have every block written at
  // once and audit the lot.

  const PICK_FIELD_SELECTOR =
    'input:not([type="hidden"]), textarea, select, [role="combobox"],' +
    ' [data-automation-id="multiSelectContainer"], button[aria-haspopup="listbox"]';

  /**
   * The smallest block around `el` that holds more than one field.
   *
   * Stopping at the first container with two or more fields is what keeps the
   * selection tight — walking to the outermost match would just reselect the
   * whole form, which is the thing being avoided.
   */
  function sectionAround(el) {
    let node = el;
    let fallback = null;
    while (node && node !== document.body && node !== document.documentElement) {
      const count = node.querySelectorAll ? node.querySelectorAll(PICK_FIELD_SELECTOR).length : 0;
      if (count >= 1 && !fallback) fallback = node;
      if (count >= 2) return node;
      node = node.parentElement;
    }
    return fallback || el;
  }

  function fieldCount(node) {
    try {
      return node.querySelectorAll(PICK_FIELD_SELECTOR).length;
    } catch (e) {
      return 0;
    }
  }

  /**
   * Let the user point at a section. Resolves with the chosen element, or
   * null if they cancelled.
   */
  let activePick = null;

  TA.pickSection = function pickSection() {
    return new Promise((resolve) => {
      const box = document.createElement("div");
      box.setAttribute("data-ta-picker", "");
      box.style.cssText = [
        "position:fixed", "z-index:2147483646", "pointer-events:none",
        "border:2px solid #2563eb", "background:rgba(37,99,235,.10)",
        "border-radius:6px", "transition:all .06s linear", "display:none",
      ].join(";");

      const tip = document.createElement("div");
      tip.setAttribute("data-ta-picker", "");
      tip.style.cssText = [
        "position:fixed", "z-index:2147483647", "pointer-events:none",
        "background:#111827", "color:#fff", "font:12px/1.4 system-ui,sans-serif",
        "padding:5px 9px", "border-radius:6px", "box-shadow:0 2px 8px rgba(0,0,0,.3)",
      ].join(";");
      tip.textContent = "Click a section to fill it · Esc to cancel";

      document.documentElement.append(box, tip);
      const previousCursor = document.documentElement.style.cursor;
      document.documentElement.style.cursor = "crosshair";

      let current = null;

      const cleanup = () => {
        activePick = null;
        document.removeEventListener("mousemove", onMove, true);
        document.removeEventListener("click", onClick, true);
        document.removeEventListener("keydown", onKey, true);
        box.remove();
        tip.remove();
        document.documentElement.style.cursor = previousCursor;
      };

      // So another frame winning the click can tear this one down — and
      // actually settle the promise, not just remove the overlay.
      activePick = () => {
        cleanup();
        resolve(null);
      };

      const onMove = (e) => {
        const target = document.elementFromPoint(e.clientX, e.clientY);
        // Never offer our own overlay or the panel as a section.
        if (!target || target.closest("[data-ta-picker], #tempoapply-widget-host")) return;
        const section = sectionAround(target);
        if (!section) return;
        current = section;
        const r = section.getBoundingClientRect();
        box.style.display = "block";
        box.style.left = `${r.left}px`;
        box.style.top = `${r.top}px`;
        box.style.width = `${r.width}px`;
        box.style.height = `${r.height}px`;
        const n = fieldCount(section);
        tip.textContent = `${n} field${n === 1 ? "" : "s"} · click to fill · Esc to cancel`;
        tip.style.left = `${Math.min(e.clientX + 14, window.innerWidth - 240)}px`;
        tip.style.top = `${Math.max(e.clientY - 34, 4)}px`;
      };

      // Capture phase, and swallow the event: the click is for choosing a
      // section, and must never reach the portal's own button underneath.
      const onClick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        cleanup();
        resolve(current);
      };

      const onKey = (e) => {
        if (e.key !== "Escape") return;
        e.preventDefault();
        e.stopPropagation();
        cleanup();
        resolve(null);
      };

      document.addEventListener("mousemove", onMove, true);
      document.addEventListener("click", onClick, true);
      document.addEventListener("keydown", onKey, true);
    });
  };

  TA.cancelPick = function cancelPick() {
    if (activePick) {
      activePick();
      return;
    }
    document.querySelectorAll("[data-ta-picker]").forEach((n) => n.remove());
  };

  /** Outline a field so the user can see, at a glance, what was touched. */
  TA.mark = function mark(el, kind) {
    const target =
      el.type === "radio" || el.type === "checkbox"
        ? el.closest("label, fieldset, .field, .form-field") || el
        : el;
    target.classList.remove("ta-mark-ok", "ta-mark-low", "ta-mark-fail", "ta-mark-todo");
    target.classList.add(`ta-mark-${kind}`);
  };

  TA.clearMarks = function clearMarks() {
    document
      .querySelectorAll(".ta-mark-ok, .ta-mark-low, .ta-mark-fail, .ta-mark-todo")
      .forEach((el) => el.classList.remove("ta-mark-ok", "ta-mark-low", "ta-mark-fail", "ta-mark-todo"));
  };

  /** Flag required questions nobody answered, so they are easy to find. */
  TA.markTodo = function markTodo(labels, fields, elements) {
    const wanted = new Set(labels.map(norm));
    let first = null;
    for (const field of fields) {
      const text = norm(field.group_label || field.label || field.placeholder || field.name);
      if (!wanted.has(text)) continue;
      const el = elements.get(String(field.idx));
      if (!el || !el.isConnected) continue;
      if (el.classList.contains("ta-mark-ok") || el.classList.contains("ta-mark-low")) continue;
      TA.mark(el, "todo");
      if (!first) first = el;
    }
    return first;
  };

  TA.injectStyles = function injectStyles() {
    if (document.getElementById("ta-fill-styles")) return;
    const style = document.createElement("style");
    style.id = "ta-fill-styles";
    style.textContent = `
      .ta-mark-ok   { outline: 2px solid #10b981 !important; outline-offset: 1px !important;
                      border-radius: 4px; transition: outline-color .3s ease; }
      .ta-mark-low  { outline: 2px solid #f59e0b !important; outline-offset: 1px !important;
                      border-radius: 4px; }
      .ta-mark-fail { outline: 2px dashed #ef4444 !important; outline-offset: 1px !important;
                      border-radius: 4px; }
      .ta-mark-todo { outline: 2px dashed #f59e0b !important; outline-offset: 1px !important;
                      border-radius: 4px; }
    `;
    (document.head || document.documentElement).appendChild(style);
  };
})();
