#!/bin/bash
# disable_macos_contacts_autopop.sh
#
# Schaltet macOS-Mechanismen ab, die selbststaendig E-Mail-Absender als Kontakte
# hinzufuegen oder Namen auf bestehende Contacts-Eintraege schreiben. Adressiert
# die Wurzel der "Contacts Pollution" (alle Account-Sources iCloud/Exchange/
# Google/CardDAV betroffen, weil contactsd/suggestd upstream schreibt).
#
# Was passiert:
#   1. defaults-Keys setzen (best effort — Keys variieren je macOS-Version)
#   2. Relevante Settings-Panes oeffnen mit Klartext-Anleitung was zu toggeln ist
#   3. contactsd/suggestd neu starten damit Aenderungen greifen
#
# Reversibel: alle Aenderungen sind defaults/Toggle-Settings, kein DB-Eingriff.
#
# Nutzung: bash ~/AssistantDev/scripts/disable_macos_contacts_autopop.sh

set -e

echo "════════════════════════════════════════════════════════════════"
echo "  macOS Contacts Auto-Population deaktivieren"
echo "════════════════════════════════════════════════════════════════"
echo ""

# ── 1. defaults: bekannte Keys setzen ─────────────────────────────────────────

echo "[1/3] Setze defaults-Keys (best effort)..."

# Siri/Spotlight Suggestions global drosseln (verhindert Vorschlaege->Contacts Backflow)
defaults write com.apple.suggestd SuggestionsAppLibraryEnabled -bool false 2>/dev/null && \
    echo "  ✓ com.apple.suggestd SuggestionsAppLibraryEnabled = false" || \
    echo "  ⚠ com.apple.suggestd SuggestionsAppLibraryEnabled — Schreibfehler"

# Pro-App fuer Mail explizit: Mail soll keine Suggestions an Contacts liefern
defaults write com.apple.suggestd com.apple.mail.SuggestionsAppLibraryEnabled -bool false 2>/dev/null && \
    echo "  ✓ com.apple.suggestd com.apple.mail.SuggestionsAppLibraryEnabled = false" || \
    echo "  ⚠ Mail-spezifisch — Schreibfehler"

# Mail: Sender-Auto-Add (aelterer Schluessel; auf neueren OS evtl. wirkungslos)
defaults write com.apple.mail AddSendersToPreviousRecipientsList -bool false 2>/dev/null && \
    echo "  ✓ com.apple.mail AddSendersToPreviousRecipientsList = false" || \
    echo "  ⚠ Mail AddSenders — Schreibfehler"

# Contacts.app: "in Mail gefundene Kontakte anzeigen" (Schluesselname variiert)
for KEY in ABShowSiriSuggestions ABShowFoundInMail ABFoundInMailSuggestions; do
    defaults write com.apple.AddressBook "$KEY" -bool false 2>/dev/null && \
        echo "  ✓ com.apple.AddressBook $KEY = false" || true
done

echo ""

# ── 2. Settings-Panes oeffnen + Klartext-Anleitung ────────────────────────────

echo "[2/3] Manuelle Schritte (defaults greifen nicht ueberall):"
echo ""
echo "  In Contacts.app:"
echo "    Contacts → Settings → General"
echo "    [ ] 'Show Contacts found in Mail'    UNCHECK"
echo "    [ ] 'Siri Suggestions'               UNCHECK (falls vorhanden)"
echo ""
echo "  In Mail.app:"
echo "    Mail → Settings → General"
echo "    [ ] 'Add invitations to Calendar...'  unbeeinflusst"
echo "    Mail → Settings → Composing"
echo "    [ ] 'Mark addresses not ending with...'  unbeeinflusst"
echo "    (Mail bietet kein direktes UI-Toggle fuer Sender-Autoadd mehr —"
echo "     der Backflow geht ueber Siri/Spotlight Suggestions, siehe Schritt 3.)"
echo ""
echo "  In System Settings:"
echo "    Apple Intelligence & Siri → Suggestions"
echo "    [ ] 'Allow Siri to suggest contacts in...'  UNCHECK fuer Mail + Contacts"
echo ""
read -p "  Soll ich die Settings-Panes jetzt oeffnen? (j/n): " ANSWER
if [[ "$ANSWER" =~ ^[jJyY] ]]; then
    open "x-apple.systempreferences:com.apple.Siri-Settings.extension" 2>/dev/null || \
        open "x-apple.systempreferences:com.apple.preference.speech" 2>/dev/null || true
    open -a Contacts 2>/dev/null && \
        osascript -e 'tell application "Contacts" to activate' \
                  -e 'tell application "System Events" to keystroke "," using command down' 2>/dev/null || true
    echo "  Settings-Panes geoeffnet. Bitte Toggles wie oben setzen."
fi

echo ""

# ── 3. Daemons neu starten ────────────────────────────────────────────────────

echo "[3/3] Daemons neu starten damit Aenderungen greifen..."
killall suggestd 2>/dev/null && echo "  ✓ suggestd neu gestartet" || echo "  · suggestd lief nicht"
killall contactsd 2>/dev/null && echo "  ✓ contactsd neu gestartet" || echo "  · contactsd lief nicht"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Fertig. Pollution sollte ab jetzt nicht mehr auftreten."
echo "  Verifikation in 24h: bash ~/AssistantDev/scripts/contact_watchdog.py"
echo "════════════════════════════════════════════════════════════════"
