# Salesforce Clipper — Installation

Ein Bookmarklet das Salesforce Lead/Account/Opportunity/Contact-Daten
mit einem Klick in den Agent-Memory speichert.

## Voraussetzung

Der Web Clipper Server muss laufen (Port 8081).
Pruefe: `curl http://127.0.0.1:8081/agents` — sollte eine Agent-Liste zeigen.
Die Assistant.app startet den Server automatisch.

## Bookmarklet generieren

Das Bookmarklet enthaelt eine hardcodierte Agenten-Liste. Bei neuen Agenten
muss es neu generiert werden:

```bash
python3 ~/AssistantDev/scripts/generate_salesforce_bookmarklet.py
```

Der fertige Code wird nach `scripts/salesforce_bookmarklet.txt` geschrieben
und im Terminal angezeigt.

## Installation in Chrome

1. **Bookmarklet generieren:** `python3 ~/AssistantDev/scripts/generate_salesforce_bookmarklet.py`
2. **Code kopieren:** Inhalt von `~/AssistantDev/scripts/salesforce_bookmarklet.txt`
3. **Bookmark erstellen:** Rechtsklick auf die Lesezeichen-Leiste > "Seite hinzufuegen..."
4. **Name:** `SF Clipper`
5. **URL:** Den kopierten `javascript:void(...)` Code einfuegen
6. **Speichern**

## Installation in Safari

1. **Bookmarklet generieren:** Wie oben
2. **Beliebige Seite als Lesezeichen speichern** (z.B. diese Seite)
3. **Lesezeichen bearbeiten:** Lesezeichen-Sidebar > Rechtsklick auf das neue Lesezeichen > "Bearbeiten"
4. **Adresse:** Den `javascript:void(...)` Code einfuegen
5. **Name:** `SF Clipper`
6. **Hinweis:** Safari blockiert evtl. Popups. Falls der Clipper nicht funktioniert:
   Safari > Einstellungen > Websites > Pop-Up-Fenster > salesforce.com auf "Erlauben" setzen

## Benutzung

1. Oeffne eine Salesforce Lead/Account/Opportunity/Contact-Seite
2. Klicke auf das `SF Clipper` Lesezeichen
3. Ein Popup erscheint mit:
   - Erkanntem Seitentyp und Datensatz-Name
   - Vorschau der extrahierten Felder
   - Agent-Dropdown (hardcodierte Liste, sofort verfuegbar)
4. Agent auswaehlen und "Speichern" klicken
5. Gruene Bestaetigung: "Gespeichert in [agent]"

## Gespeichertes Format

```
=== SALESFORCE LEAD: Max Mustermann ===
URL: https://mycompany.lightning.force.com/lightning/r/Lead/...
Exportiert: 2026-04-02 14:30:00

Name: Max Mustermann
Company: Acme Corp
Email: max@acme.com
Phone: +49 123 456789
Status: Open
...
```

Dateiname: `salesforce_lead_Max_Mustermann_2026-04-02.txt`
Gespeichert in: `[agent]/memory/`

## Troubleshooting

**Popup blockiert:** Browser Popup-Blocker fuer salesforce.com deaktivieren.
Der Clipper nutzt kurze about:blank Popups um die CSP-Beschraenkung zu umgehen.

**Wenige Felder extrahiert:** Salesforce Lightning rendert Felder lazy.
Loesung: Seite ganz nach unten scrollen bevor der Clipper geklickt wird.

**Neuer Agent fehlt im Dropdown:** Bookmarklet neu generieren:
`python3 ~/AssistantDev/scripts/generate_salesforce_bookmarklet.py`
Dann den neuen Code als Bookmark-URL einfuegen.
