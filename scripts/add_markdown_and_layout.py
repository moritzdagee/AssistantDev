#!/usr/bin/env python3
"""
Add marked.js Markdown rendering + improve chat bubble layout in web_server.py.
"""

SRC = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(SRC, 'r') as f:
    code = f.read()

changes = 0

# ── 1. Add marked.js CDN before </head> ──

OLD_HEAD = """</style>
</head>"""

NEW_HEAD = """</style>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>"""

if OLD_HEAD in code:
    code = code.replace(OLD_HEAD, NEW_HEAD, 1)
    changes += 1
    print("1. marked.js CDN eingefuegt")
else:
    print("WARN: </style></head> nicht gefunden")

# ── 2. Fix chat bubble layout CSS ──

# 2a: #messages container — add max-width + center
OLD_MESSAGES_CSS = "  #messages { flex:1; overflow-y:auto; padding:20px 24px; display:flex; flex-direction:column; gap:12px; }"
NEW_MESSAGES_CSS = "  #messages { flex:1; overflow-y:auto; padding:20px 24px; display:flex; flex-direction:column; gap:12px; max-width:900px; width:100%; margin:0 auto; }"

if OLD_MESSAGES_CSS in code:
    code = code.replace(OLD_MESSAGES_CSS, NEW_MESSAGES_CSS)
    changes += 1
    print("2a. #messages max-width + centering")
else:
    print("WARN: #messages CSS nicht gefunden")

# 2b: .msg max-width
OLD_MSG_CSS = "  .msg { max-width:820px; }"
NEW_MSG_CSS = "  .msg { max-width:72%; }"

if OLD_MSG_CSS in code:
    code = code.replace(OLD_MSG_CSS, NEW_MSG_CSS)
    changes += 1
    print("2b. .msg max-width 72%")
else:
    print("WARN: .msg CSS nicht gefunden")

# 2c: .bubble padding — ensure adequate spacing
OLD_BUBBLE_CSS = "  .bubble { padding:12px 16px; border-radius:10px; font-size:14px; line-height:1.65; }"
NEW_BUBBLE_CSS = "  .bubble { padding:10px 16px; border-radius:10px; font-size:14px; line-height:1.65; }"

if OLD_BUBBLE_CSS in code:
    code = code.replace(OLD_BUBBLE_CSS, NEW_BUBBLE_CSS)
    changes += 1
    print("2c. .bubble padding aktualisiert")
else:
    print("WARN: .bubble CSS nicht gefunden")

# ── 3. Add Markdown CSS for rendered content ──

# Insert after the existing .bubble { position:relative; } line
OLD_BUBBLE_REL = "  .bubble { position:relative; }"
NEW_BUBBLE_REL = """  .bubble { position:relative; }
  .bubble.markdown-rendered h1, .bubble.markdown-rendered h2, .bubble.markdown-rendered h3, .bubble.markdown-rendered h4 { color:#e8e8e8; margin:14px 0 6px 0; font-family:Inter,sans-serif; }
  .bubble.markdown-rendered h1 { font-size:18px; font-weight:700; }
  .bubble.markdown-rendered h2 { font-size:16px; font-weight:700; }
  .bubble.markdown-rendered h3 { font-size:15px; font-weight:600; }
  .bubble.markdown-rendered h4 { font-size:14px; font-weight:600; }
  .bubble.markdown-rendered p { margin:6px 0; }
  .bubble.markdown-rendered ul, .bubble.markdown-rendered ol { margin:6px 0 6px 20px; padding:0; }
  .bubble.markdown-rendered li { margin:3px 0; }
  .bubble.markdown-rendered a { color:#6aafff; text-decoration:underline; }
  .bubble.markdown-rendered a:hover { color:#8ac4ff; }
  .bubble.markdown-rendered strong { color:#f0f0f0; }
  .bubble.markdown-rendered code { background:#0d0d0d; padding:1px 5px; border-radius:3px; font-size:13px; font-family:monospace; }
  .bubble.markdown-rendered pre { background:#0d0d0d; border:1px solid #333; border-radius:6px; padding:10px 12px; margin:8px 0; overflow-x:auto; }
  .bubble.markdown-rendered pre code { background:none; padding:0; font-size:12px; }
  .bubble.markdown-rendered table { border-collapse:collapse; margin:8px 0; width:100%; font-size:13px; }
  .bubble.markdown-rendered th, .bubble.markdown-rendered td { border:1px solid #333; padding:6px 10px; text-align:left; }
  .bubble.markdown-rendered th { background:#1a1a1a; color:#ccc; font-weight:600; }
  .bubble.markdown-rendered blockquote { border-left:3px solid #444; padding-left:12px; margin:8px 0; color:#999; }
  .bubble.markdown-rendered hr { border:none; border-top:1px solid #333; margin:12px 0; }
  .bubble.markdown-rendered img { max-width:100%; border-radius:4px; }"""

if OLD_BUBBLE_REL in code:
    code = code.replace(OLD_BUBBLE_REL, NEW_BUBBLE_REL, 1)
    changes += 1
    print("3. Markdown CSS eingefuegt")
else:
    print("WARN: .bubble position:relative nicht gefunden")

# ── 4. Replace renderMessageContent to use marked.js ──

