/*
 * Assistant Memory Clipper v2 — Content Script
 * Full structured extraction with site-specific handlers.
 * Sends structured JSON to background.js for saving + screenshot.
 */

// ─── HELPERS ────────────────────────────────────────────────────────────────

function queryShadowAll(root, selector) {
  let results = [...root.querySelectorAll(selector)];
  const MAX_DEPTH = 5;
  function recurse(el, depth) {
    if (depth > MAX_DEPTH) return;
    if (el.shadowRoot) {
      results = results.concat([...el.shadowRoot.querySelectorAll(selector)]);
      el.shadowRoot.querySelectorAll('*').forEach(child => recurse(child, depth + 1));
    }
  }
  root.querySelectorAll('*').forEach(el => recurse(el, 0));
  return results;
}

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function safeName(str, maxLen) {
  return str.replace(/[^a-zA-Z0-9 _-]/g, '').replace(/\s+/g, '_').substring(0, maxLen || 40);
}

function datestamp() {
  // YYYY-MM-DD_HH-MM-SS for unique filenames on same-day clips
  return new Date().toISOString().replace('T', '_').replace(/:/g, '-').substring(0, 19);
}

// ─── COMMON PAGE METADATA ───────────────────────────────────────────────────

function extractPageMetadata() {
  const meta = {};

  meta.title = document.title || '';
  meta.url = location.href;
  meta.lastModified = document.lastModified || '';
  meta.timestamp = new Date().toISOString();

  // Meta tags
  meta.metaTags = [];
  document.querySelectorAll('meta[name], meta[property], meta[http-equiv]').forEach(el => {
    const name = el.getAttribute('name') || el.getAttribute('property') || el.getAttribute('http-equiv') || '';
    const content = el.getAttribute('content') || '';
    if (name && content) meta.metaTags.push({ name, content });
  });

  // Headings H1-H6
  meta.headings = [];
  document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(el => {
    const text = el.textContent.trim();
    if (text) meta.headings.push({ level: parseInt(el.tagName[1]), text: text.substring(0, 200) });
  });

  // Links (deduplicated, max 500)
  const seenLinks = new Set();
  meta.links = [];
  document.querySelectorAll('a[href]').forEach(el => {
    const href = el.href;
    if (href && !seenLinks.has(href) && meta.links.length < 500) {
      seenLinks.add(href);
      meta.links.push({ text: (el.textContent || '').trim().substring(0, 100), href });
    }
  });

  // Images with alt text (max 200)
  meta.images = [];
  document.querySelectorAll('img[src]').forEach(el => {
    if (meta.images.length < 200) {
      meta.images.push({ src: el.src, alt: (el.alt || '').substring(0, 200) });
    }
  });

  // Tables (max 20)
  meta.tables = [];
  document.querySelectorAll('table').forEach(table => {
    if (meta.tables.length >= 20) return;
    const rows = [];
    table.querySelectorAll('tr').forEach(tr => {
      const cells = [];
      tr.querySelectorAll('th, td').forEach(cell => cells.push(cell.textContent.trim().substring(0, 200)));
      if (cells.length) rows.push(cells);
    });
    if (rows.length) {
      meta.tables.push({ headers: rows[0] || [], rows: rows.slice(1) });
    }
  });

  // Form fields
  meta.forms = [];
  document.querySelectorAll('input, select, textarea').forEach(el => {
    if (meta.forms.length < 100) {
      const label = el.labels && el.labels[0] ? el.labels[0].textContent.trim() : (el.placeholder || el.name || '');
      meta.forms.push({ label, type: el.type || el.tagName.toLowerCase(), value: (el.value || '').substring(0, 200) });
    }
  });

  return meta;
}

// ─── SITE DETECTION ─────────────────────────────────────────────────────────

