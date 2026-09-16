/**
 * Service worker: the only place that talks to the backend.
 *
 * Content scripts cannot fetch localhost from a page whose CSP forbids it
 * (Workday's does), so every request is proxied through here. It also routes
 * messages between frames, since a content script cannot address its siblings.
 */

const DEFAULT_API = "http://localhost:8000";
const TIMEOUT_MS = 12000;

async function apiBase() {
  const stored = await chrome.storage.local.get("apiBase");
  return (stored.apiBase || DEFAULT_API).replace(/\/+$/, "");
}

async function call(path, options) {
  const base = await apiBase();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${base}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(options && options.headers) },
    });
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        if (body && body.detail) detail = body.detail;
      } catch (e) {
        /* non-JSON error body */
      }
      return { ok: false, error: detail };
    }
    return { ok: true, data: await response.json() };
  } catch (e) {
    const message = e && e.name === "AbortError" ? "request timed out" : String(e && e.message ? e.message : e);
    return { ok: false, error: message };
  } finally {
    clearTimeout(timer);
  }
}

// Cache the resume — it is the same bytes on every form in a session. The TTL
// is what makes swapping in a new resume take effect on its own, without
// reloading the extension.
const RESUME_TTL_MS = 5 * 60 * 1000;
let resumeCache = null;
let resumeCachedAt = 0;

async function getResume() {
  if (resumeCache && Date.now() - resumeCachedAt < RESUME_TTL_MS) {
    return { ok: true, data: resumeCache };
  }
  const result = await call("/api/autofill/resume");
  if (result.ok) {
    resumeCache = result.data;
    resumeCachedAt = Date.now();
  }
  return result;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    switch (message.type) {
      case "ping":
        sendResponse(await call("/api/autofill/ping"));
        return;

      case "resolve":
        sendResponse(
          await call("/api/autofill/resolve", {
            method: "POST",
            body: JSON.stringify(message.payload),
          })
        );
        return;

      case "resume":
        sendResponse(await getResume());
        return;

      case "track":
        sendResponse(
          await call("/api/autofill/track", {
            method: "POST",
            body: JSON.stringify(message.payload),
          })
        );
        return;

      // Top frame -> every frame in the same tab.
      case "broadcast": {
        const tabId = sender.tab && sender.tab.id;
        if (tabId != null) {
          try {
            await chrome.tabs.sendMessage(tabId, message.message);
          } catch (e) {
            /* frames without our content script simply do not answer */
          }
        }
        sendResponse({ ok: true });
        return;
      }

      // Child frame -> top frame: "I am about to fill, wait for me".
      case "starting": {
        const tabId = sender.tab && sender.tab.id;
        if (tabId != null) {
          try {
            await chrome.tabs.sendMessage(tabId, { type: "TA_FRAME_STARTING" }, { frameId: 0 });
          } catch (e) {
            /* top frame gone */
          }
        }
        sendResponse({ ok: true });
        return;
      }

      // Child frame -> top frame.
      case "report": {
        const tabId = sender.tab && sender.tab.id;
        if (tabId != null) {
          try {
            await chrome.tabs.sendMessage(tabId, { type: "TA_REPORT", result: message.result }, { frameId: 0 });
          } catch (e) {
            /* top frame gone */
          }
        }
        sendResponse({ ok: true });
        return;
      }

      case "setApiBase":
        await chrome.storage.local.set({ apiBase: message.value });
        resumeCache = null;
        sendResponse({ ok: true });
        return;

      case "getApiBase":
        sendResponse({ ok: true, data: { apiBase: await apiBase() } });
        return;

      case "clearResumeCache":
        resumeCache = null;
        sendResponse({ ok: true });
        return;

      default:
        sendResponse({ ok: false, error: `unknown message ${message.type}` });
    }
  })();
  return true; // keep the channel open for the async reply
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "autofill") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || tab.id == null) return;
  try {
    await chrome.tabs.sendMessage(tab.id, { type: "TA_RUN", opts: {} }, { frameId: 0 });
  } catch (e) {
    /* no content script on this page */
  }
});
