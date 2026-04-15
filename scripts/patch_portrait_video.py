#!/usr/bin/env python3
"""Patch: Portrait-Video (9:16) korrekt im Chat anzeigen.
1. generate_video gibt aspect_ratio zurueck
2. created_videos bekommt is_portrait Flag
3. addVideoPreview beruecksichtigt Portrait-Format
"""
import sys

path = '/Users/moritzcremer/AssistantDev/src/web_server.py'
with open(path, 'r') as f:
    content = f.read()

def must_replace(label, old, new):
    global content
    if old not in content:
        print(f"FEHLER bei {label}: Suchstring nicht gefunden!", file=sys.stderr)
        sys.exit(1)
    content = content.replace(old, new, 1)
    print(f"OK: {label}")

# ═══════════════════════════════════════════════════════════════
# 1. generate_video: Track welcher aspect tatsaechlich verwendet wurde
#    und gib ihn als dritten Return-Wert zurueck
# ═══════════════════════════════════════════════════════════════

# Return bei URI download
must_replace("generate_video: URI return mit aspect",
"            print(f\"[VEO] Video gespeichert: {fpath} ({len(vr.content)} bytes)\", flush=True)\n"
"            task_done(task_id, message='Video fertig')\n"
"            return fname, fpath",
"            print(f\"[VEO] Video gespeichert: {fpath} ({len(vr.content)} bytes)\", flush=True)\n"
"            task_done(task_id, message='Video fertig')\n"
"            return fname, fpath, aspect")

# Return bei base64 download
must_replace("generate_video: base64 return mit aspect",
"            with open(fpath, 'wb') as f:\n"
"                f.write(base64.b64decode(vid_b64))\n"
"            task_done(task_id, message='Video fertig')\n"
"            return fname, fpath",
"            with open(fpath, 'wb') as f:\n"
"                f.write(base64.b64decode(vid_b64))\n"
"            task_done(task_id, message='Video fertig')\n"
"            return fname, fpath, aspect")

# ═══════════════════════════════════════════════════════════════
# 2. Caller: Unpack 3 return values + detect portrait
# ═══════════════════════════════════════════════════════════════
must_replace("caller: unpack 3 values + is_portrait",
"                fname, fpath = generate_video(\n"
"                    vid_prompt, state['agent'] or 'standard',\n"
"                    state.get('provider', 'anthropic'),\n"
"                    task_id=_vid_task_id,\n"
"                )\n"
"                created_videos.append({\n"
"                    'filename': fname, 'path': fpath,\n"
"                    'prompt': vid_prompt[:100], 'task_id': _vid_task_id,\n"
"                })",
"                fname, fpath, _vid_aspect = generate_video(\n"
"                    vid_prompt, state['agent'] or 'standard',\n"
"                    state.get('provider', 'anthropic'),\n"
"                    task_id=_vid_task_id,\n"
"                )\n"
"                # Detect portrait: API aspect OR prompt keywords\n"
"                _portrait_kws = ['9:16', 'portrait', 'hochformat', 'vertical', 'senkrecht', 'vertikal', 'tiktok', 'reels', 'shorts']\n"
"                _is_portrait = (_vid_aspect == '9:16') or any(kw in vid_prompt.lower() for kw in _portrait_kws)\n"
"                created_videos.append({\n"
"                    'filename': fname, 'path': fpath,\n"
"                    'prompt': vid_prompt[:100], 'task_id': _vid_task_id,\n"
"                    'is_portrait': _is_portrait,\n"
"                })")

# ═══════════════════════════════════════════════════════════════
# 3. Frontend: addVideoPreview — Portrait-Styling
# ═══════════════════════════════════════════════════════════════
must_replace("addVideoPreview: Portrait-Styling",
"function addVideoPreview(vid) {\n"
"  const msgs = document.getElementById('messages');\n"
"  const div = document.createElement('div');\n"
"  div.style.cssText = 'text-align:center;padding:12px 0;';\n"
"  div.innerHTML = '<video controls style=\"max-width:600px;border-radius:8px;border:1px solid #333;\"><source src=\"/download_file?path=' + encodeURIComponent(vid.path) + '\" type=\"video/mp4\"></video><br>' +\n"
"    '<span style=\"font-size:11px;color:#888;font-family:Inter,sans-serif;\">' + vid.filename + '</span><br>' +\n"
"    '<a href=\"/download_file?path=' + encodeURIComponent(vid.path) + '\" download=\"' + vid.filename + '\" ' +\n"
"    'style=\"display:inline-block;margin-top:6px;background:#f0c060;color:#111;padding:6px 20px;border-radius:6px;font-size:12px;font-weight:700;text-decoration:none;font-family:Inter,sans-serif;\">\\u2b07 Video herunterladen</a>';\n"
"  msgs.appendChild(div);\n"
"  scrollDown();\n"
"}",
"function addVideoPreview(vid) {\n"
"  const msgs = document.getElementById('messages');\n"
"  const div = document.createElement('div');\n"
"  div.style.cssText = 'text-align:center;padding:12px 0;';\n"
"  var videoStyle = vid.is_portrait\n"
"    ? 'max-width:280px;max-height:500px;aspect-ratio:9/16;border-radius:8px;border:1px solid #333;display:block;margin:0 auto;'\n"
"    : 'max-width:600px;border-radius:8px;border:1px solid #333;';\n"
"  div.innerHTML = '<video controls style=\"' + videoStyle + '\"><source src=\"/download_file?path=' + encodeURIComponent(vid.path) + '\" type=\"video/mp4\"></video><br>' +\n"
"    '<span style=\"font-size:11px;color:#888;font-family:Inter,sans-serif;\">' + vid.filename + (vid.is_portrait ? ' (Portrait 9:16)' : '') + '</span><br>' +\n"
"    '<a href=\"/download_file?path=' + encodeURIComponent(vid.path) + '\" download=\"' + vid.filename + '\" ' +\n"
"    'style=\"display:inline-block;margin-top:6px;background:#f0c060;color:#111;padding:6px 20px;border-radius:6px;font-size:12px;font-weight:700;text-decoration:none;font-family:Inter,sans-serif;\">\\u2b07 Video herunterladen</a>';\n"
"  msgs.appendChild(div);\n"
"  scrollDown();\n"
"}")

# Write
with open(path, 'w') as f:
    f.write(content)

print("\nAlle Patches erfolgreich angewendet!")
