# Cloudflare Tunnel Setup — `api.bios.love`

Ziel: `https://api.bios.love` zeigt auf deinen lokalen `localhost:8080`-Flask-Server,
damit Lovable (und jede andere Web-App) gegen die API arbeiten kann — mit Bearer-Token-Auth.

Die Schritte 1-3 brauchen **Browser-Interaktion** (Cloudflare-Login) und laufen einmalig.

---

## 1. Domain in Cloudflare aktivieren (einmalig, falls noch nicht)

Wenn `bios.love` bereits bei Cloudflare als Zone eingerichtet ist → überspringen.
Sonst:
1. https://dash.cloudflare.com öffnen, Account einloggen
2. „Add a site" → `bios.love` eintragen
3. Cloudflare zeigt dir Nameserver an — die musst du bei deinem Domain-Registrar (wo du `bios.love` gekauft hast) hinterlegen
4. Warten (kann wenige Minuten bis ~24h dauern), bis Status „Active" ist

## 2. Tunnel-Client authentifizieren

```bash
cloudflared tunnel login
```

Öffnet den Browser, du loggst dich in Cloudflare ein, wählst die Zone `bios.love` aus.
Danach liegt ein Cert in `~/.cloudflared/cert.pem`.

## 3. Tunnel anlegen + DNS-Route setzen

```bash
cloudflared tunnel create assistantdev-api
cloudflared tunnel route dns assistantdev-api api.bios.love
```

Der zweite Befehl erstellt automatisch den CNAME-Record in Cloudflare:
`api.bios.love → <tunnel-uuid>.cfargotunnel.com`.

Die erzeugte Credentials-Datei liegt in `~/.cloudflared/<UUID>.json`.

## 4. Tunnel-Config schreiben

`~/.cloudflared/config.yml`:

```yaml
tunnel: assistantdev-api
credentials-file: /Users/moritzcremer/.cloudflared/<UUID>.json   # Pfad aus Schritt 3

ingress:
  - hostname: api.bios.love
    service: http://localhost:8080
  - service: http_status:404
```

(Die UUID im `credentials-file`-Pfad mit der echten ersetzen — `ls ~/.cloudflared/` zeigt sie.)

## 5. Einmal manuell starten (zum Testen)

```bash
cloudflared tunnel run assistantdev-api
```

In einem zweiten Terminal:

```bash
TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/AssistantDev/config/api_auth.json'))['api_token'])")

# Ohne Token -> 401
curl -s -o /dev/null -w "%{http_code}\n" https://api.bios.love/api/oauth-status

# Mit Token -> 200
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" https://api.bios.love/api/oauth-status
```

## 6. Permanent laufen lassen (LaunchAgent)

```bash
cp ~/AssistantDev/scripts/com.assistantdev.cloudflared.plist.optional \
   ~/Library/LaunchAgents/com.assistantdev.cloudflared.plist
launchctl load ~/Library/LaunchAgents/com.assistantdev.cloudflared.plist
```

Der Tunnel startet jetzt bei jedem Login automatisch neu. Log: `~/AssistantDev/logs/cloudflared.log`.

Stoppen:
```bash
launchctl unload ~/Library/LaunchAgents/com.assistantdev.cloudflared.plist
```

## 7. Lovable konfigurieren

Im Lovable-Projekt (lovable.dev → deine App → Project Settings → Environment Variables):

| Key | Wert |
|---|---|
| `VITE_API_BASE_URL` | `https://api.bios.love` |
| `VITE_API_TOKEN` | Inhalt von `config/api_auth.json` → Feld `api_token` |

Den Token zeigen:
```bash
python3 -c "import json; print(json.load(open('$HOME/AssistantDev/config/api_auth.json'))['api_token'])"
```

Nach dem Setzen der Env-Variablen → „Redeploy" in Lovable. Die Preview und die Published
App greifen dann live auf deine Mac-API zu.

---

## Was das Backend schützt

- **Localhost-Requests** (`Host: localhost:8080`, Desktop-App + Claude + Tests) → kein Token nötig
- **Tunnel-Requests** (`Host: api.bios.love`) → `Authorization: Bearer <token>` Pflicht, sonst 401
- **Fehlender Token in Config** (`api_auth.json` weg) → externer Zugriff 503, localhost bleibt frei
- **CORS** erlaubt nur `*.lovable.app`, `*.lovable.dev`, `*.bios.love`, `localhost:5173`/`:8080`

## Token neu generieren (falls kompromittiert)

```bash
python3 -c "import json,secrets; p='$HOME/AssistantDev/config/api_auth.json'; d=json.load(open(p)); d['api_token']=secrets.token_urlsafe(32); json.dump(d,open(p,'w'),indent=2); print('neuer Token:',d['api_token'])"
bash ~/AssistantDev/scripts/deploy.sh
```

Danach in Lovable die `VITE_API_TOKEN`-Env-Variable aktualisieren.
