#!/usr/bin/env python3
"""Patch: addCodeCopyButtons soll auch marked.js <pre><code> Blöcke abdecken."""

import sys

path = '/Users/moritzcremer/AssistantDev/src/web_server.py'
with open(path, 'r') as f:
    content = f.read()

# --- Patch 1: Replace addCodeCopyButtons to also handle marked.js <pre><code> blocks ---
old_func = """function addCodeCopyButtons(msgEl) {
  var blocks = msgEl.querySelectorAll('.code-block-wrapper');
  blocks.forEach(function(wrapper) {
    var code = wrapper.getAttribute('data-code');
    if (!code) return;
    var btn = document.createElement('button');
    btn.className = 'code-copy-btn';
    btn.textContent = 'Kopieren';
    btn.onclick = function() { copyToClipboard(code, btn, 'Kopieren'); };
    wrapper.appendChild(btn);
  });
}"""

new_func = """function addCodeCopyButtons(msgEl) {
  // Handle custom code-block-wrapper (renderCodeBlocks fallback)
  var blocks = msgEl.querySelectorAll('.code-block-wrapper');
  blocks.forEach(function(wrapper) {
    if (wrapper.querySelector('.code-copy-btn')) return;
    var code = wrapper.getAttribute('data-code');
    if (!code) return;
    var btn = document.createElement('button');
    btn.className = 'code-copy-btn';
    btn.textContent = 'Kopieren';
    btn.onclick = function() { copyToClipboard(code, btn, 'Kopieren'); };
    wrapper.appendChild(btn);
  });
  // Handle marked.js rendered <pre><code> blocks
  var pres = msgEl.querySelectorAll('pre');
  pres.forEach(function(pre) {
    if (pre.closest('.code-block-wrapper') || pre.closest('.output-block')) return;
    if (pre.parentNode.classList && pre.parentNode.classList.contains('code-block-wrapper')) return;
    if (pre.querySelector('.code-copy-btn')) return;
    var codeEl = pre.querySelector('code');
    var codeText = codeEl ? codeEl.textContent : pre.textContent;
    if (!codeText || codeText.trim().length < 2) return;
    // Wrap in code-block-wrapper for consistent styling
    var wrapper = document.createElement('div');
    wrapper.className = 'code-block-wrapper';
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);
    // Detect language from class (marked adds language-xxx)
    if (codeEl) {
      var langClass = (codeEl.className || '').match(/language-(\\w+)/);
      if (langClass) {
        var langLabel = document.createElement('span');
        langLabel.className = 'code-block-lang';
        langLabel.textContent = langClass[1];
        wrapper.insertBefore(langLabel, pre);
      }
    }
    var btn = document.createElement('button');
    btn.className = 'code-copy-btn';
    btn.textContent = 'Kopieren';
    btn.onclick = function() { copyToClipboard(codeText, btn, 'Kopieren'); };
    wrapper.appendChild(btn);
  });
}"""

if old_func not in content:
    print("FEHLER: addCodeCopyButtons Funktion nicht gefunden!", file=sys.stderr)
    sys.exit(1)

content = content.replace(old_func, new_func)

# --- Patch 2: Also add copy buttons to user messages (not just assistant) ---
old_user_msg = """    div.innerHTML = '<div class="bubble"><pre>' + escHtml(text) + '</pre></div><div class="meta">' + meta + '</div>';
  }
  msgs.appendChild(div);"""

new_user_msg = """    div.innerHTML = '<div class="bubble"><pre>' + escHtml(text) + '</pre></div><div class="meta">' + meta + '</div>';
    addCodeCopyButtons(div);
  }
  msgs.appendChild(div);"""

if old_user_msg not in content:
    print("WARNUNG: User-Message Block nicht gefunden - evtl. bereits gepatcht", file=sys.stderr)
else:
    content = content.replace(old_user_msg, new_user_msg)

with open(path, 'w') as f:
    f.write(content)

print("Patch erfolgreich angewendet.")
print("- addCodeCopyButtons erweitert: behandelt jetzt auch marked.js <pre><code> Blöcke")
print("- Copy-Buttons werden jetzt auch für User-Nachrichten eingefügt")