OLD_RENDER = """function renderMessageContent(text) {
  // Parse <output>...</output> blocks
  var outputMatch = text.match(/<output>([\\\\s\\\\S]*?)<\\\\/output>/);
  if (outputMatch) {
    var before = text.substring(0, outputMatch.index).trim();
    var outputContent = outputMatch[1].trim();
    var after = text.substring(outputMatch.index + outputMatch[0].length).trim();
    var html = '';
    if (before) html += renderCodeBlocks(before);
    html += '<div class="output-block" data-output="' + escHtml(outputContent).replace(/"/g, '&quot;') + '">' + renderCodeBlocks(outputContent) + '</div>';
    if (after) html += renderCodeBlocks(after);
    return html;
  }
  // No output block — render normally with code blocks
  return renderCodeBlocks(text);
}"""

NEW_RENDER = r"""function renderMessageContent(text) {
  // Parse <output>...</output> blocks first
  var outputMatch = text.match(/<output>([\s\S]*?)<\/output>/);
  if (outputMatch) {
    var before = text.substring(0, outputMatch.index).trim();
    var outputContent = outputMatch[1].trim();
    var after = text.substring(outputMatch.index + outputMatch[0].length).trim();
    var html = '';
    if (before) html += renderMarkdown(before);
    html += '<div class="output-block" data-output="' + escHtml(outputContent).replace(/"/g, '&quot;') + '">' + renderCodeBlocks(outputContent) + '</div>';
    if (after) html += renderMarkdown(after);
    return html;
  }
  // No output block — render with Markdown
  return renderMarkdown(text);
}

function renderMarkdown(text) {
  // Use marked.js if available, otherwise fall back to renderCodeBlocks
  if (typeof marked !== 'undefined') {
    try {
      marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        mangle: false,
      });
      // Let marked handle everything including code blocks
      var html = marked.parse(text);
      // Make links open in new tab
      html = html.replace(/<a /g, '<a target="_blank" rel="noopener" ');
      return html;
    } catch(e) {
      console.warn('Markdown parse error, falling back:', e);
    }
  }
  return renderCodeBlocks(text);
}"""

if OLD_RENDER in code:
    code = code.replace(OLD_RENDER, NEW_RENDER)
    changes += 1
    print("4. renderMessageContent + renderMarkdown eingefuegt")
else:
    print("WARN: renderMessageContent nicht gefunden — versuche alternative Suche")
    # The escaping in Python string might differ - try a simpler match
    if "function renderMessageContent(text) {" in code and "return renderCodeBlocks(text);" in code:
        # Find the function boundaries
        start = code.index("function renderMessageContent(text) {")
        # Find the closing of the function (next function definition)
        end_marker = "\n\nfunction addMessage("
        end = code.index(end_marker, start)
        old_func = code[start:end]
        new_func = r"""function renderMessageContent(text) {
  // Parse <output>...</output> blocks first
  var outputMatch = text.match(/<output>([\s\S]*?)<\/output>/);
  if (outputMatch) {
    var before = text.substring(0, outputMatch.index).trim();
    var outputContent = outputMatch[1].trim();
    var after = text.substring(outputMatch.index + outputMatch[0].length).trim();
    var html = '';
    if (before) html += renderMarkdown(before);
    html += '<div class="output-block" data-output="' + escHtml(outputContent).replace(/"/g, '&quot;') + '">' + renderCodeBlocks(outputContent) + '</div>';
    if (after) html += renderMarkdown(after);
    return html;
  }
  // No output block — render with Markdown
  return renderMarkdown(text);
}

function renderMarkdown(text) {
  // Use marked.js if available, otherwise fall back to renderCodeBlocks
  if (typeof marked !== 'undefined') {
    try {
      marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        mangle: false,
      });
      var html = marked.parse(text);
      // Make links open in new tab
      html = html.replace(/<a /g, '<a target="_blank" rel="noopener" ');
      return html;
    } catch(e) {
      console.warn('Markdown parse error, falling back:', e);
    }
  }
  return renderCodeBlocks(text);
}"""
        code = code[:start] + new_func + code[end:]
        changes += 1
        print("4. renderMessageContent + renderMarkdown eingefuegt (alternative Methode)")
    else:
        print("FEHLER: renderMessageContent konnte nicht ersetzt werden!")

# ── 5. Update addMessage to add markdown-rendered class to assistant bubbles ──

OLD_ADD_MSG = """  if (role === 'assistant') {
    div.innerHTML = '<div class="bubble">' + renderMessageContent(text) + '</div><div class="meta">' + meta + '</div>';"""

NEW_ADD_MSG = """  if (role === 'assistant') {
    div.innerHTML = '<div class="bubble markdown-rendered">' + renderMessageContent(text) + '</div><div class="meta">' + meta + '</div>';"""

if OLD_ADD_MSG in code:
    code = code.replace(OLD_ADD_MSG, NEW_ADD_MSG)
    changes += 1
    print("5. addMessage: markdown-rendered class hinzugefuegt")
else:
    print("WARN: addMessage assistant block nicht gefunden")

# ── 6. Remove the <pre> wrapper from user messages for cleaner look ──
# User messages currently wrap in <pre> which is fine — leave as is

# ── Write ──

with open(SRC, 'w') as f:
    f.write(code)

print(f"\n{changes} Aenderungen geschrieben.")
