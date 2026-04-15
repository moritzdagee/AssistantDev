/*
 * Salesforce Clipper Bookmarklet
 * Extrahiert Daten aus Salesforce Lightning und speichert sie
 * via Web Clipper Server (localhost:8081) in den Agent-Memory.
 *
 * Problem: Salesforce CSP blockiert fetch() zu localhost.
 * Loesung: Daten per DOM extrahieren, dann in einem neuen
 *          about:blank Tab senden und sofort schliessen.
 *
 * Installation: Den BOOKMARKLET-Code ganz unten als Bookmark-URL einfuegen.
 */

(function() {
  // --- Prevent double-run ---
  if (document.getElementById('sf-clipper-overlay')) return;

  // --- Extract page type from URL ---
  var url = location.href;
  var typ = 'Record';
  if (url.includes('/Lead/')) typ = 'Lead';
  else if (url.includes('/Account/')) typ = 'Account';
  else if (url.includes('/Opportunity/')) typ = 'Opportunity';
  else if (url.includes('/Contact/')) typ = 'Contact';
  else if (url.includes('/Case/')) typ = 'Case';

  // --- Extract record name ---
  var nameEl = document.querySelector('h1 .uiOutputText, h1 lightning-formatted-text, h1 slot lightning-formatted-text, h1, .slds-page-header__title');
  var recordName = nameEl ? nameEl.textContent.trim() : document.title.replace(' | Salesforce', '').trim();

  // --- Extract form fields ---
  var fields = [];

  // Method 1: slds-form-element labels + values
  document.querySelectorAll('.slds-form-element').forEach(function(el) {
    var labelEl = el.querySelector('.slds-form-element__label, .test-id__field-label');
    var valueEl = el.querySelector('.slds-form-element__static, .test-id__field-value, lightning-formatted-text, lightning-formatted-email, lightning-formatted-phone, lightning-formatted-url, lightning-formatted-name, a');
    if (labelEl && valueEl) {
      var label = labelEl.textContent.trim().replace(/\n/g, ' ');
      var value = valueEl.textContent.trim().replace(/\n/g, ' ');
      if (label && value && label !== value) {
        fields.push(label + ': ' + value);
      }
    }
  });

  // Method 2: dt/dd pairs
  document.querySelectorAll('dt').forEach(function(dt) {
    var dd = dt.nextElementSibling;
    if (dd && dd.tagName === 'DD') {
      var label = dt.textContent.trim();
      var value = dd.textContent.trim();
      if (label && value) {
        fields.push(label + ': ' + value);
      }
    }
  });

  // Method 3: records-highlights fields
  document.querySelectorAll('records-highlights-details-item, records-record-layout-item').forEach(function(el) {
    var labelEl = el.querySelector('.slds-form-element__label, span.test-id__field-label');
    var valueEl = el.querySelector('.slds-form-element__static, .test-id__field-value');
    if (labelEl && valueEl) {
      var label = labelEl.textContent.trim();
      var value = valueEl.textContent.trim();
      if (label && value && !fields.some(function(f) { return f.startsWith(label + ':'); })) {
        fields.push(label + ': ' + value);
      }
    }
  });

  // Deduplicate
  var seen = {};
  fields = fields.filter(function(f) {
    if (seen[f]) return false;
    seen[f] = true;
    return true;
  });

  // --- Build content ---
  var datum = new Date().toISOString().replace('T', ' ').substring(0, 19);
  var safeName = recordName.replace(/[^a-zA-Z0-9 _-]/g, '').replace(/\s+/g, '_').substring(0, 40);
  var datestamp = new Date().toISOString().substring(0, 10);

  var content = '=== SALESFORCE ' + typ.toUpperCase() + ': ' + recordName + ' ===\n';
  content += 'URL: ' + url + '\n';
  content += 'Exportiert: ' + datum + '\n\n';
  content += fields.join('\n') + '\n';

  var filename = 'salesforce_' + typ.toLowerCase() + '_' + safeName + '_' + datestamp + '.txt';

  // --- Create overlay UI ---
  var overlay = document.createElement('div');
  overlay.id = 'sf-clipper-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:999999;display:flex;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,sans-serif;';

  var box = document.createElement('div');
  box.style.cssText = 'background:#1a1a1a;border:1px solid #444;border-radius:12px;padding:24px;min-width:340px;max-width:500px;color:#ddd;box-shadow:0 20px 60px rgba(0,0,0,0.5);';

  box.innerHTML =
    '<div style="font-size:16px;font-weight:700;margin-bottom:16px;">💾 Salesforce Clipper</div>' +
    '<div style="font-size:12px;color:#888;margin-bottom:12px;">' + typ + ': ' + recordName + ' (' + fields.length + ' Felder)</div>' +
    '<div style="margin-bottom:12px;">' +
      '<label style="font-size:12px;color:#999;display:block;margin-bottom:4px;">Agent:</label>' +
      '<select id="sf-clipper-agent" style="width:100%;padding:8px;background:#222;border:1px solid #444;color:#ddd;border-radius:6px;font-size:13px;">' +
        '<option value="">Lade Agenten...</option>' +
      '</select>' +
      '<input id="sf-clipper-agent-fallback" type="text" placeholder="Agent-Name eingeben..." style="display:none;width:100%;padding:8px;background:#222;border:1px solid #444;color:#ddd;border-radius:6px;font-size:13px;margin-top:6px;box-sizing:border-box;" />' +
    '</div>' +
    '<div style="font-size:11px;color:#666;margin-bottom:16px;max-height:120px;overflow-y:auto;background:#111;padding:8px;border-radius:6px;white-space:pre-wrap;">' + content.substring(0, 500) + (content.length > 500 ? '\n...' : '') + '</div>' +
    '<div style="display:flex;gap:10px;justify-content:flex-end;">' +
      '<button id="sf-clipper-cancel" style="padding:8px 16px;background:#333;border:1px solid #555;color:#ccc;border-radius:6px;cursor:pointer;font-size:13px;">Abbrechen</button>' +
      '<button id="sf-clipper-save" style="padding:8px 16px;background:#f0c060;border:none;color:#111;border-radius:6px;cursor:pointer;font-size:13px;font-weight:700;">Speichern</button>' +
    '</div>';

  overlay.appendChild(box);
  document.body.appendChild(overlay);

  // --- Load agents via about:blank trick ---
  var agentSelect = document.getElementById('sf-clipper-agent');
  var agentFallback = document.getElementById('sf-clipper-agent-fallback');

  try {
    var agentWin = window.open('about:blank', '_blank', 'width=1,height=1,left=-100,top=-100');
    if (agentWin) {
      agentWin.document.write('<script>' +
        'fetch("http://127.0.0.1:8081/agents").then(r=>r.json()).then(d=>{' +
          'window.opener.postMessage({sfClipperAgents:d.agents},"*");' +
          'window.close();' +
        '}).catch(e=>{' +
          'window.opener.postMessage({sfClipperAgents:null},"*");' +
          'window.close();' +
        '});' +
      '<\/script>');
      agentWin.document.close();
    } else {
      agentFallback.style.display = 'block';
      agentSelect.style.display = 'none';
    }
  } catch(e) {
    agentFallback.style.display = 'block';
    agentSelect.style.display = 'none';
  }

  // --- Receive agents from popup ---
  function onAgentMessage(ev) {
    if (ev.data && ev.data.sfClipperAgents !== undefined) {
      window.removeEventListener('message', onAgentMessage);
      var agents = ev.data.sfClipperAgents;
      if (agents && agents.length) {
        agentSelect.innerHTML = '';
        agents.forEach(function(a) {
          var opt = document.createElement('option');
          opt.value = a;
          opt.textContent = a;
          agentSelect.appendChild(opt);
        });
        // Pre-select signicat if available
        var preselect = agents.find(function(a) { return a === 'signicat'; });
        if (preselect) agentSelect.value = preselect;
      } else {
        agentFallback.style.display = 'block';
        agentSelect.style.display = 'none';
      }
    }
  }
  window.addEventListener('message', onAgentMessage);

  // Timeout fallback
  setTimeout(function() {
    if (agentSelect.options.length === 1 && agentSelect.options[0].value === '') {
      agentFallback.style.display = 'block';
      agentSelect.style.display = 'none';
    }
  }, 3000);

  // --- Cancel ---
  document.getElementById('sf-clipper-cancel').onclick = function() {
    overlay.remove();
  };
  overlay.onclick = function(e) {
    if (e.target === overlay) overlay.remove();
  };

  // --- Save via about:blank ---
  document.getElementById('sf-clipper-save').onclick = function() {
    var agent = agentSelect.style.display !== 'none' ? agentSelect.value : agentFallback.value.trim();
    if (!agent) { alert('Bitte Agent auswaehlen'); return; }

    var payload = JSON.stringify({
      agent: agent,
      content: content,
      filename: filename
    });

    var saveWin = window.open('about:blank', '_blank', 'width=1,height=1,left=-100,top=-100');
    if (!saveWin) {
      alert('Popup blockiert. Bitte Popups fuer Salesforce erlauben.');
      return;
    }

    saveWin.document.write('<script>' +
      'fetch("http://127.0.0.1:8081/save",{' +
        'method:"POST",' +
        'headers:{"Content-Type":"application/json"},' +
        'body:' + JSON.stringify(payload) +
      '}).then(r=>r.json()).then(d=>{' +
        'window.opener.postMessage({sfClipperSaved:true,agent:' + JSON.stringify(agent) + '},"*");' +
        'window.close();' +
      '}).catch(e=>{' +
        'window.opener.postMessage({sfClipperSaved:false,error:e.message},"*");' +
        'window.close();' +
      '});' +
    '<\/script>');
    saveWin.document.close();

    // Update button state
    var saveBtn = document.getElementById('sf-clipper-save');
    saveBtn.textContent = 'Sende...';
    saveBtn.disabled = true;
  };

  // --- Receive save confirmation ---
  function onSaveMessage(ev) {
    if (ev.data && ev.data.sfClipperSaved !== undefined) {
      window.removeEventListener('message', onSaveMessage);
      overlay.remove();
      if (ev.data.sfClipperSaved) {
        showToast('\u2713 Gespeichert in ' + (ev.data.agent || 'Agent'));
      } else {
        showToast('\u2717 Fehler: ' + (ev.data.error || 'Unbekannt'), true);
      }
    }
  }
  window.addEventListener('message', onSaveMessage);

  // Timeout for save
  setTimeout(function() {
    if (document.getElementById('sf-clipper-overlay')) {
      overlay.remove();
      showToast('\u2717 Timeout — Web Clipper Server erreichbar?', true);
    }
  }, 10000);

  // --- Toast notification ---
  function showToast(msg, isError) {
    var toast = document.createElement('div');
    toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;z-index:999999;font-family:-apple-system,sans-serif;box-shadow:0 4px 20px rgba(0,0,0,0.3);transition:opacity 0.3s;';
    toast.style.background = isError ? '#cc3333' : '#2d8a4e';
    toast.style.color = '#fff';
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(function() { toast.style.opacity = '0'; }, 1700);
    setTimeout(function() { toast.remove(); }, 2000);
  }

})();


