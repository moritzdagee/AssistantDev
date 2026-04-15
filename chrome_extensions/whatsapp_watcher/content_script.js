/**
 * WhatsApp Watcher — Content Script
 * Runs on web.whatsapp.com, observes new messages via MutationObserver.
 * Batches new messages and sends them to localhost:8081/whatsapp/sync
 */

(function() {
  'use strict';

  const SYNC_URL = 'http://localhost:8081/whatsapp/sync';
  const BATCH_INTERVAL_MS = 5000;  // 5 seconds between batches
  const MAX_MSGS_PER_BATCH = 50;

  let pendingMessages = [];
  let lastBatchTime = 0;
  let observer = null;
  let currentContact = null;
  let isActive = true;

  // ── Robust selectors (ARIA/data-testid, not CSS classes) ──

  const SELECTORS = {
    messageContainer: '[data-testid="conversation-panel-messages"]',
    msgContainer: '[data-testid="msg-container"]',
    msgText: '[data-testid="msg-text"]',
    msgMeta: '[data-testid="msg-meta"]',
    chatHeader: 'header [data-testid="conversation-info-header-chat-title"]',
    chatHeaderAlt: 'header span[title]',
    msgOut: '.message-out',
    msgIn: '.message-in',
  };

  function getContactName() {
    let el = document.querySelector(SELECTORS.chatHeader);
    if (el) return el.textContent.trim();
    el = document.querySelector(SELECTORS.chatHeaderAlt);
    if (el) return el.getAttribute('title') || el.textContent.trim();
    return null;
  }

  function parseMessage(msgEl) {
    const textEl = msgEl.querySelector(SELECTORS.msgText);
    const metaEl = msgEl.querySelector(SELECTORS.msgMeta);

    const text = textEl ? textEl.textContent.trim() : '';
    const isMedia = !textEl && msgEl.querySelector('[data-testid="image-thumb"], [data-testid="video-thumb"], [data-testid="audio-player"]');
    const isOut = !!msgEl.closest('.message-out');

    let timestamp = '';
    if (metaEl) {
      const timeStr = metaEl.textContent.trim();
      // Build ISO timestamp from time string + today
      const now = new Date();
      const match = timeStr.match(/(\d{1,2}):(\d{2})/);
      if (match) {
        const h = parseInt(match[1]), m = parseInt(match[2]);
        now.setHours(h, m, 0, 0);
        timestamp = now.toISOString();
      }
    }

    if (!text && !isMedia) return null;

    return {
      sender: isOut ? 'Me' : (currentContact || 'Unknown'),
      timestamp: timestamp || new Date().toISOString(),
      text: text || '[Medien]',
      is_media: !!isMedia,
    };
  }

  function getExistingMessageIds() {
    const ids = new Set();
    document.querySelectorAll(SELECTORS.msgContainer).forEach(el => {
      const id = el.getAttribute('data-id');
      if (id) ids.add(id);
    });
    return ids;
  }

  function onNewMessages(mutations) {
    if (!isActive) return;

    const contact = getContactName();
    if (!contact) return;
    currentContact = contact;

    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType !== 1) continue;
        const msgEls = node.matches && node.matches(SELECTORS.msgContainer)
          ? [node]
          : node.querySelectorAll ? Array.from(node.querySelectorAll(SELECTORS.msgContainer)) : [];

        for (const msgEl of msgEls) {
          const msg = parseMessage(msgEl);
          if (msg) {
            pendingMessages.push(msg);
          }
        }
      }
    }

    // Throttle batches
    const now = Date.now();
    if (pendingMessages.length > 0 && (now - lastBatchTime) >= BATCH_INTERVAL_MS) {
      flushBatch();
    }
  }

  async function flushBatch() {
    if (pendingMessages.length === 0) return;

    const batch = pendingMessages.splice(0, MAX_MSGS_PER_BATCH);
    lastBatchTime = Date.now();

    const settings = await chrome.storage.local.get(['agent', 'paused']);
    if (settings.paused) return;
    const agent = settings.agent || 'privat';

    try {
      const resp = await fetch(SYNC_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent: agent,
          contact: currentContact,
          messages: batch,
          last_known_timestamp: batch[0].timestamp,
        }),
      });

      const data = await resp.json();
      if (data.status === 'success') {
        chrome.storage.local.set({
          lastSync: new Date().toISOString(),
          lastSyncCount: data.appended || 0,
          todayCount: ((await chrome.storage.local.get('todayCount')).todayCount || 0) + (data.appended || 0),
        });
      }
    } catch (e) {
      console.warn('[WA-Watcher] Sync failed:', e.message);
    }
  }

  function startObserving() {
    const container = document.querySelector(SELECTORS.messageContainer);
    if (!container) {
      // Retry after delay
      setTimeout(startObserving, 3000);
      return;
    }

    if (observer) observer.disconnect();
    observer = new MutationObserver(onNewMessages);
    observer.observe(container, { childList: true, subtree: true });
    console.log('[WA-Watcher] MutationObserver aktiv');
  }

  // Watch for chat switches (conversation panel changes)
  const panelObserver = new MutationObserver(() => {
    const container = document.querySelector(SELECTORS.messageContainer);
    if (container && (!observer || !container.contains(document.querySelector(SELECTORS.msgContainer)))) {
      startObserving();
    }
  });

  // Start
  const appRoot = document.getElementById('app') || document.body;
  panelObserver.observe(appRoot, { childList: true, subtree: true });
  startObserving();

  // Periodic flush
  setInterval(() => {
    if (pendingMessages.length > 0) flushBatch();
  }, BATCH_INTERVAL_MS);

  // Listen for messages from popup/background
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === 'syncNow') {
      flushBatch();
      sendResponse({ ok: true });
    } else if (msg.action === 'getStatus') {
      sendResponse({
        active: isActive,
        contact: currentContact,
        pending: pendingMessages.length,
      });
    } else if (msg.action === 'pause') {
      isActive = false;
      sendResponse({ ok: true });
    } else if (msg.action === 'resume') {
      isActive = true;
      sendResponse({ ok: true });
    }
  });

})();