function detectSiteType() {
  const host = location.hostname;
  const url = location.href;

  if (host.includes('salesforce.com') || host.includes('force.com')) {
    let typ = 'Record';
    if (url.includes('/Lead/')) typ = 'Lead';
    else if (url.includes('/Account/')) typ = 'Account';
    else if (url.includes('/Opportunity/')) typ = 'Opportunity';
    else if (url.includes('/Contact/')) typ = 'Contact';
    else if (url.includes('/Case/')) typ = 'Case';
    return { site: 'salesforce', subtype: typ, icon: '\uD83C\uDFE2' };
  }

  if (host.includes('slack.com')) {
    return { site: 'slack', subtype: 'channel', icon: '\uD83D\uDCAC' };
  }

  if (host.includes('linkedin.com')) {
    let typ = url.includes('/in/') ? 'Profile' : 'Post';
    return { site: 'linkedin', subtype: typ, icon: '\uD83D\uDC64' };
  }

  return { site: 'web', subtype: 'page', icon: '\uD83C\uDF10' };
}

// ─── SALESFORCE EXTRACTION ──────────────────────────────────────────────────

function extractSalesforce(subtype) {
  const url = location.href;

  const nameEl = queryShadowAll(document, 'h1 .uiOutputText, h1 lightning-formatted-text, h1, .slds-page-header__title')[0];
  const recordName = nameEl ? nameEl.textContent.trim() : document.title.replace(' | Salesforce', '').trim();

  const idMatch = url.match(/\/([a-zA-Z0-9]{15,18})(?:\/|$)/);
  const recordId = idMatch ? idMatch[1] : '';

  const fields = [];
  const seen = {};

  function addField(label, value) {
    const l = (label || '').trim().replace(/\n/g, ' ');
    const v = (value || '').trim().replace(/\n/g, ' ');
    if (l && v && l !== v && !seen[l + v]) {
      seen[l + v] = 1;
      fields.push({ label: l, value: v });
    }
  }

  // Method 1: slds-form-element (+ shadow DOM)
  queryShadowAll(document, '.slds-form-element').forEach(el => {
    const l = el.querySelector('.slds-form-element__label, .test-id__field-label');
    const v = el.querySelector('.slds-form-element__static, .test-id__field-value, lightning-formatted-text, lightning-formatted-email, lightning-formatted-phone, lightning-formatted-url, lightning-formatted-name, a');
    if (l && v) addField(l.textContent, v.textContent);
  });

  // Method 2: dt/dd pairs
  queryShadowAll(document, 'dt').forEach(dt => {
    const dd = dt.nextElementSibling;
    if (dd && dd.tagName === 'DD') addField(dt.textContent, dd.textContent);
  });

  // Method 3: records-highlights
  queryShadowAll(document, 'records-highlights-details-item, records-record-layout-item').forEach(el => {
    const l = el.querySelector('.slds-form-element__label, span.test-id__field-label');
    const v = el.querySelector('.slds-form-element__static, .test-id__field-value');
    if (l && v) addField(l.textContent, v.textContent);
  });

  // Related Lists
  const relatedLists = [];
  queryShadowAll(document, '.slds-card, force-related-list-single-container, lst-related-list-single-container').forEach(card => {
    const titleEl = card.querySelector('.slds-card__header-title, .slds-text-heading--small, h2');
    const title = titleEl ? titleEl.textContent.trim() : '';
    if (!title) return;
    const items = [];
    card.querySelectorAll('tr, .slds-item').forEach(row => {
      const text = row.textContent.trim().replace(/\s+/g, ' ').substring(0, 300);
      if (text && text.length > 5) items.push(text);
    });
    if (items.length) relatedLists.push({ title, items });
  });

  // Activity Timeline
  const activities = [];
  queryShadowAll(document, '.activityTimelineItem, .forceActivityTimelineItem, timeline-item-occurrence').forEach(item => {
    const text = item.textContent.trim().replace(/\s+/g, ' ').substring(0, 300);
    if (text && !seen['act_' + text.substring(0, 50)]) {
      seen['act_' + text.substring(0, 50)] = 1;
      activities.push(text);
    }
  });

  // Chatter Feed
  const chatter = [];
  queryShadowAll(document, '.cuf-feedItem, .forceChatterFeedItem, feed-item-component').forEach(item => {
    const text = item.textContent.trim().replace(/\s+/g, ' ').substring(0, 500);
    if (text) chatter.push(text);
  });

  const pageMetadata = extractPageMetadata();
  const fieldTexts = fields.map(f => f.label + ': ' + f.value);
  const fullText = [
    'SALESFORCE ' + subtype.toUpperCase() + ': ' + recordName,
    'URL: ' + url,
    ...fieldTexts,
    ...activities.map(a => '[Activity] ' + a),
    ...chatter.map(c => '[Chatter] ' + c),
  ].join('\n');

  const filename = 'salesforce_' + subtype.toLowerCase() + '_' + safeName(recordName) + '_' + datestamp() + '.json';

  return {
    title: subtype + ': ' + recordName,
    preview: fieldTexts.slice(0, 3).join('\n'),
    fieldCount: fields.length,
    filename,
    extracted_data: {
      site_type: 'salesforce', subtype, record_name: recordName, record_id: recordId,
      fields, related_lists: relatedLists, activity_timeline: activities, chatter_feed: chatter,
      page_metadata: pageMetadata,
    },
    full_text: fullText.substring(0, 50000),
  };
}

