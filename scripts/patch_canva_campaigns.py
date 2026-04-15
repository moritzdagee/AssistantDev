#!/usr/bin/env python3
"""Patch: Canva Brand Templates + Autofill (Campaign-Generierung)."""
import os, sys
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
src = open(WS).read()
MARKER = 'CANVA_CAMPAIGNS_V1'
if MARKER in src:
    print("Schon gepatcht.")
    sys.exit(0)

# Neue Funktionen nach canva_list_folders einfuegen
OLD = """def canva_list_folders(count=50):
    \"\"\"Listet Ordner im Canva-Account.\"\"\"
    return _canva_api('GET', '/folders', params={'count': count})"""

NEW = """def canva_list_folders(count=50):
    \"\"\"Listet Ordner im Canva-Account.\"\"\"
    return _canva_api('GET', '/folders', params={'count': count})


# CANVA_CAMPAIGNS_V1: Brand Templates + Autofill fuer Ad-Kampagnen
# Docs: https://www.canva.dev/docs/connect/api-reference/autofills/

def canva_list_brand_templates(query=None, count=50):
    \"\"\"Listet alle Brand Templates des Users (erfordert Canva Enterprise oder Team).\"\"\"
    params = {'count': count}
    if query:
        params['query'] = query
    return _canva_api('GET', '/brand-templates', params=params)

def canva_get_brand_template(template_id):
    \"\"\"Gibt Metadaten eines Brand Templates zurueck.\"\"\"
    return _canva_api('GET', f'/brand-templates/{template_id}')

def canva_get_template_dataset(template_id):
    \"\"\"Gibt die ausfuellbaren Felder (Dataset) eines Brand Templates zurueck.
    Zeigt welche Platzhalter (Text, Bild, Chart) befuellt werden koennen.\"\"\"
    return _canva_api('GET', f'/brand-templates/{template_id}/dataset')

def canva_autofill(template_id, data, title=None):
    \"\"\"Erstellt ein neues Design aus einem Brand Template mit automatisch
    befuellten Feldern (Texte, Bilder, Charts).

    template_id: Brand Template ID
    data: dict mit Feld-Mappings, z.B.:
      {
        "headline": {"type": "text", "text": "Summer Sale 50% Off"},
        "body": {"type": "text", "text": "Shop now at example.com"},
        "hero_image": {"type": "image", "asset_id": "abc123"}
      }
    title: Name des generierten Designs (optional)

    Returns: (ok, job_data) — Job ist async, Status via canva_get_autofill_job()
    \"\"\"
    body = {'brand_template_id': template_id, 'data': data}
    if title:
        body['title'] = title[:255]
    return _canva_api('POST', '/autofills', json_body=body)

def canva_get_autofill_job(job_id):
    \"\"\"Prueft den Status eines Autofill-Jobs (in_progress/success/failed).\"\"\"
    return _canva_api('GET', f'/autofills/{job_id}')

def canva_upload_asset(url, name='uploaded_image'):
    \"\"\"Laedt ein Bild/Asset von einer URL in Canva hoch. Gibt asset_id zurueck.\"\"\"
    body = {
        'asset_upload': {
            'type': 'external_url',
            'url': url,
            'name': name,
        }
    }
    return _canva_api('POST', '/assets/upload', json_body=body)

def canva_batch_campaign(template_id, rows, title_prefix='Campaign'):
    \"\"\"Generiert mehrere Designs aus einem Template mit verschiedenen Daten.
    rows: list of dicts, jeder dict = ein Design mit Feld-Mappings
    Gibt Liste von Job-IDs zurueck.

    Beispiel:
      rows = [
        {"headline": {"type":"text","text":"Ad Variant A"}, "cta": {"type":"text","text":"Buy Now"}},
        {"headline": {"type":"text","text":"Ad Variant B"}, "cta": {"type":"text","text":"Shop Now"}},
      ]
    \"\"\"
    jobs = []
    for i, row in enumerate(rows):
        title = f"{title_prefix} {i+1}"
        ok, data = canva_autofill(template_id, row, title=title)
        if ok:
            job_id = data.get('job', {}).get('id', data.get('id', ''))
            jobs.append({'index': i, 'ok': True, 'job_id': job_id, 'title': title})
        else:
            jobs.append({'index': i, 'ok': False, 'error': data.get('error', '?'), 'title': title})
    return jobs"""

if src.count(OLD) != 1:
    print(f"FEHLER: {src.count(OLD)} Vorkommen")
    sys.exit(2)
src = src.replace(OLD, NEW, 1)

# Route erweitern: neue actions in /api/canva
OLD_ROUTE = """    elif action == 'folders':
        ok, resp = canva_list_folders(count=data.get('count', 50))
        return jsonify({'ok': ok, 'data': resp})

    return jsonify({'error': f'Unbekannte action: {action}'})"""

NEW_ROUTE = """    elif action == 'folders':
        ok, resp = canva_list_folders(count=data.get('count', 50))
        return jsonify({'ok': ok, 'data': resp})

    # CANVA_CAMPAIGNS_V1: Brand Templates + Autofill Actions
    elif action == 'brand_templates' or action == 'templates':
        ok, resp = canva_list_brand_templates(query=data.get('query'), count=data.get('count', 50))
        return jsonify({'ok': ok, 'data': resp})

    elif action == 'template_dataset':
        tid = data.get('template_id', '')
        if not tid:
            return jsonify({'error': 'template_id erforderlich'})
        ok, resp = canva_get_template_dataset(tid)
        return jsonify({'ok': ok, 'data': resp})

    elif action == 'autofill':
        tid = data.get('template_id', '')
        field_data = data.get('data', {})
        if not tid:
            return jsonify({'error': 'template_id erforderlich'})
        if not field_data:
            return jsonify({'error': 'data (Feld-Mappings) erforderlich'})
        ok, resp = canva_autofill(tid, field_data, title=data.get('title'))
        return jsonify({'ok': ok, 'data': resp})

    elif action == 'autofill_status':
        jid = data.get('job_id', '')
        if not jid:
            return jsonify({'error': 'job_id erforderlich'})
        ok, resp = canva_get_autofill_job(jid)
        return jsonify({'ok': ok, 'data': resp})

    elif action == 'batch_campaign':
        tid = data.get('template_id', '')
        rows = data.get('rows', [])
        if not tid or not rows:
            return jsonify({'error': 'template_id und rows erforderlich'})
        jobs = canva_batch_campaign(tid, rows, title_prefix=data.get('title_prefix', 'Campaign'))
        return jsonify({'ok': True, 'jobs': jobs, 'count': len(jobs)})

    elif action == 'upload_asset':
        url = data.get('url', '')
        name = data.get('name', 'uploaded_image')
        if not url:
            return jsonify({'error': 'url erforderlich'})
        ok, resp = canva_upload_asset(url, name=name)
        return jsonify({'ok': ok, 'data': resp})

    return jsonify({'error': f'Unbekannte action: {action}'})"""

if src.count(OLD_ROUTE) != 1:
    print(f"FEHLER Route: {src.count(OLD_ROUTE)} Vorkommen")
    sys.exit(2)
src = src.replace(OLD_ROUTE, NEW_ROUTE, 1)

open(WS, 'w').write(src)
print("OK: Canva Campaigns + Autofill eingefuegt")
