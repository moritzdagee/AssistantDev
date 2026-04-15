#!/usr/bin/env python3
"""
Fix: Strikte Provider-Auswahl – kein stiller Fallback.
- Bug 1: Provider korrekt durchreichen (war bereits OK, nur Haertung)
- Bug 2: generate_image() – kein Fallback auf anderen Provider
- Bug 3: Gemini Bildgenerierung – korrektes Modell
- Bug 4: generate_video() – kein stiller Fallback, Provider durchreichen
"""

import re
import sys

WEB_SERVER = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(WEB_SERVER, "r", encoding="utf-8") as f:
    code = f.read()

changes = 0

# ═══════════════════════════════════════════════════════════════
# Bug 2: generate_image() – entferne Fallback-Kette
# ═══════════════════════════════════════════════════════════════

old_generate_image = '''def generate_image(prompt, agent_name, provider_key=None):
    """Generate an image with automatic provider fallback. Returns (filename, filepath, info)."""
    config = load_models()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    fname = f"{agent_name}_image_{ts}.png"
    fpath = os.path.join(OUTPUT_DIR, fname)

    # Build ordered list of providers to try
    providers_to_try = []
    if provider_key and provider_key in IMAGE_PROVIDERS:
        providers_to_try.append(provider_key)
    for pkey in ['gemini', 'openai']:
        if pkey not in providers_to_try and pkey in IMAGE_PROVIDERS:
            if config['providers'].get(pkey, {}).get('api_key'):
                providers_to_try.append(pkey)

    if not providers_to_try:
        raise Exception("Kein Image-Provider verfuegbar (OpenAI oder Gemini API-Key benoetigt)")

    errors = []
    used_provider = None
    for pkey in providers_to_try:
        api_key = config['providers'][pkey]['api_key']
        try:
            _generate_image_single(prompt, fpath, pkey, api_key)
            used_provider = pkey
            break
        except Exception as e:
            errors.append(f"{pkey}: {e}")
            print(f"  Image-Gen {pkey} fehlgeschlagen: {e}")

    if used_provider is None:
        raise Exception("Alle Image-Provider fehlgeschlagen: " + "; ".join(errors))

    fallback_info = ""
    if used_provider != providers_to_try[0]:
        fallback_info = f" (Fallback von {providers_to_try[0]} auf {used_provider})"

    return fname, fpath, fallback_info'''

new_generate_image = '''def generate_image(prompt, agent_name, provider_key=None):
    """Generate an image with the selected provider. No fallback to other providers."""
    config = load_models()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    fname = f"{agent_name}_image_{ts}.png"
    fpath = os.path.join(OUTPUT_DIR, fname)

    # Strikte Provider-Pruefung – kein Fallback
    if not provider_key or provider_key not in IMAGE_PROVIDERS:
        supported = ', '.join(IMAGE_PROVIDERS.keys())
        provider_name = provider_key or 'keiner'
        raise Exception(
            f"Bildgenerierung nicht verfuegbar mit {provider_name}. "
            f"Wechsle zu Google Gemini oder OpenAI fuer Bildgenerierung."
        )

    api_key = config['providers'].get(provider_key, {}).get('api_key', '')
    if not api_key:
        raise Exception(f"Kein API-Key fuer {provider_key} konfiguriert.")

    try:
        _generate_image_single(prompt, fpath, provider_key, api_key)
    except Exception as e:
        raise Exception(f"Fehler bei Bildgenerierung mit {provider_key}: {e}")

    return fname, fpath, ""'''

if old_generate_image in code:
    code = code.replace(old_generate_image, new_generate_image)
    changes += 1
    print("✓ Bug 2: generate_image() Fallback-Kette entfernt")
else:
    print("✗ Bug 2: generate_image() Pattern nicht gefunden – manuell pruefen!")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Bug 3: Gemini Bildgenerierung – korrektes Modell
# Aktuell: gemini-2.5-flash-image (scheint korrekt fuer die REST API)
# Der Prompt sagt gemini-2.0-flash-preview-image-generation
# Wir testen gemini-2.0-flash-preview-image-generation als primaeres Modell
# mit gemini-2.5-flash als intra-Gemini Fallback
# ═══════════════════════════════════════════════════════════════

old_gemini_image = '''    elif provider_key == 'gemini':
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={api_key}"
        r = requests.post(url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": "Generate an image: " + prompt}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}
            },
            timeout=120)
        data = r.json()
        if r.status_code != 200:
            raise Exception(f"Gemini: {data.get('error', {}).get('message', str(data))}")
        parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        for p in parts:
            if 'inlineData' in p:
                with open(fpath, 'wb') as f:
                    f.write(_b64.b64decode(p['inlineData']['data']))
                return True
        raise Exception("Gemini: Kein Bild generiert (moeglicherweise Content-Filter)")'''

