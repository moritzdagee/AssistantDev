#!/usr/bin/env python3
"""
Patch-Skript: Erhoeht Veo Polling-Timeout auf 6 Minuten, fuegt Logging hinzu,
erkennt RAI/Content-Filter und liefert bessere Fehlermeldungen.

Zielfunktion: generate_video in src/web_server.py (nur 1x definiert,
ausserhalb der duplizierten Bloecke 1-1358 — sicher zu patchen).

Der Patch ersetzt exakt den Poll-Loop-Block durch eine erweiterte Variante.
Idempotent: wenn der neue Marker schon vorhanden ist, wird nichts getan.
"""
import os
import sys

WS = os.path.expanduser("~/AssistantDev/src/web_server.py")

OLD = '''    task_update(task_id, progress=5, message='Video wird generiert...')

    # Poll for completion (max 5 minutes)
    import base64
    poll_url = f"https://generativelanguage.googleapis.com/v1beta/{op_name}?key={api_key}"
    MAX_ATTEMPTS = 60
    for _attempt in range(MAX_ATTEMPTS):
        import time as _t
        _t.sleep(5)
        # Simulated progress (5 -> 95) based on attempt number, clamped
        pct = min(95, 5 + int((_attempt + 1) * 90 / MAX_ATTEMPTS))
        if _attempt < 6:
            phase = 'Video wird initialisiert...'
        elif _attempt < 24:
            phase = 'Video wird gerendert...'
        elif _attempt < 48:
            phase = 'Rendering laeuft, fast fertig...'
        else:
            phase = 'Letzte Schritte...'
        task_update(task_id, progress=pct, message=phase)

        pr = requests.get(poll_url, timeout=30)
        pdata = pr.json()
        if pdata.get('done'):
            response = pdata.get('response', {})
            # Handle current Veo API format: generateVideoResponse.generatedSamples
            samples = response.get('generateVideoResponse', {}).get('generatedSamples', [])
            # Fallback: older format with predictions or generatedVideos
            if not samples:
                samples = response.get('predictions', response.get('generatedVideos', []))
            if not samples:
                raise Exception("Gemini Veo: Kein Video generiert")
            # Try URI download first (current API returns download URL)
            vid_uri = samples[0].get('video', {}).get('uri', '')
            if vid_uri:
                task_update(task_id, progress=97, message='Lade Video herunter...')
                # API key is required for download
                dl_url = vid_uri + ('&' if '?' in vid_uri else '?') + f'key={api_key}'
                vr = requests.get(dl_url, timeout=120)
                if vr.status_code != 200:
                    raise Exception(f"Gemini Veo: Video-Download fehlgeschlagen (HTTP {vr.status_code})")
                with open(fpath, 'wb') as f:
                    f.write(vr.content)
                task_done(task_id, message='Video fertig')
                return fname, fpath
            # Fallback: base64 encoded video
            vid_b64 = samples[0].get('bytesBase64Encoded', samples[0].get('video', {}).get('bytesBase64Encoded', ''))
            if vid_b64:
                task_update(task_id, progress=97, message='Dekodiere Video...')
                with open(fpath, 'wb') as f:
                    f.write(base64.b64decode(vid_b64))
                task_done(task_id, message='Video fertig')
                return fname, fpath
            raise Exception("Gemini Veo: Video-Format nicht erkannt")
        if pdata.get('error'):
            raise Exception(f"Gemini Veo Fehler: {pdata['error'].get('message', str(pdata['error']))}")

    raise Exception("Gemini Veo: Timeout nach 5 Minuten")'''

