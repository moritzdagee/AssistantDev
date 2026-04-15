#!/usr/bin/env python3
"""
Fix image generation in web_server.py:
1. Replace generate_image() with version that has automatic provider fallback
2. Update CREATE_IMAGE parsing to propagate fallback info to LLM response
"""

import re

SRC = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(SRC, 'r') as f:
    code = f.read()

# ── Fix 1: Replace generate_image function with fallback logic ──

OLD_GENERATE_IMAGE = '''def generate_image(prompt, agent_name, provider_key=None):
    """Generate an image using the best available provider. Returns (filename, filepath)."""
    config = load_models()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    fname = f"{agent_name}_image_{ts}.png"
    fpath = os.path.join(OUTPUT_DIR, fname)

    # Determine provider: use current if capable, otherwise fallback
    if not provider_key or provider_key not in IMAGE_PROVIDERS:
        for pkey in ['openai', 'gemini']:
            if pkey in IMAGE_PROVIDERS and config['providers'].get(pkey, {}).get('api_key'):
                provider_key = pkey
                break
    if not provider_key:
        raise Exception("Kein Image-Provider verfuegbar (OpenAI oder Gemini API-Key benoetigt)")

    api_key = config['providers'][provider_key]['api_key']
    fallback_info = ""

    if provider_key == 'openai':
        r = requests.post("https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "gpt-image-1", "prompt": prompt, "size": "1024x1024",
                  "quality": "medium", "output_format": "png"},
            timeout=120)
        data = r.json()
        if r.status_code != 200:
            raise Exception(f"OpenAI Image API Fehler: {data.get('error', {}).get('message', str(data))}")
        import base64
        img_b64 = data['data'][0]['b64_json']
        with open(fpath, 'wb') as f:
            f.write(base64.b64decode(img_b64))

    elif provider_key == 'gemini':
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
            raise Exception(f"Gemini Image API Fehler: {data.get('error', {}).get('message', str(data))}")
        import base64
        parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        img_found = False
        for p in parts:
            if 'inlineData' in p:
                with open(fpath, 'wb') as f:
                    f.write(base64.b64decode(p['inlineData']['data']))
                img_found = True
                break
        if not img_found:
            raise Exception("Gemini Image: Kein Bild generiert (moeglicherweise Content-Filter)")

    return fname, fpath, fallback_info'''