// ─── SLACK EXTRACTION ───────────────────────────────────────────────────────

function extractSlack() {
  const url = location.href;

  const channelEl = document.querySelector(
    '[data-qa="channel_name"], .p-classic_nav__model__title__name__button, ' +
    '.p-view_header__channel_title button, [data-sidebar-channel-id].p-channel_sidebar__channel--selected'
  );
  const channelName = channelEl ? channelEl.textContent.trim() : 'unknown';

  const topicEl = document.querySelector('[data-qa="channel_topic"], .p-view_header__topic');
  const channelTopic = topicEl ? topicEl.textContent.trim() : '';

  const messages = [];
  document.querySelectorAll('.c-message_kit__message, [data-qa="message_container"], .c-virtual_list__item').forEach(msg => {
    const authorEl = msg.querySelector('.c-message__sender button, [data-qa="message_sender_name"], .c-message_kit__sender');
    const textEl = msg.querySelector('.c-message_kit__text, [data-qa="message-text"], .p-rich_text_section');
    const timeEl = msg.querySelector('.c-timestamp, [data-qa="message_time"], time');

    if (textEl) {
      const author = authorEl ? authorEl.textContent.trim() : '?';
      const text = textEl.textContent.trim().substring(0, 1000);
      const time = timeEl ? (timeEl.getAttribute('datetime') || timeEl.textContent.trim()) : '';

      const reactions = [];
      msg.querySelectorAll('.c-reaction, [data-qa="reaction"]').forEach(r => {
        const emoji = r.querySelector('.c-emoji, img') ? (r.querySelector('.c-emoji, img').alt || r.querySelector('.c-emoji, img').getAttribute('data-emoji') || '') : '';
        const count = r.querySelector('.c-reaction__count, [data-qa="reaction_count"]');
        reactions.push({ emoji, count: count ? parseInt(count.textContent) || 1 : 1 });
      });

      const threadEl = msg.querySelector('.c-message__reply_count, [data-qa="reply_count"]');
      const threadCount = threadEl ? parseInt(threadEl.textContent) || 0 : 0;

      if (text) messages.push({ author, time, text, reactions, thread_reply_count: threadCount });
    }
  });

  const pageMetadata = extractPageMetadata();
  const fullText = [
    'SLACK: #' + channelName,
    channelTopic ? 'Topic: ' + channelTopic : '',
    'URL: ' + url, '',
    ...messages.map(m => '[' + m.time + '] ' + m.author + ': ' + m.text),
  ].filter(Boolean).join('\n');

  const filename = 'slack_' + safeName(channelName) + '_' + datestamp() + '.json';

  return {
    title: '#' + channelName,
    preview: messages.slice(0, 3).map(m => m.author + ': ' + m.text.substring(0, 80)).join('\n'),
    fieldCount: messages.length,
    filename,
    extracted_data: {
      site_type: 'slack', channel_name: channelName, channel_topic: channelTopic,
      messages, page_metadata: pageMetadata,
    },
    full_text: fullText.substring(0, 50000),
  };
}