/*
 * ═══════════════════════════════════════════════════════
 * BOOKMARKLET — diese Zeile als Bookmark-URL einfuegen:
 * ═══════════════════════════════════════════════════════
 */

// javascript:void((function(){if(document.getElementById('sf-clipper-overlay'))return;var url=location.href;var typ='Record';if(url.includes('/Lead/'))typ='Lead';else if(url.includes('/Account/'))typ='Account';else if(url.includes('/Opportunity/'))typ='Opportunity';else if(url.includes('/Contact/'))typ='Contact';else if(url.includes('/Case/'))typ='Case';var nameEl=document.querySelector('h1 .uiOutputText,h1 lightning-formatted-text,h1 slot lightning-formatted-text,h1,.slds-page-header__title');var recordName=nameEl?nameEl.textContent.trim():document.title.replace(' | Salesforce','').trim();var fields=[];var seen={};document.querySelectorAll('.slds-form-element').forEach(function(el){var l=el.querySelector('.slds-form-element__label,.test-id__field-label');var v=el.querySelector('.slds-form-element__static,.test-id__field-value,lightning-formatted-text,lightning-formatted-email,lightning-formatted-phone,lightning-formatted-url,lightning-formatted-name,a');if(l&&v){var lbl=l.textContent.trim().replace(/\n/g,' ');var val=v.textContent.trim().replace(/\n/g,' ');if(lbl&&val&&lbl!==val&&!seen[lbl+val]){seen[lbl+val]=1;fields.push(lbl+': '+val)}}});document.querySelectorAll('dt').forEach(function(dt){var dd=dt.nextElementSibling;if(dd&&dd.tagName==='DD'){var l=dt.textContent.trim();var v=dd.textContent.trim();if(l&&v&&!seen[l+v]){seen[l+v]=1;fields.push(l+': '+v)}}});var datum=new Date().toISOString().replace('T',' ').substring(0,19);var safeName=recordName.replace(/[^a-zA-Z0-9 _-]/g,'').replace(/\s+/g,'_').substring(0,40);var datestamp=new Date().toISOString().substring(0,10);var content='=== SALESFORCE '+typ.toUpperCase()+': '+recordName+' ===\nURL: '+url+'\nExportiert: '+datum+'\n\n'+fields.join('\n')+'\n';var filename='salesforce_'+typ.toLowerCase()+'_'+safeName+'_'+datestamp+'.txt';var overlay=document.createElement('div');overlay.id='sf-clipper-overlay';overlay.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:999999;display:flex;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,sans-serif;';var box=document.createElement('div');box.style.cssText='background:#1a1a1a;border:1px solid #444;border-radius:12px;padding:24px;min-width:340px;max-width:500px;color:#ddd;box-shadow:0 20px 60px rgba(0,0,0,0.5);';box.innerHTML='<div style="font-size:16px;font-weight:700;margin-bottom:16px;">💾 Salesforce Clipper</div><div style="font-size:12px;color:#888;margin-bottom:12px;">'+typ+': '+recordName+' ('+fields.length+' Felder)</div><div style="margin-bottom:12px;"><label style="font-size:12px;color:#999;display:block;margin-bottom:4px;">Agent:</label><select id="sf-clipper-agent" style="width:100%;padding:8px;background:#222;border:1px solid #444;color:#ddd;border-radius:6px;font-size:13px;"><option value="">Lade Agenten...</option></select><input id="sf-clipper-agent-fallback" type="text" placeholder="Agent-Name eingeben..." style="display:none;width:100%;padding:8px;background:#222;border:1px solid #444;color:#ddd;border-radius:6px;font-size:13px;margin-top:6px;box-sizing:border-box;" /></div><div style="font-size:11px;color:#666;margin-bottom:16px;max-height:120px;overflow-y:auto;background:#111;padding:8px;border-radius:6px;white-space:pre-wrap;">'+content.substring(0,500)+(content.length>500?'\n...':'')+'</div><div style="display:flex;gap:10px;justify-content:flex-end;"><button id="sf-clipper-cancel" style="padding:8px 16px;background:#333;border:1px solid #555;color:#ccc;border-radius:6px;cursor:pointer;font-size:13px;">Abbrechen</button><button id="sf-clipper-save" style="padding:8px 16px;background:#f0c060;border:none;color:#111;border-radius:6px;cursor:pointer;font-size:13px;font-weight:700;">Speichern</button></div>';overlay.appendChild(box);document.body.appendChild(overlay);var agentSelect=document.getElementById('sf-clipper-agent');var agentFallback=document.getElementById('sf-clipper-agent-fallback');try{var agentWin=window.open('about:blank','_blank','width=1,height=1,left=-100,top=-100');if(agentWin){agentWin.document.write('<script>fetch("http://127.0.0.1:8081/agents").then(r=>r.json()).then(d=>{window.opener.postMessage({sfClipperAgents:d.agents},"*");window.close();}).catch(e=>{window.opener.postMessage({sfClipperAgents:null},"*");window.close();});<\/script>');agentWin.document.close()}else{agentFallback.style.display='block';agentSelect.style.display='none'}}catch(e){agentFallback.style.display='block';agentSelect.style.display='none'}function onAgentMessage(ev){if(ev.data&&ev.data.sfClipperAgents!==undefined){window.removeEventListener('message',onAgentMessage);var agents=ev.data.sfClipperAgents;if(agents&&agents.length){agentSelect.innerHTML='';agents.forEach(function(a){var opt=document.createElement('option');opt.value=a;opt.textContent=a;agentSelect.appendChild(opt)});var pre=agents.find(function(a){return a==='signicat'});if(pre)agentSelect.value=pre}else{agentFallback.style.display='block';agentSelect.style.display='none'}}}window.addEventListener('message',onAgentMessage);setTimeout(function(){if(agentSelect.options.length===1&&agentSelect.options[0].value===''){agentFallback.style.display='block';agentSelect.style.display='none'}},3000);document.getElementById('sf-clipper-cancel').onclick=function(){overlay.remove()};overlay.onclick=function(e){if(e.target===overlay)overlay.remove()};document.getElementById('sf-clipper-save').onclick=function(){var agent=agentSelect.style.display!=='none'?agentSelect.value:agentFallback.value.trim();if(!agent){alert('Bitte Agent auswaehlen');return}var payload=JSON.stringify({agent:agent,content:content,filename:filename});var saveWin=window.open('about:blank','_blank','width=1,height=1,left=-100,top=-100');if(!saveWin){alert('Popup blockiert.');return}saveWin.document.write('<script>fetch("http://127.0.0.1:8081/save",{method:"POST",headers:{"Content-Type":"application/json"},body:'+JSON.stringify(payload)+'}).then(r=>r.json()).then(d=>{window.opener.postMessage({sfClipperSaved:true,agent:'+JSON.stringify(agent)+'},"*");window.close()}).catch(e=>{window.opener.postMessage({sfClipperSaved:false,error:e.message},"*");window.close()});<\/script>');saveWin.document.close();var sb=document.getElementById('sf-clipper-save');sb.textContent='Sende...';sb.disabled=true};function onSaveMessage(ev){if(ev.data&&ev.data.sfClipperSaved!==undefined){window.removeEventListener('message',onSaveMessage);overlay.remove();if(ev.data.sfClipperSaved){showToast('\u2713 Gespeichert in '+(ev.data.agent||'Agent'))}else{showToast('\u2717 Fehler: '+(ev.data.error||'Unbekannt'),true)}}}window.addEventListener('message',onSaveMessage);setTimeout(function(){if(document.getElementById('sf-clipper-overlay')){overlay.remove();showToast('\u2717 Timeout',true)}},10000);function showToast(msg,isError){var t=document.createElement('div');t.style.cssText='position:fixed;top:20px;left:50%;transform:translateX(-50%);padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;z-index:999999;font-family:-apple-system,sans-serif;box-shadow:0 4px 20px rgba(0,0,0,0.3);transition:opacity 0.3s;';t.style.background=isError?'#cc3333':'#2d8a4e';t.style.color='#fff';t.textContent=msg;document.body.appendChild(t);setTimeout(function(){t.style.opacity='0'},1700);setTimeout(function(){t.remove()},2000)}})())
