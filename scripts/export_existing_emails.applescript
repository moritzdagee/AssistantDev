-- export_existing_emails.applescript
-- Exportiert alle E-Mails der letzten 12 Monate aus Apple Mail
-- Ziel: ~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/email_inbox/
-- Duplikate werden automatisch uebersprungen (gleicher Dateiname = gleicher Tag + Betreff)
-- Durchsucht: Inbox, Sent, alle Unterordner — NICHT Trash und Junk
--
-- Ausfuehren: osascript ~/AssistantDev/scripts/export_existing_emails.applescript

set inboxPath to (POSIX path of (path to home folder)) & "Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/email_inbox/"

-- Ordner erstellen falls nicht vorhanden
do shell script "mkdir -p " & quoted form of inboxPath

-- Cutoff: 12 Monate zurueck
set cutoffDate to (current date) - (365 * 24 * 60 * 60)

set exportCount to 0
set skipCount to 0
set errorCount to 0

-- Hilfsfunktion: sicheren Dateinamen aus Betreff erstellen
on makeSafeFilename(msgSubject)
	try
		set safeName to do shell script "echo " & quoted form of msgSubject & " | tr -cd '[:alnum:] _-' | cut -c1-40 | tr ' ' '_'"
		if safeName is "" then set safeName to "kein_betreff"
		return safeName
	on error
		return "kein_betreff"
	end try
end makeSafeFilename

-- Hilfsfunktion: Datum als String formatieren
on formatDate(theDate)
	set y to year of theDate as string
	set m to (month of theDate as integer) as string
	if length of m is 1 then set m to "0" & m
	set d to day of theDate as string
	if length of d is 1 then set d to "0" & d
	set h to hours of theDate as string
	if length of h is 1 then set h to "0" & h
	set mins to minutes of theDate as string
	if length of mins is 1 then set mins to "0" & mins
	set s to seconds of theDate as string
	if length of s is 1 then set s to "0" & s
	return y & "-" & m & "-" & d & "_" & h & "-" & mins & "-" & s
end formatDate

-- Hilfsfunktion: pruefen ob Mailbox uebersprungen werden soll
on shouldSkipMailbox(boxName)
	set lowerName to do shell script "echo " & quoted form of boxName & " | tr '[:upper:]' '[:lower:]'"
	if lowerName contains "trash" then return true
	if lowerName contains "junk" then return true
	if lowerName contains "papierkorb" then return true
	if lowerName contains "spam" then return true
	if lowerName contains "werbung" then return true
	if lowerName contains "deleted" then return true
	return false
end shouldSkipMailbox

-- Hilfsfunktion: eine einzelne E-Mail exportieren
on exportMessage(theMessage, inboxPath, cutoffDate, exportCount, skipCount, errorCount, totalInfo)
	try
		set msgDate to date received of theMessage
		if msgDate is missing value then set msgDate to date sent of theMessage
		if msgDate is missing value then return {exportCount, skipCount, errorCount}

		-- Aelter als 12 Monate? Ueberspringen.
		if msgDate < cutoffDate then return {exportCount, skipCount, errorCount}

		set msgSubject to subject of theMessage
		if msgSubject is missing value then set msgSubject to ""

		set dateStr to my formatDate(msgDate)
		set safeName to my makeSafeFilename(msgSubject)
		set fileName to "email_" & dateStr & "_" & safeName & ".eml"
		set filePath to inboxPath & fileName

		-- Duplikat-Check: Datei existiert bereits?
		try
			do shell script "test -f " & quoted form of filePath
			-- Datei existiert → ueberspringen
			return {exportCount, skipCount + 1, errorCount}
		on error
			-- Datei existiert nicht → exportieren
		end try

		-- E-Mail exportieren
		set theSource to source of theMessage
		set fileRef to open for access POSIX file filePath with write permission
		set eof fileRef to 0
		write theSource to fileRef
		close access fileRef

		-- Fortschritt anzeigen
		log totalInfo & ": " & msgSubject

		return {exportCount + 1, skipCount, errorCount}

	on error errMsg
		log "Fehler: " & errMsg
		return {exportCount, skipCount, errorCount + 1}
	end try
end exportMessage

tell application "Mail"

	-- Alle Accounts durchgehen
	set allAccounts to every account
	set totalMessages to 0

	-- Erst zaehlen fuer Fortschrittsanzeige
	log "Zaehle E-Mails..."

	repeat with acct in allAccounts
		set acctName to name of acct
		set allBoxes to every mailbox of acct

		repeat with mbox in allBoxes
			set boxName to name of mbox
			if not (my shouldSkipMailbox(boxName)) then
				try
					set msgCount to count of messages of mbox
					set totalMessages to totalMessages + msgCount
				end try

				-- Unterordner
				try
					set subBoxes to every mailbox of mbox
					repeat with subBox in subBoxes
						set subName to name of subBox
						if not (my shouldSkipMailbox(subName)) then
							try
								set subCount to count of messages of subBox
								set totalMessages to totalMessages + subCount
							end try
						end if
					end repeat
				end try
			end if
		end repeat
	end repeat

	log "Gefunden: " & totalMessages & " E-Mails insgesamt. Starte Export..."

	set processedCount to 0

	-- Jetzt exportieren
	repeat with acct in allAccounts
		set acctName to name of acct
		set allBoxes to every mailbox of acct

		repeat with mbox in allBoxes
			set boxName to name of mbox
			if not (my shouldSkipMailbox(boxName)) then

				log "Mailbox: " & acctName & "/" & boxName

				try
					set boxMessages to every message of mbox
					repeat with theMessage in boxMessages
						set processedCount to processedCount + 1
						set totalInfo to "Exportiere " & processedCount & " von " & totalMessages
						set {exportCount, skipCount, errorCount} to my exportMessage(theMessage, inboxPath, cutoffDate, exportCount, skipCount, errorCount, totalInfo)
					end repeat
				end try

				-- Unterordner
				try
					set subBoxes to every mailbox of mbox
					repeat with subBox in subBoxes
						set subName to name of subBox
						if not (my shouldSkipMailbox(subName)) then
							log "  Unterordner: " & subName
							try
								set subMessages to every message of subBox
								repeat with theMessage in subMessages
									set processedCount to processedCount + 1
									set totalInfo to "Exportiere " & processedCount & " von " & totalMessages
									set {exportCount, skipCount, errorCount} to my exportMessage(theMessage, inboxPath, cutoffDate, exportCount, skipCount, errorCount, totalInfo)
								end repeat
							end try
						end if
					end repeat
				end try

			end if
		end repeat
	end repeat

end tell

set summaryMsg to "Fertig! " & exportCount & " exportiert, " & skipCount & " uebersprungen (Duplikate), " & errorCount & " Fehler."
log summaryMsg
display dialog summaryMsg buttons {"OK"} default button "OK" with title "E-Mail Export"