new_gemini_image = '''    elif provider_key == 'gemini':
        # Gemini Bildgenerierung: primaer gemini-2.0-flash-preview-image-generation,
        # Fallback auf gemini-2.5-flash (nur innerhalb Gemini)
        gemini_models = ["gemini-2.0-flash-preview-image-generation", "gemini-2.5-flash"]
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

if old_gemini_image in code:
    code = code.replace(old_gemini_image, new_gemini_image)
    changes += 1
    print("✓ Bug 3: Gemini Bildgenerierung – Modell-Fallback innerhalb Gemini")
else:
    print("✗ Bug 3: Gemini Image Pattern nicht gefunden – manuell pruefen!")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Bug 4: generate_video() – kein stiller Fallback auf Gemini
# ═══════════════════════════════════════════════════════════════

old_video_check = '''    # Only Gemini supports video
    if not provider_key or provider_key not in VIDEO_PROVIDERS:
        provider_key = 'gemini'
    api_key = config['providers'].get(provider_key, {}).get('api_key')
    if not api_key:
        raise Exception("Video-Generierung benoetigt einen Gemini API-Key")'''

new_video_check = '''    # Strikte Provider-Pruefung – kein Fallback auf Gemini
    if not provider_key or provider_key not in VIDEO_PROVIDERS:
        provider_name = provider_key or 'keiner'
        raise Exception(
            f"Videogenerierung ist nur mit Google Gemini verfuegbar. "
            f"Bitte wechsle zu Gemini fuer Videogenerierung."
        )
    api_key = config['providers'].get(provider_key, {}).get('api_key')
    if not api_key:
        raise Exception("Video-Generierung benoetigt einen Gemini API-Key")'''

if old_video_check in code:
    code = code.replace(old_video_check, new_video_check)
    changes += 1
    print("✓ Bug 4: generate_video() Fallback entfernt")
else:
    print("✗ Bug 4: generate_video() Pattern nicht gefunden – manuell pruefen!")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Bug 2b: CREATE_IMAGE Handler – Provider durchreichen (Zeile 4481)
# Aktuell: current_provider ... if current_provider in IMAGE_PROVIDERS else None
# Mit None faellt es in die neue generate_image Fehlermeldung → gut!
# Aber: wir wollen den Provider immer durchreichen damit die Fehlermeldung korrekt ist
# ═══════════════════════════════════════════════════════════════

old_img_handler = '''                current_provider = state.get('provider', 'openai')
                img_provider = current_provider if current_provider in IMAGE_PROVIDERS else None
                fname, fpath, fallback_info = generate_image(img_prompt, state['agent'] or 'standard', img_provider)'''

new_img_handler = '''                current_provider = state.get('provider', 'anthropic')
                fname, fpath, fallback_info = generate_image(img_prompt, state['agent'] or 'standard', current_provider)'''

if old_img_handler in code:
    code = code.replace(old_img_handler, new_img_handler)
    changes += 1
    print("✓ Bug 2b: CREATE_IMAGE Handler – Provider direkt durchgereicht")
else:
    print("✗ Bug 2b: CREATE_IMAGE Handler Pattern nicht gefunden – manuell pruefen!")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Bug 4b: CREATE_VIDEO Handler – Provider durchreichen (Zeile 4497)
# Aktuell: generate_video(vid_prompt, state['agent'] or 'standard')
# Fehlt: provider_key Parameter
# ═══════════════════════════════════════════════════════════════

old_vid_handler = "                fname, fpath = generate_video(vid_prompt, state['agent'] or 'standard')"
new_vid_handler = "                fname, fpath = generate_video(vid_prompt, state['agent'] or 'standard', state.get('provider', 'anthropic'))"

if old_vid_handler in code:
    code = code.replace(old_vid_handler, new_vid_handler)
    changes += 1
    print("✓ Bug 4b: CREATE_VIDEO Handler – Provider durchgereicht")
else:
    print("✗ Bug 4b: CREATE_VIDEO Handler Pattern nicht gefunden – manuell pruefen!")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Schreiben
# ═══════════════════════════════════════════════════════════════

with open(WEB_SERVER, "w", encoding="utf-8") as f:
    f.write(code)

print(f"\n{'='*50}")
print(f"Gesamt: {changes} Aenderungen geschrieben in web_server.py")
