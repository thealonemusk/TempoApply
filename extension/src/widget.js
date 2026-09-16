/**
 * The floating panel, top frame only.
 *
 * Lives in a shadow root so no portal stylesheet can reach it — Workday in
 * particular sets aggressive global styles on buttons and lists.
 */
(function () {
  const TA = (window.__TA = window.__TA || {});

  const STYLES = `
    :host { all: initial; }
    * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }

    .panel {
      position: fixed; right: 20px; bottom: 20px; z-index: 2147483647;
      width: 300px; background: #ffffff; color: #0f172a;
      border: 1px solid rgba(15,23,42,.10); border-radius: 14px;
      box-shadow: 0 12px 32px rgba(15,23,42,.16), 0 2px 6px rgba(15,23,42,.08);
      overflow: hidden; font-size: 13px; line-height: 1.45;
    }
    .panel.collapsed { width: auto; }

    .head { display: flex; align-items: center; gap: 8px; padding: 11px 12px;
            cursor: grab; user-select: none; border-bottom: 1px solid rgba(15,23,42,.07); }
    .panel.collapsed .head { border-bottom: none; }
    .head:active { cursor: grabbing; }
    .bolt { width: 22px; height: 22px; border-radius: 6px; flex: none;
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            display: grid; place-items: center; color: #fff; font-size: 13px; }
    .name { font-weight: 600; font-size: 13px; letter-spacing: -.01em; flex: 1; }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: #cbd5e1; flex: none; }
    .dot.up { background: #10b981; } .dot.down { background: #ef4444; }
    .icon-btn { border: none; background: transparent; cursor: pointer; padding: 2px 4px;
                color: #64748b; font-size: 14px; line-height: 1; border-radius: 4px; }
    .icon-btn:hover { background: rgba(15,23,42,.06); color: #0f172a; }

    .body { padding: 12px; display: grid; gap: 10px; }
    .panel.collapsed .body { display: none; }

    .job { font-size: 12px; color: #475569; }
    .job b { color: #0f172a; font-weight: 600; }
    .job .ats { display: inline-block; margin-top: 3px; padding: 1px 6px; border-radius: 4px;
                background: #eef2ff; color: #4338ca; font-size: 10px; font-weight: 600;
                text-transform: uppercase; letter-spacing: .04em; }

    .actions { display: grid; gap: 6px; }

    .step { font-size: 10.5px; font-weight: 600; color: #4338ca; background: #eef2ff;
            border-radius: 5px; padding: 3px 7px; justify-self: start; letter-spacing: .01em; }

    .btn { width: 100%; border: none; border-radius: 9px; padding: 9px 12px; font-size: 13px;
           font-weight: 600; cursor: pointer; transition: transform .06s ease, filter .15s ease; }
    .btn:active { transform: scale(.985); }
    .btn:disabled { opacity: .55; cursor: not-allowed; }
    .btn.primary { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; }
    .btn.primary:hover:not(:disabled) { filter: brightness(1.06); }
    .btn.ghost { background: #f1f5f9; color: #334155; }
    .btn.ghost:hover:not(:disabled) { background: #e2e8f0; }
    .row { display: flex; gap: 6px; }
    .row .btn { flex: 1; }

    .stats { display: flex; gap: 6px; }
    .stat { flex: 1; text-align: center; padding: 7px 4px; border-radius: 8px; background: #f8fafc; }
    .stat b { display: block; font-size: 15px; font-weight: 700; letter-spacing: -.02em; }
    .stat span { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }
    .stat.ok b { color: #059669; } .stat.low b { color: #d97706; } .stat.todo b { color: #dc2626; }

    .todo { display: grid; gap: 4px; max-height: 132px; overflow-y: auto; }
    .todo-item { text-align: left; width: 100%; background: #fffbeb; border: 1px solid #fde68a;
                 color: #92400e; border-radius: 7px; padding: 6px 8px; font-size: 11.5px;
                 cursor: pointer; }
    .todo-item:hover { background: #fef3c7; }

    .msg { font-size: 11.5px; padding: 7px 9px; border-radius: 7px; }
    .msg.err { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
    .msg.info { background: #f8fafc; color: #475569; }
    .msg a { color: #4f46e5; }

    .foot { font-size: 10.5px; color: #94a3b8; text-align: center; }
    kbd { background: #f1f5f9; border: 1px solid #e2e8f0; border-bottom-width: 2px;
          border-radius: 4px; padding: 0 4px; font-size: 10px; font-family: ui-monospace, monospace; }

    @media (prefers-color-scheme: dark) {
      .panel { background: #0f172a; color: #e2e8f0; border-color: rgba(148,163,184,.18);
               box-shadow: 0 12px 32px rgba(0,0,0,.5); }
      .head { border-bottom-color: rgba(148,163,184,.14); }
      .icon-btn { color: #94a3b8; } .icon-btn:hover { background: rgba(148,163,184,.14); color: #e2e8f0; }
      .job { color: #94a3b8; } .job b { color: #f1f5f9; }
      .job .ats { background: #312e81; color: #c7d2fe; }
      .step { background: #312e81; color: #c7d2fe; }
      .btn.ghost { background: #1e293b; color: #cbd5e1; }
      .btn.ghost:hover:not(:disabled) { background: #334155; }
      .stat { background: #1e293b; } .stat span { color: #94a3b8; }
      .todo-item { background: #422006; border-color: #854d0e; color: #fde68a; }
      .todo-item:hover { background: #713f12; }
      .msg.err { background: #450a0a; color: #fca5a5; border-color: #7f1d1d; }
      .msg.info { background: #1e293b; color: #94a3b8; }
      kbd { background: #1e293b; border-color: #334155; }
    }
  `;

  const HTML = `
    <div class="panel" part="panel">
      <div class="head" data-drag>
        <div class="bolt">⚡</div>
        <div class="name">TempoApply</div>
        <div class="dot" data-dot title="backend status"></div>
        <button class="icon-btn" data-toggle title="Collapse">–</button>
        <button class="icon-btn" data-close title="Hide on this page">×</button>
      </div>
      <div class="body">
        <div class="job" data-job></div>
        <div class="step" data-step hidden></div>
        <button class="btn primary" data-fill>Autofill</button>
        <div class="actions" data-actions-gate hidden></div>
        <div data-results hidden>
          <div class="stats">
            <div class="stat ok"><b data-n-ok>0</b><span>filled</span></div>
            <div class="stat low"><b data-n-low>0</b><span>check</span></div>
            <div class="stat todo"><b data-n-todo>0</b><span>you</span></div>
          </div>
        </div>
        <div class="todo" data-todo hidden></div>
        <div data-msg hidden></div>
        <div class="row" data-actions hidden>
          <button class="btn ghost" data-refill>Fill again</button>
          <button class="btn ghost" data-applied>Mark applied</button>
        </div>
        <div class="foot">Review before you submit · <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>F</kbd></div>
      </div>
    </div>
  `;

  let host = null;
  let root = null;
  let el = {};

  function build() {
    if (host) return;
    host = document.createElement("div");
    host.id = "tempoapply-widget-host";
    host.style.cssText = "all: initial; position: static;";
    root = host.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = STYLES;
    root.appendChild(style);
    const wrap = document.createElement("div");
    wrap.innerHTML = HTML;
    root.appendChild(wrap);
    (document.body || document.documentElement).appendChild(host);

    const q = (sel) => root.querySelector(sel);
    el = {
      panel: q(".panel"),
      head: q("[data-drag]"),
      job: q("[data-job]"),
      dot: q("[data-dot]"),
      fill: q("[data-fill]"),
      gate: q("[data-actions-gate]"),
      step: q("[data-step]"),
      results: q("[data-results]"),
      nOk: q("[data-n-ok]"),
      nLow: q("[data-n-low]"),
      nTodo: q("[data-n-todo]"),
      todo: q("[data-todo]"),
      msg: q("[data-msg]"),
      actions: q("[data-actions]"),
      refill: q("[data-refill]"),
      applied: q("[data-applied]"),
      toggle: q("[data-toggle]"),
      close: q("[data-close]"),
    };

    el.toggle.addEventListener("click", () => {
      const collapsed = el.panel.classList.toggle("collapsed");
      el.toggle.textContent = collapsed ? "+" : "–";
    });
    el.close.addEventListener("click", () => host.remove());
    makeDraggable();
  }

  function makeDraggable() {
    let startX = 0, startY = 0, originX = 0, originY = 0, dragging = false;
    el.head.addEventListener("mousedown", (e) => {
      if (e.target.closest(".icon-btn")) return;
      dragging = true;
      const rect = el.panel.getBoundingClientRect();
      startX = e.clientX; startY = e.clientY;
      originX = rect.left; originY = rect.top;
      e.preventDefault();
    });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const x = Math.max(4, Math.min(window.innerWidth - 60, originX + e.clientX - startX));
      const y = Math.max(4, Math.min(window.innerHeight - 40, originY + e.clientY - startY));
      el.panel.style.left = `${x}px`;
      el.panel.style.top = `${y}px`;
      el.panel.style.right = "auto";
      el.panel.style.bottom = "auto";
    });
    window.addEventListener("mouseup", () => { dragging = false; });
  }

  TA.widget = {
    mount(handlers) {
      build();
      el.fill.addEventListener("click", handlers.onFill);
      el.refill.addEventListener("click", handlers.onRefill);
      el.applied.addEventListener("click", handlers.onApplied);
      this.onTodoClick = handlers.onTodoClick;
    },

    isMounted: () => !!host && host.isConnected,

    setBackend(up, detail) {
      if (!host) return;
      el.dot.className = `dot ${up ? "up" : "down"}`;
      el.dot.title = detail || (up ? "backend connected" : "backend unreachable");
    },

    setJob(title, company, ats) {
      if (!host) return;
      const name = [title, company].filter(Boolean).join(" · ");
      el.job.innerHTML = name
        ? `<b>${escapeHtml(title || "")}</b>${company ? ` · ${escapeHtml(company)}` : ""}` +
          (ats && ats !== "unknown" ? `<br><span class="ats">${escapeHtml(ats)}</span>` : "")
        : "Ready on this page.";
    },

    /**
     * Portal gates (Workday's chooser, its sign-in step). Swaps the Autofill
     * button for the one thing that actually moves the user forward.
     */
    setStage(stage, handlers) {
      if (!host) return;
      el.step.hidden = !stage.step;
      el.step.textContent = stage.step || "";

      const actions = stage.actions || [];
      if (stage.stage === "gate" && actions.length) {
        el.fill.hidden = true;
        el.gate.hidden = false;
        el.gate.innerHTML = "";
        // First choice is the recommended one and gets the primary styling.
        actions.forEach((action, i) => {
          const btn = document.createElement("button");
          btn.className = `btn ${i === 0 ? "primary" : "ghost"}`;
          btn.textContent = action.label;
          btn.addEventListener("click", () => handlers.onAction(action.selector));
          el.gate.appendChild(btn);
        });
      } else {
        el.fill.hidden = false;
        el.gate.hidden = true;
        el.gate.innerHTML = "";
      }
    },

    setBusy(busy, label) {
      if (!host) return;
      el.fill.disabled = busy;
      el.refill.disabled = busy;
      el.fill.textContent = busy ? label || "Filling…" : "Autofill";
    },

    showResults({ filled, low, todo }) {
      if (!host) return;
      el.results.hidden = false;
      el.actions.hidden = false;
      el.nOk.textContent = filled;
      el.nLow.textContent = low;
      el.nTodo.textContent = todo;
      el.fill.textContent = "Autofill";
    },

    showTodo(labels) {
      if (!host) return;
      el.todo.innerHTML = "";
      el.todo.hidden = labels.length === 0;
      labels.forEach((label) => {
        const btn = document.createElement("button");
        btn.className = "todo-item";
        btn.textContent = label.length > 70 ? `${label.slice(0, 70)}…` : label;
        btn.addEventListener("click", () => this.onTodoClick && this.onTodoClick(label));
        el.todo.appendChild(btn);
      });
    },

    message(text, kind) {
      if (!host) return;
      el.msg.hidden = !text;
      el.msg.className = `msg ${kind || "info"}`;
      el.msg.innerHTML = text || "";
    },

    setAppliedLabel(text) {
      if (!host) return;
      el.applied.textContent = text;
    },
  };

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
})();