// ─── LINKEDIN EXTRACTION ────────────────────────────────────────────────────

function extractLinkedIn(subtype) {
  const url = location.href;

  if (subtype === 'Profile') {
    const nameEl = document.querySelector('.text-heading-xlarge, .pv-top-card h1, h1');
    const name = nameEl ? nameEl.textContent.trim() : '';
    const headlineEl = document.querySelector('.text-body-medium, .pv-top-card .text-body-medium');
    const headline = headlineEl ? headlineEl.textContent.trim() : '';
    const locationEl = document.querySelector('.text-body-small .inline-show-more-text, .pv-top-card--experience-list .text-body-small');
    const loc = locationEl ? locationEl.textContent.trim() : '';
    const aboutEl = document.querySelector('.pv-about-section .inline-show-more-text, [data-section="summary"] .visually-hidden, .pv-shared-text-with-see-more span[aria-hidden="true"]');
    const about = aboutEl ? aboutEl.textContent.trim() : '';

    const experience = [];
    document.querySelectorAll('.pvs-list__paged-list-item, .pv-entity__position-group, li.artdeco-list__item').forEach(item => {
      const text = item.textContent.trim().replace(/\s+/g, ' ').substring(0, 500);
      if (text && text.length > 10) experience.push(text);
    });

    const pageMetadata = extractPageMetadata();
    const fullText = ['LINKEDIN PROFILE: ' + name, headline, loc, about ? 'About: ' + about : '', 'URL: ' + url,
      ...experience.map(e => '[Experience] ' + e)].filter(Boolean).join('\n');
    const filename = 'linkedin_profile_' + safeName(name) + '_' + datestamp() + '.json';

    return {
      title: 'Profile: ' + name, preview: [name, headline, loc].filter(Boolean).join('\n'),
      fieldCount: experience.length + 3, filename,
      extracted_data: { site_type: 'linkedin', subtype: 'profile', name, headline, location: loc, about, experience, page_metadata: pageMetadata },
      full_text: fullText.substring(0, 50000),
    };
  }

  // Post/Feed
  const postEl = document.querySelector('.feed-shared-update-v2__description, .feed-shared-text, .update-components-text');
  const postText = postEl ? postEl.textContent.trim() : '';
  const authorEl = document.querySelector('.update-components-actor__name, .feed-shared-actor__name');
  const author = authorEl ? authorEl.textContent.trim() : '';
  const pageMetadata = extractPageMetadata();
  const fullText = ['LINKEDIN POST by ' + author, postText, 'URL: ' + url].join('\n');
  const filename = 'linkedin_post_' + safeName(author) + '_' + datestamp() + '.json';

  return {
    title: 'Post: ' + author, preview: postText.substring(0, 200), fieldCount: 1, filename,
    extracted_data: { site_type: 'linkedin', subtype: 'post', author, text: postText, page_metadata: pageMetadata },
    full_text: fullText.substring(0, 50000),
  };
}

// ─── WEB EXTRACTION (DEFAULT) ───────────────────────────────────────────────

