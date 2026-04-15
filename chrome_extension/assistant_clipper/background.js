/*
 * Assistant Memory Clipper v2 — Background Service Worker
 * Handles:
 * 1. Extension icon click → triggers content_script extraction
 * 2. Fetches agent list from localhost:8081
 * 3. Captures full-page screenshot via chrome.debugger API
 * 4. Saves structured JSON + PNG to agent memory via localhost:8081/save
 */

const SERVER = 'http://127.0.0.1:8081';

// ─── EXTENSION ICON CLICK ────────────────────────────────────────────────────

chrome.action.onClicked.addListener(async (tab) => {
  console.log('[Clipper] Icon clicked, tab:', tab.id, tab.url);
  try {
    await chrome.tabs.sendMessage(tab.id, { action: 'clip' });
  } catch (e) {
    console.log('[Clipper] Content script not loaded, injecting...', e.message);
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content_script.js'],
      });
      setTimeout(async () => {
        try {
          await chrome.tabs.sendMessage(tab.id, { action: 'clip' });
        } catch (e2) {
          console.error('[Clipper] Could not send message after inject:', e2);
        }
      }, 300);
    } catch (e3) {
      console.error('[Clipper] Could not inject content script:', e3);
    }
  }
});

// ─── FULL-PAGE SCREENSHOT ───────────────────────────────────────────────────

async function captureFullPageScreenshot(tabId) {
  const MAX_HEIGHT = 15000;

  try {
    // Attach debugger
    await chrome.debugger.attach({ tabId }, '1.3');

    try {
      // Trigger lazy-loading by scrolling through the page
      await chrome.debugger.sendCommand({ tabId }, 'Runtime.evaluate', {
        expression: `(async () => {
          const h = Math.min(document.body.scrollHeight, ${MAX_HEIGHT});
          const step = window.innerHeight;
          for (let y = 0; y < h; y += step) {
            window.scrollTo(0, y);
            await new Promise(r => setTimeout(r, 100));
          }
          window.scrollTo(0, 0);
          await new Promise(r => setTimeout(r, 300));
        })()`
      });

      // Wait for lazy content to load
      await new Promise(r => setTimeout(r, 500));

      // Get page dimensions
      const metrics = await chrome.debugger.sendCommand({ tabId }, 'Page.getLayoutMetrics');
      const width = Math.ceil(Math.min(metrics.contentSize.width, 1920));
      const height = Math.ceil(Math.min(metrics.contentSize.height, MAX_HEIGHT));

      // Override viewport to full page
      await chrome.debugger.sendCommand({ tabId }, 'Emulation.setDeviceMetricsOverride', {
        width,
        height,
        deviceScaleFactor: 1,
        mobile: false,
      });

      // Small delay for render
      await new Promise(r => setTimeout(r, 200));

      // Capture
      const result = await chrome.debugger.sendCommand({ tabId }, 'Page.captureScreenshot', {
        format: 'png',
        captureBeyondViewport: true,
      });

      // Reset viewport
      await chrome.debugger.sendCommand({ tabId }, 'Emulation.clearDeviceMetricsOverride');

      console.log('[Clipper] Screenshot captured via debugger, base64 length:', result.data.length);
      return result.data;

    } finally {
      await chrome.debugger.detach({ tabId }).catch(() => {});
    }

  } catch (err) {
    console.warn('[Clipper] Debugger screenshot failed, trying fallback:', err.message);

    // Fallback: capture visible tab only
    try {
      const dataUrl = await chrome.tabs.captureVisibleTab(null, { format: 'png' });
      const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
      console.log('[Clipper] Fallback screenshot captured, base64 length:', base64.length);
      return base64;
    } catch (fallbackErr) {
      console.error('[Clipper] Fallback screenshot also failed:', fallbackErr.message);
      return null;
    }
  }
}

// ─── MESSAGE HANDLER ─────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  console.log('[Clipper] Message received:', msg.action);

  if (msg.action === 'getAgents') {
    fetchAgents().then(agents => {
      sendResponse({ agents });
    }).catch(err => {
      sendResponse({ agents: [], error: err.message });
    });
    return true;
  }

  if (msg.action === 'save') {
    (async () => {
      try {
        // Step 1: Capture screenshot (if we have a tab)
        let screenshot = null;
        if (sender && sender.tab && sender.tab.id) {
          try {
            screenshot = await captureFullPageScreenshot(sender.tab.id);
          } catch (e) {
            console.warn('[Clipper] Screenshot skipped:', e.message);
          }
        }

        // Step 2: Build payload and send to server
        const payload = {
          agent: msg.agent,
          url: msg.url || '',
          title: msg.title || '',
          timestamp: msg.timestamp || new Date().toISOString(),
          extracted_data: msg.extracted_data || null,
          full_text: msg.full_text || msg.content || '',
          filename: msg.filename || '',
          screenshot_png_base64: screenshot,
        };

        // Detect format: new (has extracted_data) vs legacy (has content string only)
        if (!msg.extracted_data && msg.content) {
          // Legacy format — send as old-style {agent, content, filename}
          payload.content = msg.content;
          delete payload.extracted_data;
          delete payload.full_text;
          delete payload.screenshot_png_base64;
        }

        const result = await saveToServer(payload);
        sendResponse(result);
      } catch (err) {
        console.error('[Clipper] Save pipeline error:', err);
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true;
  }
});

// ─── API CALLS ───────────────────────────────────────────────────────────────

async function fetchAgents() {
  try {
    const r = await fetch(SERVER + '/agents', { signal: AbortSignal.timeout(5000) });
    const data = await r.json();
    return data.agents || [];
  } catch (e) {
    console.error('[Clipper] Failed to fetch agents:', e);
    return [];
  }
}

async function saveToServer(payload) {
  try {
    const bodyStr = JSON.stringify(payload);
    console.log('[Clipper] Sending to server, payload size:', Math.round(bodyStr.length / 1024), 'KB');

    const r = await fetch(SERVER + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: bodyStr,
      signal: AbortSignal.timeout(30000),
    });

    const data = await r.json();
    console.log('[Clipper] Save response:', data);

    if (data.success) {
      return {
        success: true,
        saved_to: data.saved_to,
        saved_to_agent: data.saved_to_agent,
        saved_to_global: data.saved_to_global,
        screenshot_saved: data.screenshot_saved || false,
      };
    }
    return { success: false, error: data.error || 'Server-Fehler' };
  } catch (e) {
    console.error('[Clipper] Save fetch error:', e);
    return { success: false, error: 'Web Clipper Server nicht erreichbar. Laeuft localhost:8081?' };
  }
}