NEW_GENERATE_IMAGE = '''def _generate_image_single(prompt, fpath, provider_key, api_key):
    """Try generating an image with a single provider. Returns True on success."""
    import base64 as _b64

    if provider_key == 'openai':
        r = requests.post("https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "gpt-image-1", "prompt": prompt, "size": "1024x1024",
                  "quality": "medium", "output_format": "png"},
            timeout=120)
        data = r.json()
        if r.status_code != 200:
            raise Exception(f"OpenAI: {data.get('error', {}).get('message', str(data))}")
        with open(fpath, 'wb') as f:
            f.write(_b64.b64decode(data['data'][0]['b64_json']))
        return True

    elif provider_key == 'gemini':
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
        raise Exception("Gemini: Kein Bild generiert (moeglicherweise Content-Filter)")

    raise Exception(f"Unbekannter Image-Provider: {provider_key}")


def generate_image(prompt, agent_name, provider_key=None):
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

if OLD_GENERATE_IMAGE in code:
    code = code.replace(OLD_GENERATE_IMAGE, NEW_GENERATE_IMAGE)
    print("✓ generate_image() mit Provider-Fallback ersetzt")
else:
    print("✗ generate_image() Pattern nicht gefunden!")
    # Try to find partial match
    if 'def generate_image(' in code:
        print("  (Funktion existiert, aber Pattern stimmt nicht exakt)")
    exit(1)

# ── Fix 2: Update CREATE_IMAGE parsing — better success message ──

OLD_PARSE = """        # Parse CREATE_IMAGE
        created_images = []
        img_pattern = re.compile(r'\\[?CREATE_IMAGE:\\s*(.+?)\\]?(?:\\n|$)')
        img_matches = list(img_pattern.finditer(text))
        for m in reversed(img_matches):
            img_prompt = m.group(1).strip().rstrip(']')
            try:
                current_provider = state.get('provider', 'openai')
                img_provider = current_provider if current_provider in IMAGE_PROVIDERS else None
                fallback_msg = ""
                if img_provider is None:
                    for pk in ['openai', 'gemini']:
                        if pk in IMAGE_PROVIDERS:
                            img_provider = pk
                            fallback_msg = f" (Provider-Fallback: {current_provider} unterstuetzt keine Bilder, verwende {pk})"
                            break
                fname, fpath, _ = generate_image(img_prompt, state['agent'] or 'standard', img_provider)
                created_images.append({'filename': fname, 'path': fpath, 'prompt': img_prompt[:100]})
                replacement = f'[Bild generiert: {fname}]{fallback_msg}'
                text = text[:m.start()] + replacement + text[m.end()]
            except Exception as ie:
                text = text[:m.start()] + f'[Bild-Generierung fehlgeschlagen: {str(ie)}]' + text[m.end():]"""

NEW_PARSE = """        # Parse CREATE_IMAGE
        created_images = []
        img_pattern = re.compile(r'\\[?CREATE_IMAGE:\\s*(.+?)\\]?(?:\\n|$)')
        img_matches = list(img_pattern.finditer(text))
        for m in reversed(img_matches):
            img_prompt = m.group(1).strip().rstrip(']')
            try:
                current_provider = state.get('provider', 'openai')
                img_provider = current_provider if current_provider in IMAGE_PROVIDERS else None
                fname, fpath, fallback_info = generate_image(img_prompt, state['agent'] or 'standard', img_provider)
                created_images.append({'filename': fname, 'path': fpath, 'prompt': img_prompt[:100]})
                replacement = f'\\n\\n*Bild erfolgreich generiert: {fname}{fallback_info}. Das Bild wird unten angezeigt.*'
                text = text[:m.start()] + replacement + text[m.end()]
            except Exception as ie:
                text = text[:m.start()] + f'\\n\\n*Bild-Generierung fehlgeschlagen: {str(ie)}. Du kannst es erneut versuchen.*' + text[m.end():]"""

# The parsing block uses text[m.end():] with colon - check both variants
# Actually let me do a more targeted replacement
old_parse_line = "                replacement = f'[Bild generiert: {fname}]{fallback_msg}'"
new_parse_line = "                replacement = f'\\n\\n*Bild erfolgreich generiert: {fname}{fallback_info}. Das Bild wird unten angezeigt.*'"

if old_parse_line in code:
    code = code.replace(old_parse_line, new_parse_line)
    print("✓ Erfolgs-Nachricht verbessert")
else:
    print("✗ Erfolgs-Nachricht Pattern nicht gefunden")

# Fix the fallback_msg variable references
old_fb1 = """                current_provider = state.get('provider', 'openai')
                img_provider = current_provider if current_provider in IMAGE_PROVIDERS else None
                fallback_msg = ""
                if img_provider is None:
                    for pk in ['openai', 'gemini']:
                        if pk in IMAGE_PROVIDERS:
                            img_provider = pk
                            fallback_msg = f" (Provider-Fallback: {current_provider} unterstuetzt keine Bilder, verwende {pk})"
                            break
                fname, fpath, _ = generate_image(img_prompt, state['agent'] or 'standard', img_provider)"""

new_fb1 = """                current_provider = state.get('provider', 'openai')
                img_provider = current_provider if current_provider in IMAGE_PROVIDERS else None
                fname, fpath, fallback_info = generate_image(img_prompt, state['agent'] or 'standard', img_provider)"""

if old_fb1 in code:
    code = code.replace(old_fb1, new_fb1)
    print("✓ Fallback-Logik in Parsing vereinfacht (jetzt in generate_image)")
else:
    print("✗ Fallback-Logik Pattern nicht gefunden")

# Fix error message
old_err = "                text = text[:m.start()] + f'[Bild-Generierung fehlgeschlagen: {str(ie)}]' + text[m.end():]"
new_err = "                text = text[:m.start()] + f'\\n\\n*Bild-Generierung fehlgeschlagen: {str(ie)}. Du kannst es erneut versuchen.*' + text[m.end():]"
if old_err in code:
    code = code.replace(old_err, new_err)
    print("✓ Fehler-Nachricht verbessert")
else:
    print("✗ Fehler-Nachricht Pattern nicht gefunden")

# Also fix video error message
old_vid_err = "                text = text[:m.start()] + f'[Video-Generierung fehlgeschlagen: {str(ve)}]' + text[m.end():]"
new_vid_err = "                text = text[:m.start()] + f'\\n\\n*Video-Generierung fehlgeschlagen: {str(ve)}. Du kannst es erneut versuchen.*' + text[m.end():]"
if old_vid_err in code:
    code = code.replace(old_vid_err, new_vid_err)
    print("✓ Video-Fehler-Nachricht verbessert")

old_vid_ok = "                text = text[:m.start()] + f'[Video generiert: {fname}]' + text[m.end():]"
new_vid_ok = "                text = text[:m.start()] + f'\\n\\n*Video erfolgreich generiert: {fname}. Das Video wird unten angezeigt.*' + text[m.end():]"
if old_vid_ok in code:
    code = code.replace(old_vid_ok, new_vid_ok)
    print("✓ Video-Erfolgs-Nachricht verbessert")

with open(SRC, 'w') as f:
    f.write(code)

print("\nAlle Aenderungen geschrieben.")