function extractWeb() {
  const url = location.href;
  const title = document.title.trim();

  const sections = [];
  document.querySelectorAll('article, main, section, aside').forEach(el => {
    const tagName = el.tagName.toLowerCase();
    const heading = el.querySelector('h1, h2, h3');
    const headingText = heading ? heading.textContent.trim() : '';
    const text = el.textContent.trim().replace(/\s+/g, ' ').substring(0, 5000);
    if (text.length > 20) sections.push({ tag: tagName, heading: headingText, text });
  });

  const clone = document.body.cloneNode(true);
  clone.querySelectorAll(
    'script, style, nav, footer, header, .nav, .footer, .header, .sidebar, ' +
    '.menu, .ad, .advertisement, .cookie-banner, [role="navigation"], [role="banner"]'
  ).forEach(el => el.remove());
  const bodyText = (clone.textContent || '').replace(/\s+/g, ' ').trim();

  const pageMetadata = extractPageMetadata();
  const filename = 'web_' + safeName(title) + '_' + datestamp() + '.json';

  return {
    title: title.substring(0, 80), preview: bodyText.substring(0, 200),
    fieldCount: sections.length || Math.round(bodyText.length / 100), filename,
    extracted_data: { site_type: 'web', sections, page_metadata: pageMetadata },
    full_text: bodyText.substring(0, 50000),
  };
}

// ─── SMART EXTRACT DISPATCHER ───────────────────────────────────────────────

function smartExtract() {
  const siteInfo = detectSiteType();
  let data;
  switch (siteInfo.site) {
    case 'salesforce': data = extractSalesforce(siteInfo.subtype); break;
    case 'slack': data = extractSlack(); break;
    case 'linkedin': data = extractLinkedIn(siteInfo.subtype); break;
    default: data = extractWeb();
  }
  return { ...siteInfo, ...data };
}

// ─── POPUP UI ───────────────────────────────────────────────────────────────

