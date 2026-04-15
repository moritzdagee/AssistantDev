#!/usr/bin/env python3
"""Add section copy buttons to AI answers in web_server.py"""

import sys

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r') as f:
    content = f.read()

# === 1. Add CSS before </style> ===
css_anchor = '  .snippet-copy-btn.copied { color:#4caf50; border-color:#4caf50; }\n</style>'
css_new = """  .snippet-copy-btn.copied { color:#4caf50; border-color:#4caf50; }
  .section-copy-marker { position:relative; height:0; overflow:visible; pointer-events:none; }
  .section-copy-btn { position:absolute; right:0; top:2px; background:transparent; border:1px solid rgba(255,255,255,0.08); border-radius:4px; color:#555; font-size:10px; padding:1px 7px; cursor:pointer; transition:opacity 0.15s, color 0.15s, border-color 0.15s; z-index:5; font-family:Inter,sans-serif; opacity:0.4; pointer-events:auto; }
  .section-copy-btn:hover { opacity:1; color:#f0c060; border-color:#f0c060; }
  .section-copy-btn.copied { color:#4caf50; border-color:#4caf50; opacity:1; }
</style>"""

if css_anchor not in content:
    print("ERROR: CSS anchor not found!")
    sys.exit(1)
if '.section-copy-btn' in content:
    print("SKIP: section-copy-btn CSS already exists")
else:
    count = content.count(css_anchor)
    if count != 1:
        print(f"ERROR: CSS anchor found {count} times, expected 1")
        sys.exit(1)
    content = content.replace(css_anchor, css_new, 1)
    print("OK: CSS added")

# === 2. Add addSectionCopyButtons function after addCopyButton function ===
func_anchor = """  // Small "Alles" button on bubble level (for copying everything)
  if (!bubble.querySelector('.snippet-copy-btn')) {
    var hasBlocks = bubble.querySelectorAll('.code-block-wrapper, .output-block').length > 0;
    if (hasBlocks) {
      var btn = document.createElement('button');
      btn.className = 'snippet-copy-btn';
      btn.textContent = 'Alles';
      btn.onclick = function() { copyToClipboard(rawText, btn, 'Alles'); };
      bubble.appendChild(btn);
    } else {
      var btn = document.createElement('button');
      btn.className = 'snippet-copy-btn';
      btn.textContent = 'Kopieren';
      btn.onclick = function() { copyToClipboard(rawText, btn, 'Kopieren'); };
      bubble.appendChild(btn);
    }
  }
}"""

new_func = func_anchor + """

function addSectionCopyButtons(msgEl, rawText) {
  if (!rawText || rawText.length < 40) return;
  var bubble = msgEl.querySelector('.bubble');
  if (!bubble) return;
  // Find ## headings in rawText, but only outside code blocks
  var codeParts = rawText.split('```');
  var headingPositions = [];
  var charPos = 0;
  for (var ci = 0; ci < codeParts.length; ci++) {
    if (ci % 2 === 0) {
      var re = /^## .+/gm;
      var m;
      while ((m = re.exec(codeParts[ci])) !== null) {
        headingPositions.push(charPos + m.index);
      }
    }
    charPos += codeParts[ci].length + 3;
  }
  if (headingPositions.length === 0) return;
  // Build rest-texts for each heading position
  var restTexts = headingPositions.map(function(p) { return rawText.substring(p).trim(); });
  // Find content <pre> elements (not in code-block-wrapper or output-block)
  var allPres = Array.from(bubble.querySelectorAll('pre'));
  var contentPres = allPres.filter(function(pre) {
    return !pre.closest('.code-block-wrapper') && !pre.closest('.output-block');
  });
  var restIdx = 0;
  contentPres.forEach(function(pre) {
    var preText = pre.textContent;
    var preLines = preText.split('\\n');
    var headingLineIdxs = [];
    for (var li = 0; li < preLines.length; li++) {
      if (/^## /.test(preLines[li]) && restIdx < restTexts.length) {
        headingLineIdxs.push({ lineIdx: li, restText: restTexts[restIdx] });
        restIdx++;
      }
    }
    if (headingLineIdxs.length === 0) return;
    // Split <pre> at heading boundaries and insert buttons
    var frag = document.createDocumentFragment();
    var lastCut = 0;
    headingLineIdxs.forEach(function(h) {
      if (h.lineIdx > lastCut) {
        var beforeText = preLines.slice(lastCut, h.lineIdx).join('\\n').trim();
        if (beforeText) {
          var p = document.createElement('pre');
          p.textContent = beforeText;
          frag.appendChild(p);
        }
      }
      var marker = document.createElement('div');
      marker.className = 'section-copy-marker';
      var btn = document.createElement('button');
      btn.className = 'section-copy-btn';
      btn.textContent = '\\u2193 Kopieren';
      (function(rt, b) {
        b.onclick = function() { copyToClipboard(rt, b, '\\u2193 Kopieren'); };
      })(h.restText, btn);
      marker.appendChild(btn);
      frag.appendChild(marker);
      lastCut = h.lineIdx;
    });
    if (lastCut < preLines.length) {
      var rest = preLines.slice(lastCut).join('\\n').trim();
      if (rest) {
        var p = document.createElement('pre');
        p.textContent = rest;
        frag.appendChild(p);
      }
    }
    pre.parentNode.replaceChild(frag, pre);
  });
}"""

if func_anchor not in content:
    print("ERROR: function anchor not found!")
    sys.exit(1)
if 'addSectionCopyButtons' in content:
    print("SKIP: addSectionCopyButtons already exists")
else:
    count = content.count(func_anchor)
    if count != 1:
        print(f"ERROR: function anchor found {count} times, expected 1")
        sys.exit(1)
    content = content.replace(func_anchor, new_func, 1)
    print("OK: addSectionCopyButtons function added")

# === 3. Add call in addMessage ===
call_anchor = '    addCopyButton(div, text);'
call_new = '    addCopyButton(div, text);\n    addSectionCopyButtons(div, text);'

if 'addSectionCopyButtons(div, text)' in content:
    print("SKIP: addSectionCopyButtons call already exists")
else:
    count = content.count(call_anchor)
    if count != 1:
        print(f"ERROR: call anchor found {count} times, expected 1")
        sys.exit(1)
    content = content.replace(call_anchor, call_new, 1)
    print("OK: addSectionCopyButtons call added in addMessage")

with open(filepath, 'w') as f:
    f.write(content)

print("DONE: web_server.py updated")
