/**
 * WhatsApp Watcher — Background Service Worker
 * Periodic check via alarms, manages extension state.
 */

chrome.alarms.create('wa-check', { periodInMinutes: 1 });

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== 'wa-check') return;

  // Find WhatsApp Web tabs
  const tabs = await chrome.tabs.query({ url: 'https://web.whatsapp.com/*' });
  if (tabs.length === 0) return;

  const settings = await chrome.storage.local.get(['paused']);
  if (settings.paused) return;

  // Ping content script to flush any pending messages
  for (const tab of tabs) {
    try {
      chrome.tabs.sendMessage(tab.id, { action: 'syncNow' });
    } catch (e) {
      // Tab might not have content script loaded
    }
  }
});

// Reset daily counter at midnight
chrome.alarms.create('wa-daily-reset', { periodInMinutes: 60 });
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== 'wa-daily-reset') return;
  const now = new Date();
  if (now.getHours() === 0 && now.getMinutes() < 60) {
    chrome.storage.local.set({ todayCount: 0 });
  }
});