function showClipperPanel(extracted) {
  if (document.getElementById('ac-clipper-overlay')) return;

  const overlay = document.createElement('div');
  overlay.id = 'ac-clipper-overlay';
  overlay.style.cssText =
    'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:2147483647;' +
    'display:flex;align-items:flex-start;justify-content:flex-end;padding:16px;' +
    'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;';

  const panel = document.createElement('div');
  panel.style.cssText =
    'background:#1a1a1a;border:1px solid #444;border-radius:12px;padding:20px;' +
    'width:380px;color:#ddd;box-shadow:0 20px 60px rgba(0,0,0,0.5);';

  const countLabel = extracted.site === 'slack' ? ' Nachrichten' : ' Felder';

  panel.innerHTML =
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">' +
      '<div style="font-size:15px;font-weight:700;">' + extracted.icon + ' Assistant Memory Clipper v2</div>' +
      '<button id="ac-close" style="background:none;border:none;color:#666;font-size:18px;cursor:pointer;padding:0 4px;">\u2715</button>' +
    '</div>' +
    '<div style="font-size:12px;color:#f0c060;margin-bottom:10px;font-weight:600;">' +
      extracted.icon + ' ' + escHtml(extracted.title) + ' (' + extracted.fieldCount + countLabel + ')' +
    '</div>' +
    '<div style="font-size:10px;color:#666;margin-bottom:8px;">+ Screenshot + Meta + Links + Tabellen</div>' +
    '<div style="margin-bottom:10px;">' +
      '<label style="font-size:11px;color:#888;display:block;margin-bottom:3px;">Agent:</label>' +
      '<select id="ac-agent" style="width:100%;padding:7px;background:#222;border:1px solid #444;color:#ddd;border-radius:6px;font-size:13px;">' +
        '<option value="">Lade...</option>' +
      '</select>' +
    '</div>' +
    '<div style="margin-bottom:10px;">' +
      '<label style="font-size:11px;color:#888;display:block;margin-bottom:3px;">Dateiname:</label>' +
      '<input id="ac-filename" type="text" value="' + escHtml(extracted.filename) + '" ' +
        'style="width:100%;padding:7px;background:#222;border:1px solid #444;color:#ddd;border-radius:6px;font-size:12px;box-sizing:border-box;" />' +
    '</div>' +
    '<div style="font-size:11px;color:#555;margin-bottom:14px;max-height:80px;overflow-y:auto;' +
      'background:#111;padding:8px;border-radius:6px;white-space:pre-wrap;line-height:1.4;">' +
      escHtml(extracted.preview || '(kein Inhalt)') +
    '</div>' +
    '<div id="ac-status" style="font-size:11px;color:#888;margin-bottom:10px;display:none;"></div>' +
    '<div style="display:flex;gap:8px;justify-content:flex-end;">' +
      '<button id="ac-cancel" style="padding:7px 14px;background:#333;border:1px solid #555;color:#ccc;border-radius:6px;cursor:pointer;font-size:12px;">Abbrechen</button>' +
      '<button id="ac-save" style="padding:7px 14px;background:#f0c060;border:none;color:#111;border-radius:6px;cursor:pointer;font-size:12px;font-weight:700;">\uD83D\uDCBE Speichern</button>' +
    '</div>';

  overlay.appendChild(panel);
  document.body.appendChild(overlay);

  // Load agents
  const agentSelect = document.getElementById('ac-agent');
  chrome.runtime.sendMessage({ action: 'getAgents' }, response => {
    if (response && response.agents && response.agents.length) {
      agentSelect.innerHTML = '';
      response.agents.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a;
        opt.textContent = a;
        agentSelect.appendChild(opt);
      });
      const pre = response.agents.find(a => a === 'signicat');
      if (pre) agentSelect.value = pre;
    } else {
      agentSelect.innerHTML = '<option value="signicat">signicat</option>' +
        '<option value="privat">privat</option>' +
        '<option value="trustedcarrier">trustedcarrier</option>';
    }
  });

  const close = () => overlay.remove();
  document.getElementById('ac-close').onclick = close;
  document.getElementById('ac-cancel').onclick = close;
  overlay.onclick = e => { if (e.target === overlay) close(); };

  // Save handler — sends to background which captures screenshot + saves
  document.getElementById('ac-save').onclick = () => {
    const agent = agentSelect.value;
    const filename = document.getElementById('ac-filename').value.trim();
    if (!agent) { alert('Bitte Agent auswaehlen'); return; }

    // Remove overlay FIRST so the screenshot captures the clean page
    close();
    showToast('\u23F3 Screenshot + Speichern...', false);

    // Wait for overlay to be fully removed from rendering before screenshot
    setTimeout(() => {
      chrome.runtime.sendMessage({
        action: 'save',
        agent,
        url: location.href,
        title: extracted.title,
        timestamp: new Date().toISOString(),
        extracted_data: extracted.extracted_data,
        full_text: extracted.full_text,
        filename: filename || extracted.filename,
      }, response => {
        if (chrome.runtime.lastError) {
          showToast('\u2717 Extension-Fehler: ' + chrome.runtime.lastError.message, true);
          return;
        }
        if (response && response.success) {
          const info = response.screenshot_saved ? ' + Screenshot' : '';
          showToast('\u2713 Gespeichert in ' + agent + ' + globales Memory' + info, false);
        } else {
          showToast('\u2717 ' + (response && response.error || 'Fehler beim Speichern'), true);
        }
      });
    }, 300);
  };
}

// ─── TOAST ──────────────────────────────────────────────────────────────────

function showToast(msg, isError) {
  const t = document.createElement('div');
  t.style.cssText =
    'position:fixed;top:20px;right:20px;padding:12px 24px;border-radius:8px;font-size:14px;' +
    'font-weight:600;z-index:2147483647;font-family:-apple-system,sans-serif;' +
    'box-shadow:0 4px 20px rgba(0,0,0,0.3);transition:opacity 0.3s;';
  t.style.background = isError ? '#cc3333' : '#2d8a4e';
  t.style.color = '#fff';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; }, 2500);
  setTimeout(() => { t.remove(); }, 2800);
}

// ─── MESSAGE HANDLER ────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'clip') {
    const extracted = smartExtract();
    showClipperPanel(extracted);
    sendResponse({ ok: true });
  }
});
