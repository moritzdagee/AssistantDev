#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix Veo video download: append API key to URI.
"""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old = """            # Try URI download first (current API returns download URL)
            vid_uri = samples[0].get('video', {}).get('uri', '')
            if vid_uri:
                vr = requests.get(vid_uri, timeout=120)"""

new = """            # Try URI download first (current API returns download URL)
            vid_uri = samples[0].get('video', {}).get('uri', '')
            if vid_uri:
                # API key is required for download
                dl_url = vid_uri + ('&' if '?' in vid_uri else '?') + f'key={api_key}'
                vr = requests.get(dl_url, timeout=120)
                if vr.status_code != 200:
                    raise Exception(f"Gemini Veo: Video-Download fehlgeschlagen (HTTP {vr.status_code})")"""

count = content.count(old)
if count > 0:
    content = content.replace(old, new)
    print(f"Fixed Veo URI download: added API key ({count} occurrence(s))")
else:
    print("ERROR: Veo URI block not found")
    exit(1)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("DONE")
