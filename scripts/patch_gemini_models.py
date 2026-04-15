#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch web_server.py:
1. Update Gemini Image model priority list (add Imagen 4 as primary, keep Gemini fallbacks)
2. Update Video model to Veo 3.1
3. Add MODEL_DISPLAY entries for new Gemini models
4. Update MODEL_CAPABILITIES for new models
"""

import json
import os

ws_path = '/Users/moritzcremer/AssistantDev/src/web_server.py'
models_path = os.path.expanduser(
    '~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/config/models.json'
)

with open(ws_path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# =============================================================
# 1. Update IMAGE_PROVIDERS and VIDEO_PROVIDERS
# =============================================================

old_providers = '''IMAGE_PROVIDERS = {
    "openai": "gpt-image-1",
    "gemini": "gemini-2.5-flash-image",
}
VIDEO_PROVIDERS = {
    "gemini": "veo-3.1-generate-preview",
}'''

new_providers = '''IMAGE_PROVIDERS = {
    "openai": "gpt-image-1",
    "gemini": "imagen-4.0-generate-001",
}
VIDEO_PROVIDERS = {
    "gemini": "veo-3.1-generate-preview",
}'''

count = content.count(old_providers)
if count > 0:
    content = content.replace(old_providers, new_providers)
    print(f"1. Updated IMAGE_PROVIDERS: gemini -> imagen-4.0-generate-001 ({count})")
    changes += count
else:
    print("WARNING: IMAGE_PROVIDERS block not found")

# =============================================================
# 2. Update _generate_image_single for Gemini — add Imagen 4 path
# =============================================================

old_gemini_image = '''    elif provider_key == 'gemini':
        # Gemini Bildgenerierung: verfuegbare Image-Modelle in Prioritaetsreihenfolge
        gemini_models = ["gemini-2.5-flash-image", "gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"]
        last_err = None
        for gmodel in gemini_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gmodel}:generateContent?key={api_key}"
            r = requests.post(url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": "Generate an image: " + prompt}]}],
                    "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}
                },
                timeout=120)
            data = r.json()
            if r.status_code != 200:
                last_err = f"Gemini ({gmodel}): {data.get('error', {}).get('message', str(data))}"
                print(f"  Gemini Image {gmodel} fehlgeschlagen: {last_err}")
                continue
            parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
            for p in parts:
                if 'inlineData' in p:
                    with open(fpath, 'wb') as f:
                        f.write(_b64.b64decode(p['inlineData']['data']))
                    return True
            last_err = f"Gemini ({gmodel}): Kein Bild generiert (moeglicherweise Content-Filter)"
            print(f"  {last_err}")
            continue
        raise Exception(last_err or "Gemini: Bildgenerierung fehlgeschlagen")'''

new_gemini_image = '''    elif provider_key == 'gemini':
        # Gemini Bildgenerierung: Imagen 4 zuerst (predict API), dann Gemini-Native Fallbacks
        import base64 as _img_b64

        # Versuch 1: Imagen 4 (beste Qualitaet, predict API)
        imagen_models = ["imagen-4.0-generate-001", "imagen-4.0-fast-generate-001"]
        for imodel in imagen_models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{imodel}:predict?key={api_key}"
                r = requests.post(url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "instances": [{"prompt": prompt}],
                        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}
                    },
                    timeout=120)
                data = r.json()
                if r.status_code == 200:
                    predictions = data.get('predictions', [])
                    if predictions and predictions[0].get('bytesBase64Encoded'):
                        with open(fpath, 'wb') as f:
                            f.write(_img_b64.b64decode(predictions[0]['bytesBase64Encoded']))
                        print(f"  Imagen {imodel}: Bild generiert")
                        return True
                print(f"  Imagen {imodel}: {data.get('error', {}).get('message', 'Kein Bild')}")
            except Exception as ie:
                print(f"  Imagen {imodel} Fehler: {ie}")

        # Versuch 2: Gemini-Native Image-Modelle (generateContent API mit responseModalities)
        gemini_models = ["gemini-2.5-flash-image", "gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"]
        last_err = None
        for gmodel in gemini_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gmodel}:generateContent?key={api_key}"
            r = requests.post(url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": "Generate an image: " + prompt}]}],
                    "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}
                },
                timeout=120)
            data = r.json()
            if r.status_code != 200:
                last_err = f"Gemini ({gmodel}): {data.get('error', {}).get('message', str(data))}"
                print(f"  Gemini Image {gmodel} fehlgeschlagen: {last_err}")
                continue
            parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
            for p in parts:
                if 'inlineData' in p:
                    with open(fpath, 'wb') as f:
                        f.write(_b64.b64decode(p['inlineData']['data']))
                    return True
            last_err = f"Gemini ({gmodel}): Kein Bild generiert (moeglicherweise Content-Filter)"
            print(f"  {last_err}")
            continue
        raise Exception(last_err or "Gemini: Bildgenerierung fehlgeschlagen (alle Modelle versucht)")'''

count = content.count(old_gemini_image)
if count > 0:
    content = content.replace(old_gemini_image, new_gemini_image)
    print(f"2. Updated Gemini image generation with Imagen 4 primary ({count})")
    changes += count
else:
    print("WARNING: Gemini image generation block not found")

# =============================================================
# 3. Update MODEL_CAPABILITIES with new models
# =============================================================

old_capabilities = '''MODEL_CAPABILITIES = {
    "gemini-2.5-flash": ["video", "image"],
    "gemini-2.5-flash-image": ["image"],
    "gemini-2.5-pro": ["reasoning"],
    "gpt-4o": ["image"],
    "gpt-image-1": ["image"],
    "o1": ["reasoning"],
    "sonar-deep-research": ["reasoning"],
    "sonar-reasoning-pro": ["reasoning"],
    "sonar-reasoning": ["reasoning"],
}'''

new_capabilities = '''MODEL_CAPABILITIES = {
    "gemini-2.5-flash": ["video", "image"],
    "gemini-2.5-pro": ["reasoning", "video", "image"],
    "gemini-3-flash-preview": ["video", "image"],
    "gemini-3-pro-preview": ["reasoning", "video", "image"],
    "gemini-3.1-pro-preview": ["reasoning", "video", "image"],
    "gemini-2.0-flash": ["video", "image"],
    "gpt-4o": ["image"],
    "gpt-image-1": ["image"],
    "o1": ["reasoning"],
    "sonar-deep-research": ["reasoning"],
    "sonar-reasoning-pro": ["reasoning"],
    "sonar-reasoning": ["reasoning"],
}'''

count = content.count(old_capabilities)
if count > 0:
    content = content.replace(old_capabilities, new_capabilities)
    print(f"3. Updated MODEL_CAPABILITIES ({count})")
    changes += count

# =============================================================
# 4. Update MODEL_DISPLAY with new Gemini models
# =============================================================

old_display_gemini = """    'gemini-2.0-flash': 'Gemini 2.0 Flash',
    'gemini-2.5-pro': 'Gemini 2.5 Pro',
    'gemini-2.5-flash': 'Gemini 2.5 Flash',"""

new_display_gemini = """    'gemini-2.0-flash': 'Gemini 2.0 Flash',
    'gemini-2.5-pro': 'Gemini 2.5 Pro',
    'gemini-2.5-flash': 'Gemini 2.5 Flash',
    'gemini-3-flash-preview': 'Gemini 3 Flash',
    'gemini-3-pro-preview': 'Gemini 3 Pro',
    'gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
    'gemini-2.5-flash-lite': 'Gemini 2.5 Flash Lite',"""

count = content.count(old_display_gemini)
if count > 0:
    content = content.replace(old_display_gemini, new_display_gemini)
    print(f"4. Updated MODEL_DISPLAY with new Gemini models ({count})")
    changes += count

with open(ws_path, 'w', encoding='utf-8') as f:
    f.write(content)

# =============================================================
# 5. Update models.json with new Gemini chat models
# =============================================================

with open(models_path, 'r') as f:
    models = json.load(f)

gemini = models['providers'].get('gemini', {})
current_ids = {m['id'] for m in gemini.get('models', [])}

new_models = [
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro"},
    {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash (Preview)"},
    {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro (Preview)"},
    {"id": "gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro (Preview)"},
    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
]

gemini['models'] = new_models
gemini['image_model'] = 'imagen-4.0-generate-001'
gemini['video_model'] = 'veo-3.1-generate-preview'
models['providers']['gemini'] = gemini

with open(models_path, 'w') as f:
    json.dump(models, f, indent=4, ensure_ascii=False)

added = [m['id'] for m in new_models if m['id'] not in current_ids]
print(f"5. Updated models.json: Gemini now has {len(new_models)} chat models")
if added:
    print(f"   Added: {', '.join(added)}")

print(f"\nTotal changes in web_server.py: {changes}")
print("DONE")