NEW = '''    task_update(task_id, progress=5, message='Video wird generiert...')

    # Poll for completion (max 6 minutes: 72 Versuche x 5 Sekunden = 360 s)
    # VEO_PATCH_V2: 6-Minuten-Timeout, detailliertes Logging, Content-Filter-Erkennung
    import base64
    import json as _vjson
    poll_url = f"https://generativelanguage.googleapis.com/v1beta/{op_name}?key={api_key}"
    MAX_ATTEMPTS = 72
    POLL_INTERVAL = 5  # seconds → 72 * 5 = 360 s (6 min)
    TOTAL_SECS = MAX_ATTEMPTS * POLL_INTERVAL
    print(f"[VEO] Poll gestartet: op={op_name} max_attempts={MAX_ATTEMPTS} interval={POLL_INTERVAL}s total={TOTAL_SECS}s", flush=True)

    last_api_snapshot = ''
    for _attempt in range(MAX_ATTEMPTS):
        import time as _t
        _t.sleep(POLL_INTERVAL)
        # Simulated progress (5 -> 95) based on attempt number, clamped
        pct = min(95, 5 + int((_attempt + 1) * 90 / MAX_ATTEMPTS))
        if _attempt < 8:
            phase = 'Video wird initialisiert...'
        elif _attempt < 28:
            phase = 'Video wird gerendert...'
        elif _attempt < 56:
            phase = 'Rendering laeuft, fast fertig...'
        else:
            phase = 'Letzte Schritte...'
        task_update(task_id, progress=pct, message=phase)

        try:
            pr = requests.get(poll_url, timeout=30)
            pdata = pr.json()
        except Exception as poll_ex:
            # Transient network error — log and keep trying
            print(f"[VEO] Poll #{_attempt+1}/{MAX_ATTEMPTS} Netzwerk-Fehler: {poll_ex}", flush=True)
            continue

        # Compact log for every attempt with current state
        _state_keys = sorted(list(pdata.keys()))
        _done_flag = pdata.get('done')
        _has_err = bool(pdata.get('error'))
        print(f"[VEO] Poll #{_attempt+1}/{MAX_ATTEMPTS} done={_done_flag} err={_has_err} keys={_state_keys}", flush=True)
        last_api_snapshot = _vjson.dumps(pdata)[:600]

        if pdata.get('error'):
            err_obj = pdata['error']
            err_msg = err_obj.get('message', str(err_obj))
            err_code = err_obj.get('code', '?')
            print(f"[VEO] API-Fehler code={err_code}: {err_msg}", flush=True)
            raise Exception(f"Gemini Veo API-Fehler (code {err_code}): {err_msg}")

        if not pdata.get('done'):
            continue

        # done=True — response auswerten
        response = pdata.get('response', {}) or {}
        gvr = response.get('generateVideoResponse', {}) or {}

        # Content-Filter: raiMediaFilteredCount > 0 → Video wurde von Safety-Filtern blockiert
        rai_count = gvr.get('raiMediaFilteredCount', 0)
        rai_reasons = gvr.get('raiMediaFilteredReasons', [])
        if rai_count and not gvr.get('generatedSamples'):
            reason_txt = '; '.join(str(r) for r in rai_reasons) if rai_reasons else 'Keine Details'
            print(f"[VEO] CONTENT FILTER: rai_count={rai_count} reasons={reason_txt}", flush=True)
            raise Exception(f"Gemini Veo: Video wurde vom Content-Filter blockiert ({reason_txt}). Bitte Prompt anpassen.")

        # Samples in allen bekannten Formaten suchen
        samples = gvr.get('generatedSamples', [])
        if not samples:
            samples = response.get('predictions', response.get('generatedVideos', []))
        if not samples:
            # Log full response for debugging
            resp_preview = _vjson.dumps(response)[:800]
            print(f"[VEO] done=true aber keine samples gefunden. Response: {resp_preview}", flush=True)
            raise Exception(
                f"Gemini Veo: Kein Video generiert (done=true, leere Response). "
                f"Details: {resp_preview[:200]}"
            )

        # Try URI download first (current API returns download URL)
        vid_uri = samples[0].get('video', {}).get('uri', '')
        if vid_uri:
            print(f"[VEO] Erfolgreich: Download-URI erhalten, lade Video...", flush=True)
            task_update(task_id, progress=97, message='Lade Video herunter...')
            dl_url = vid_uri + ('&' if '?' in vid_uri else '?') + f'key={api_key}'
            vr = requests.get(dl_url, timeout=180)
            if vr.status_code != 200:
                raise Exception(f"Gemini Veo: Video-Download fehlgeschlagen (HTTP {vr.status_code})")
            with open(fpath, 'wb') as f:
                f.write(vr.content)
            print(f"[VEO] Video gespeichert: {fpath} ({len(vr.content)} bytes)", flush=True)
            task_done(task_id, message='Video fertig')
            return fname, fpath

        # Fallback: base64 encoded video
        vid_b64 = samples[0].get('bytesBase64Encoded', samples[0].get('video', {}).get('bytesBase64Encoded', ''))
        if vid_b64:
            print(f"[VEO] Erfolgreich: base64-Video erhalten, dekodiere...", flush=True)
            task_update(task_id, progress=97, message='Dekodiere Video...')
            with open(fpath, 'wb') as f:
                f.write(base64.b64decode(vid_b64))
            task_done(task_id, message='Video fertig')
            return fname, fpath

        # Bekanntes Format nicht erkannt → volle Debug-Ausgabe
        sample_preview = _vjson.dumps(samples[0])[:500]
        print(f"[VEO] Sample-Format nicht erkannt. Erstes Sample: {sample_preview}", flush=True)
        raise Exception(f"Gemini Veo: Video-Format nicht erkannt. Sample: {sample_preview[:200]}")

    print(f"[VEO] TIMEOUT nach {TOTAL_SECS}s (letzte API-Snapshot: {last_api_snapshot[:300]})", flush=True)
    raise Exception(f"Gemini Veo: Timeout nach {TOTAL_SECS//60} Minuten ({MAX_ATTEMPTS} Versuche * {POLL_INTERVAL}s). Letzter Status: {last_api_snapshot[:150]}")'''


def main():
    if not os.path.exists(WS):
        print(f"FEHLER: {WS} existiert nicht", file=sys.stderr)
        sys.exit(1)
    src = open(WS).read()

    if 'VEO_PATCH_V2' in src:
        print("Patch bereits angewendet (VEO_PATCH_V2 Marker gefunden) — nichts zu tun.")
        return

    if OLD not in src:
        print("FEHLER: Alter Block nicht exakt gefunden. Abbruch.", file=sys.stderr)
        sys.exit(2)

    occurrences = src.count(OLD)
    print(f"Gefunden: {occurrences} Vorkommen des alten Blocks")
    if occurrences != 1:
        print(f"FEHLER: Erwarte genau 1 Vorkommen (duplizierte Bloecke!), gefunden: {occurrences}", file=sys.stderr)
        sys.exit(3)

    new_src = src.replace(OLD, NEW, 1)
    with open(WS, 'w') as f:
        f.write(new_src)
    print(f"OK: {WS} gepatcht ({len(src)} -> {len(new_src)} bytes)")


if __name__ == '__main__':
    main()
