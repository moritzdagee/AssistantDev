#!/usr/bin/env python3
"""
Generiert den Salesforce Clipper Bookmarklet-Code mit hardcodierter Agenten-Liste.
Liest Agenten aus config/agents/ und schreibt den fertigen javascript: Code
nach scripts/salesforce_bookmarklet.txt.

Ausfuehren:
  python3 ~/AssistantDev/scripts/generate_salesforce_bookmarklet.py

Nach dem Ausfuehren den Inhalt von salesforce_bookmarklet.txt als Bookmark-URL einfuegen.
"""

import os
import json

BASE = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake")
AGENTS_DIR = os.path.join(BASE, "config/agents")
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salesforce_bookmarklet.txt")

# Read agents — only parent agents (no underscore), and only if memory dir exists
all_files = sorted([f[:-4] for f in os.listdir(AGENTS_DIR) if f.endswith('.txt')])
agents = []
skipped = []
for name in all_files:
    if '_' in name:
        skipped.append(name + ' (sub-agent)')
        continue
    agent_dir = os.path.join(BASE, name)
    memory_dir = os.path.join(agent_dir, 'memory')
    if not os.path.exists(agent_dir) or not os.path.exists(memory_dir):
        skipped.append(name + ' (kein Memory-Ordner)')
        continue
    agents.append(name)

agents_js = json.dumps(agents)

print(f"Parent-Agenten: {len(agents)}: {', '.join(agents)}")
if skipped:
    print(f"Uebersprungen: {', '.join(skipped)}")

