-- AppleScript für Apple Mail Regel
-- Speichert eingehende E-Mails als .eml in den email_inbox Ordner
-- NUR E-Mails aus der regulären Inbox - kein Junk/Spam
-- Einrichten: Mail → Einstellungen → Regeln → Regel hinzufügen
-- Bedingung: "Junk Mail Status" ist "kein Junk" (oder "isNotJunk")
-- Aktion: "Skript ausführen" → diese Datei auswählen

using terms from application "Mail"
    on perform mail action with messages theMessages for rule theRule
        set inboxPath to (POSIX path of (path to home folder)) & "Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/email_inbox/"
        
        -- Ordner erstellen falls nicht vorhanden
        do shell script "mkdir -p " & quoted form of inboxPath
        
        repeat with theMessage in theMessages
            
            -- Junk prüfen: nur nicht-Junk E-Mails speichern
            set isJunk to junk mail status of theMessage
            if isJunk is false then
                
                set dateStr to do shell script "date +%Y-%m-%d_%H-%M-%S"
                set msgSubject to subject of theMessage
                
                -- Sicheren Dateinamen erstellen
                set safeName to do shell script "echo " & quoted form of msgSubject & " | tr -cd '[:alnum:] _-' | cut -c1-40 | tr ' ' '_'"
                set fileName to dateStr & "_" & safeName & ".eml"
                set filePath to inboxPath & fileName
                
                -- E-Mail als .eml exportieren
                set theSource to source of theMessage
                set fileRef to open for access POSIX file filePath with write permission
                set eof fileRef to 0
                write theSource to fileRef
                close access fileRef
                
            end if
        end repeat
    end perform mail action with messages
end using terms from
