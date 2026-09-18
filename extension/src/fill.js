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

  function fillText(el, value) {
    if (!isVisible(el) || el.disabled || el.readOnly) return false;
    try {
      el.focus({ preventScroll: true });
    } catch (e) {
      /* some widgets refuse focus */
    }
    if (el.isContentEditable) {
      el.textContent = value;
      el.dispatchEvent(new InputEvent("input", { bubbles: true }));
      el.blur();
      return true;
    }
    setNativeValue(el, "");
    setNativeValue(el, value);
    el.dispatchEvent(new Event("blur", { bubbles: true }));
    return norm(el.value) === norm(value) || el.value.length > 0;
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

  function closeListbox() {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    document.body.click();
  }

  /**
   * Drive a non-native dropdown: Workday's listbox button, react-select, or any
   * [role="combobox"]. Returns true only if an option was actually chosen.
   */
  async function fillCombobox(el, value) {
    if (!isVisible(el)) return false;
    try {
      el.scrollIntoView({ block: "center" });
      el.focus({ preventScroll: true });
      el.click();
    } catch (e) {
      return false;
    }
    await sleep(350);

    // Workday and react-select both expose a search box once open.
    const search = Array.from(document.querySelectorAll(SEARCH_BOX_SELECTOR)).filter(isVisible).pop();
    if (search) {
      fillText(search, value);
      await sleep(450);
    } else if (el.tagName === "INPUT") {
      fillText(el, value);
      await sleep(450);
    }

    const picked = await pickOpenOption(value, 2500);
    if (!picked) closeListbox();
    await sleep(150);
    return picked;
  }

  /**
   * Feed several values into one picker (Workday's Skills field).
   * Each value is typed, matched and committed before the next one starts.
   */
  async function fillMultiselect(el, values) {
    let picked = 0;
    for (const value of values) {
      const search =
        Array.from(document.querySelectorAll(SEARCH_BOX_SELECTOR)).filter(isVisible).pop() || null;
      if (!search) {
        try {
          el.scrollIntoView({ block: "center" });
          el.click();
        } catch (e) {
          break;
        }
        await sleep(300);
      }
      const box = Array.from(document.querySelectorAll(SEARCH_BOX_SELECTOR)).filter(isVisible).pop();
      if (box) {
        fillText(box, value);
        await sleep(450);
      } else if (el.tagName === "INPUT") {
        fillText(el, value);
        await sleep(450);
      }
      if (await pickOpenOption(value, 1800)) picked += 1;
      await sleep(200);
    }
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
            if (!ok) ok = await fillCombobox(el, fill.value);
            break;
          case "combobox":
            ok = await fillCombobox(el, fill.value);
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

  function countEntries(spec) {
    return document.querySelectorAll(spec.entry).length;
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
      for (let i = countEntries(spec); i < want; i += 1) {
        const button = addButtonFor(spec);
        if (!button) break;
        button.click();
        added += 1;
        await sleep(700);
        // Stop if the click opened nothing — better than clicking forever.
        if (countEntries(spec) <= i) break;
      }
    }
    if (added) await sleep(600);
    return added;
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