# Build bookmarklet
bookmarklet = (
    "javascript:void((function(){"
    "if(document.getElementById('sf-clipper-overlay'))return;"
    "var url=location.href;"
    "var typ='Record';"
    "if(url.includes('/Lead/'))typ='Lead';"
    "else if(url.includes('/Account/'))typ='Account';"
    "else if(url.includes('/Opportunity/'))typ='Opportunity';"
    "else if(url.includes('/Contact/'))typ='Contact';"
    "else if(url.includes('/Case/'))typ='Case';"
    "var nameEl=document.querySelector('h1 .uiOutputText,h1 lightning-formatted-text,h1 slot lightning-formatted-text,h1,.slds-page-header__title');"
    "var recordName=nameEl?nameEl.textContent.trim():document.title.replace(' | Salesforce','').trim();"
    "var fields=[];var seen={};"
    "document.querySelectorAll('.slds-form-element').forEach(function(el){"
    "var l=el.querySelector('.slds-form-element__label,.test-id__field-label');"
    "var v=el.querySelector('.slds-form-element__static,.test-id__field-value,lightning-formatted-text,lightning-formatted-email,lightning-formatted-phone,lightning-formatted-url,lightning-formatted-name,a');"
    "if(l&&v){var lbl=l.textContent.trim().replace(/\\n/g,' ');var val=v.textContent.trim().replace(/\\n/g,' ');"
    "if(lbl&&val&&lbl!==val&&!seen[lbl+val]){seen[lbl+val]=1;fields.push(lbl+': '+val)}}});"
    "document.querySelectorAll('dt').forEach(function(dt){"
    "var dd=dt.nextElementSibling;"
    "if(dd&&dd.tagName==='DD'){var l=dt.textContent.trim();var v=dd.textContent.trim();"
    "if(l&&v&&!seen[l+v]){seen[l+v]=1;fields.push(l+': '+v)}}});"
    "var datum=new Date().toISOString().replace('T',' ').substring(0,19);"
    "var safeName=recordName.replace(/[^a-zA-Z0-9 _-]/g,'').replace(/\\s+/g,'_').substring(0,40);"
    "var datestamp=new Date().toISOString().substring(0,10);"
    "var content='=== SALESFORCE '+typ.toUpperCase()+': '+recordName+' ===\\nURL: '+url+'\\nExportiert: '+datum+'\\n\\n'+fields.join('\\n')+'\\n';"
    "var filename='salesforce_'+typ.toLowerCase()+'_'+safeName+'_'+datestamp+'.txt';"
    # Hardcoded parent-only agents list
    "var agents=" + agents_js + ";"
    # Overlay
    "var overlay=document.createElement('div');"
    "overlay.id='sf-clipper-overlay';"
    "overlay.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:999999;display:flex;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,sans-serif;';"
    "var box=document.createElement('div');"
    "box.style.cssText='background:#1a1a1a;border:1px solid #444;border-radius:12px;padding:24px;min-width:340px;max-width:500px;color:#ddd;box-shadow:0 20px 60px rgba(0,0,0,0.5);';"
    "var opts='';agents.forEach(function(a){opts+='<option value=\"'+a+'\">'+a+'</option>'});"
    "box.innerHTML='"
    "<div style=\"font-size:16px;font-weight:700;margin-bottom:16px;\">\\ud83d\\udcbe Salesforce Clipper</div>"
    "<div style=\"font-size:12px;color:#888;margin-bottom:12px;\">'+typ+': '+recordName+' ('+fields.length+' Felder)</div>"
    "<div style=\"margin-bottom:12px;\">"
    "<label style=\"font-size:12px;color:#999;display:block;margin-bottom:4px;\">Agent:</label>"
    "<select id=\"sf-clipper-agent\" style=\"width:100%;padding:8px;background:#222;border:1px solid #444;color:#ddd;border-radius:6px;font-size:13px;\">'+opts+'</select>"
    "</div>"
    "<div style=\"font-size:11px;color:#666;margin-bottom:16px;max-height:120px;overflow-y:auto;background:#111;padding:8px;border-radius:6px;white-space:pre-wrap;\">'+content.substring(0,500)+(content.length>500?'\\n...':'')+'</div>"
    "<div style=\"display:flex;gap:10px;justify-content:flex-end;\">"
    "<button id=\"sf-clipper-cancel\" style=\"padding:8px 16px;background:#333;border:1px solid #555;color:#ccc;border-radius:6px;cursor:pointer;font-size:13px;\">Abbrechen</button>"
    "<button id=\"sf-clipper-save\" style=\"padding:8px 16px;background:#f0c060;border:none;color:#111;border-radius:6px;cursor:pointer;font-size:13px;font-weight:700;\">Speichern</button>"
    "</div>';"
    "overlay.appendChild(box);document.body.appendChild(overlay);"
    # Pre-select signicat
    "var sel=document.getElementById('sf-clipper-agent');"
    "for(var i=0;i<sel.options.length;i++){if(sel.options[i].value==='signicat'){sel.selectedIndex=i;break}}"
    # Cancel
    "document.getElementById('sf-clipper-cancel').onclick=function(){overlay.remove()};"
    "overlay.onclick=function(e){if(e.target===overlay)overlay.remove()};"
    # Toast function
    "function showToast(msg,isError){"
    "var t=document.createElement('div');"
    "t.style.cssText='position:fixed;top:20px;left:50%;transform:translateX(-50%);padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;z-index:999999;font-family:-apple-system,sans-serif;box-shadow:0 4px 20px rgba(0,0,0,0.3);transition:opacity 0.3s;';"
    "t.style.background=isError?'#cc3333':'#2d8a4e';t.style.color='#fff';t.textContent=msg;"
    "document.body.appendChild(t);"
    "setTimeout(function(){t.style.opacity='0'},1700);"
    "setTimeout(function(){t.remove()},2000)}"
    # Save with 3-strategy fallback
    "function doSave(agent,payload){"
    "var done=false;"
    "function finish(ok,msg){if(done)return;done=true;overlay.remove();"
    "if(ok){showToast('\\u2713 '+msg)}else{showToast('\\u2717 '+msg,true)}}"
    # Strategy 3: clipboard fallback
    "function strategy3(){"
    "try{navigator.clipboard.writeText(content).then(function(){"
    "finish(true,'\\ud83d\\udccb In Zwischenablage kopiert — manuell in Assistant einfuegen')"
    "}).catch(function(){finish(false,'Konnte nicht speichern und nicht kopieren')})"
    "}catch(e){finish(false,'Konnte nicht speichern und nicht kopieren')}}"
    # Strategy 2: direct XHR
    "function strategy2(){"
    "try{var xhr=new XMLHttpRequest();"
    "xhr.open('POST','http://127.0.0.1:8081/save');"
    "xhr.setRequestHeader('Content-Type','application/json');"
    "xhr.onload=function(){if(xhr.status===200){finish(true,'Gespeichert in '+agent)}else{strategy3()}};"
    "xhr.onerror=function(){strategy3()};"
    "xhr.ontimeout=function(){strategy3()};"
    "xhr.timeout=5000;"
    "xhr.send(payload)"
    "}catch(e){strategy3()}}"
    # Strategy 1: data: URI iframe
    "var iframe=document.createElement('iframe');"
    "iframe.style.display='none';"
    "function onMsg(ev){if(done)return;"
    "if(ev.data==='ok'){done=true;window.removeEventListener('message',onMsg);"
    "iframe.remove();finish(true,'Gespeichert in '+agent)}"
    "else if(typeof ev.data==='string'&&ev.data.indexOf('err:')===0){done=true;"
    "window.removeEventListener('message',onMsg);iframe.remove();strategy2()}}"
    "window.addEventListener('message',onMsg);"
    "try{"
    "iframe.src='data:text/html,<script>"
    "fetch(\"http://127.0.0.1:8081/save\",{method:\"POST\",headers:{\"Content-Type\":\"application/json\"},body:'+JSON.stringify(payload)+'})"
    ".then(function(){parent.postMessage(\"ok\",\"*\")})"
    ".catch(function(e){parent.postMessage(\"err:\"+e.message,\"*\")})"
    "<\\/script>';"
    "document.body.appendChild(iframe)"
    "}catch(e){strategy2()}"
    # Timeout: if strategy 1 gets no response after 3s, try strategy 2
    "setTimeout(function(){if(!done){window.removeEventListener('message',onMsg);"
    "try{iframe.remove()}catch(x){}"
    "strategy2()}},3000)"
    "}"
    "document.getElementById('sf-clipper-save').onclick=function(){"
    "var agent=document.getElementById('sf-clipper-agent').value;"
    "if(!agent){alert('Bitte Agent auswaehlen');return}"
    "var sb=document.getElementById('sf-clipper-save');sb.textContent='Sende...';sb.disabled=true;"
    "var payload=JSON.stringify({agent:agent,content:content,filename:filename});"
    "doSave(agent,payload)"
    "};"
    "})())"
)

with open(OUTPUT, 'w') as f:
    f.write(bookmarklet)

print(f"\nBookmarklet geschrieben nach: {OUTPUT}")
print(f"Laenge: {len(bookmarklet)} Zeichen\n")
print("=" * 60)
print("BOOKMARKLET CODE (als Bookmark-URL einfuegen):")
print("=" * 60)
print(bookmarklet)
