#!/bin/bash
# sync_all.sh — Voller Sync beider Repos (Backend + Lovable-Frontend)
#
# Was passiert:
#   1. AssistantDev (Backend):
#      - fetch/pull/push auf aktuellem Branch
#      - develop -> main fast-forward-mergen wenn develop ahead ist (nur FF, bei
#        echten Merges abbrechen damit Release-Entscheidung beim User bleibt)
#      - gemergte Feature-Branches loeschen (lokal, nur wenn in develop oder main)
#   2. assistantdev-frontend (Lovable):
#      - fetch/pull/push auf main
#      - gemergte Feature-Branches loeschen (lokal, nur wenn in main)
#   3. Status-Report
#
# Sicherheitsregeln:
#   - develop -> main merge ist FAST-FORWARD ONLY. Bei divergierenden Historien
#     wird nicht gemergt (Release-Merges bleiben manuell).
#   - Branch-Loeschung nur fuer Branches die git als --merged markiert (kein -D).
#   - main / develop / aktuell-ausgecheckter Branch werden niemals geloescht.

set -u

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

BACKEND="$HOME/AssistantDev"
FRONTEND="$HOME/AssistantDev/frontend"
FRONTEND_DIST="$FRONTEND/dist"
# bun liegt nicht im Standard-PATH eines LaunchAgent / cron → manuell einbinden
export PATH="$HOME/.bun/bin:$PATH"

# Wird von den Sync-Funktionen gesetzt, damit der Build-Step weiss ob er noetig ist
FRONTEND_CHANGED=0

info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
err()   { echo -e "${RED}✗${NC}  $*"; }
head1() { echo -e "\n${BOLD}=== $* ===${NC}"; }

# Sync a single repo's current branch (fetch + ff-pull + push).
# Args: $1 repo dir, $2 repo label
sync_current_branch() {
    local dir="$1" label="$2"
    cd "$dir" || { err "$label: Pfad $dir nicht vorhanden"; return 1; }
    local branch
    branch=$(git rev-parse --abbrev-ref HEAD)

    info "$label ($branch): fetch"
    git fetch --all --prune >/dev/null 2>&1 || warn "$label: fetch fehlgeschlagen (offline?)"

    # Uncommitted changes?
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        warn "$label: uncommitted changes auf $branch — pull/push uebersprungen"
        git status -s
        return 2
    fi

    # Pull fast-forward
    local pull_out
    pull_out=$(git pull --ff-only 2>&1) || { err "$label: pull nicht fast-forward-bar:\n$pull_out"; return 3; }
    if echo "$pull_out" | grep -q "Already up to date"; then
        ok "$label: $branch already up to date"
    else
        ok "$label: $branch fast-forwarded"
        # Wenn Frontend-Repo frische Commits bekommen hat, Build triggern
        [ "$label" = "Frontend" ] && FRONTEND_CHANGED=1
    fi

    # Push
    local push_out
    push_out=$(git push 2>&1) || { err "$label: push fehlgeschlagen:\n$push_out"; return 4; }
    if echo "$push_out" | grep -q "Everything up-to-date"; then
        :
    else
        ok "$label: $branch nach origin gepusht"
    fi
    return 0
}

# Merge develop -> main (Backend only).
# Versucht Fast-Forward; wenn die Historien divergieren faellt auf einen
# normalen Merge-Commit zurueck. Bei echten Konflikten: merge --abort, warnen.
merge_develop_to_main() {
    cd "$BACKEND" || return 1
    local dev_sha main_sha
    dev_sha=$(git rev-parse origin/develop 2>/dev/null) || { warn "Backend: origin/develop fehlt"; return 1; }
    main_sha=$(git rev-parse origin/main 2>/dev/null)    || { warn "Backend: origin/main fehlt"; return 1; }

    if [ "$dev_sha" = "$main_sha" ]; then
        ok "Backend: main = develop (nichts zu mergen)"
        return 0
    fi

    # Wenn main bereits alle develop-Commits enthaelt, nichts zu tun.
    if git merge-base --is-ancestor "$dev_sha" "$main_sha"; then
        ok "Backend: main enthaelt bereits develop (nichts zu mergen)"
        return 0
    fi

    # Dirty working tree: kein checkout-Switch, weil sonst Dateien verlorengehen koennten.
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        warn "Backend: uncommitted changes — develop->main uebersprungen"
        return 2
    fi

    local current
    current=$(git rev-parse --abbrev-ref HEAD)

    git fetch origin main:main >/dev/null 2>&1 || true
    git checkout main >/dev/null 2>&1 || { err "Backend: konnte main nicht auschecken"; git checkout "$current" >/dev/null 2>&1; return 3; }

    local merge_mode="FF"
    local merge_out
    if git merge --ff-only origin/develop >/dev/null 2>&1; then
        :
    else
        # Kein FF moeglich -> normaler Merge-Commit
        merge_mode="no-ff"
        merge_out=$(git merge --no-ff --no-edit -m "sync: develop -> main (via sync_all.sh)" origin/develop 2>&1)
        if [ $? -ne 0 ]; then
            err "Backend: Merge-Konflikt develop -> main:"
            echo "$merge_out" | head -20
            git merge --abort >/dev/null 2>&1 || true
            git checkout "$current" >/dev/null 2>&1
            warn "  -> bitte manuell aufloesen: git checkout main && git merge develop"
            return 4
        fi
    fi

    git push origin main >/dev/null 2>&1 || { err "Backend: push main fehlgeschlagen"; git checkout "$current" >/dev/null 2>&1; return 5; }
    git checkout "$current" >/dev/null 2>&1
    ok "Backend: develop -> main gemergt ($merge_mode) + gepusht"
    return 0
}

# Prune local branches that are fully merged into one of the given integration
# branches. NEVER force-deletes. NEVER deletes the currently checked-out branch
# or the integration branches themselves.
# Args: $1 repo dir, $2 label, $3...$N integration branches (z.B. main develop)
prune_merged() {
    local dir="$1" label="$2"; shift 2
    local integrations=("$@")
    cd "$dir" || return 1

    local current
    current=$(git rev-parse --abbrev-ref HEAD)

    # Kandidaten: alle lokalen Branches ausser current + integrations
    local to_delete=()
    while IFS= read -r b; do
        b=$(echo "$b" | sed 's/^[* ] *//' | awk '{print $1}')
        [ -z "$b" ] && continue
        [ "$b" = "$current" ] && continue
        local is_integration=0
        for i in "${integrations[@]}"; do
            [ "$b" = "$i" ] && is_integration=1 && break
        done
        [ "$is_integration" = "1" ] && continue

        # Branch muss in mindestens einer Integration --merged sein
        local merged=0
        for i in "${integrations[@]}"; do
            if git rev-parse --verify "$i" >/dev/null 2>&1; then
                if git branch --merged "$i" 2>/dev/null | grep -qE "^\s*\*?\s*${b}$"; then
                    merged=1
                    break
                fi
            fi
        done
        [ "$merged" = "1" ] && to_delete+=("$b")
    done < <(git for-each-ref --format='%(refname:short)' refs/heads/)

    if [ ${#to_delete[@]} -eq 0 ]; then
        ok "$label: keine Zombie-Branches (alles aufgeraeumt)"
        return 0
    fi

    for b in "${to_delete[@]}"; do
        if git branch -d "$b" >/dev/null 2>&1; then
            ok "$label: Branch '$b' geloescht (war gemergt)"
        else
            warn "$label: Branch '$b' konnte nicht geloescht werden (git -d abgelehnt)"
        fi
    done
}

# Baut das React-Frontend neu und startet das Backend durch deploy.sh neu,
# damit die neue dist/ vom laufenden Server ausgeliefert wird.
# Wird nur ausgefuehrt wenn Frontend-Commits frisch gepullt wurden ODER
# dist/ komplett fehlt.
build_frontend_and_redeploy() {
    local needs_build=0
    [ "$FRONTEND_CHANGED" = "1" ] && needs_build=1
    [ ! -f "$FRONTEND_DIST/index.html" ] && needs_build=1

    if [ "$needs_build" = "0" ]; then
        ok "Frontend: dist/ aktuell, kein Build noetig"
        return 0
    fi

    if ! command -v bun >/dev/null 2>&1; then
        err "Frontend: bun nicht im PATH — kann nicht bauen"
        warn "  -> installiere mit: curl -fsSL https://bun.sh/install | bash"
        return 1
    fi

    cd "$FRONTEND" || return 1

    # bun install nur wenn node_modules fehlt oder bun.lock juenger ist als das Verzeichnis
    if [ ! -d node_modules ] || [ bun.lock -nt node_modules ] || [ package.json -nt node_modules ]; then
        info "Frontend: bun install"
        if ! bun install 2>&1 | tail -3; then
            err "Frontend: bun install fehlgeschlagen"
            return 2
        fi
    fi

    info "Frontend: bun run build"
    local build_out
    build_out=$(bun run build 2>&1)
    if [ $? -ne 0 ]; then
        err "Frontend: build fehlgeschlagen:"
        echo "$build_out" | tail -15
        return 3
    fi
    ok "Frontend: neu gebaut ($(echo "$build_out" | grep -E 'built in|modules transformed' | tail -1))"

    # Backend neu starten damit die neue dist/ greift (web_server.py cached den
    # Pfad zwar nicht, aber Browser-Connections brauchen neues no-store-HTML)
    if [ -x "$BACKEND/scripts/deploy.sh" ]; then
        info "Backend: deploy.sh (Server-Neustart)"
        if bash "$BACKEND/scripts/deploy.sh" >/dev/null 2>&1; then
            ok "Backend: neu deployed (Healthcheck OK)"
        else
            warn "Backend: deploy.sh Fehler — manuell pruefen"
        fi
    fi
}

# Prueft nach dem Frontend-Pull, ob neue Commits Dateien AUSSERHALB des
# Lovable-Territoriums beruehrt haben (siehe frontend/ARCHITECTURE.md).
# Nur Warnung — bricht Sync nicht ab, damit du entscheiden kannst ob du's
# behaeltst, revertest oder anpasst.
check_lovable_territory() {
    cd "$FRONTEND" || return 0
    local prev head
    # HEAD@{1} = Position VOR der letzten Ref-Update-Operation (= vor dem pull)
    prev=$(git rev-parse 'HEAD@{1}' 2>/dev/null) || return 0
    head=$(git rev-parse HEAD)
    [ "$prev" = "$head" ] && return 0

    # Nur Commits von Lovables GitHub-App betrachten — so werden eigene
    # Claude/Moritz-Commits vom Guard ignoriert (sie duerfen ueberallhin).
    local changed
    changed=$(git log --author='gpt-engineer' --name-only --pretty=format: \
        "$prev..$head" 2>/dev/null | sort -u)
    [ -z "$changed" ] && return 0

    # Whitelist: Lovable darf diese Pfade beruehren
    local forbidden=""
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        case "$f" in
            src/components/*|src/index.css|index.html|public/*|\
            package.json|bun.lock|tsconfig*.json|\
            ARCHITECTURE.md|README.md|.gitignore)
                ;; # erlaubt
            *)
                forbidden="${forbidden}${f}\n"
                ;;
        esac
    done <<< "$changed"

    if [ -n "$forbidden" ]; then
        warn "Lovable hat Dateien ausserhalb seines Territoriums geaendert:"
        echo -e "$forbidden" | head -15 | sed 's/^/    ⚠ /'
        warn "  -> pruefen: git show ${prev}..${head} -- <datei>"
        warn "  -> Regeln: frontend/ARCHITECTURE.md"
    fi
}

# Headless-Browser-Check nach dem Build: laedt /app und prueft dass React
# in #root gerendert hat. Fangt Lovable-Bugs wie fehlende Context-Provider,
# 404 auf Assets, JS-Runtime-Fehler — genau die Klasse Bugs, die die
# Python-Grep-Tests NICHT sehen koennen.
run_frontend_smoketest() {
    local smoke="$BACKEND/tests/test_frontend_smoke.py"
    [ ! -f "$smoke" ] && return 0
    if ! python3 -c "import playwright" >/dev/null 2>&1; then
        warn "Frontend-Smoketest uebersprungen (playwright nicht installiert)"
        return 0
    fi
    info "Frontend-Smoketest (Chromium headless)"
    local out
    out=$(python3 "$smoke" --quiet 2>&1)
    local rc=$?
    if [ $rc -eq 0 ]; then
        ok "Frontend rendert sauber (#root gefuellt, keine Console-Errors)"
    else
        err "Frontend-Smoketest FAIL:"
        echo "$out" | tail -20
        return 1
    fi
}

##### RUN #####

head1 "Backend: AssistantDev"
sync_current_branch "$BACKEND" "Backend"
merge_develop_to_main
prune_merged "$BACKEND" "Backend" main develop

head1 "Frontend: assistantdev-frontend"
sync_current_branch "$FRONTEND" "Frontend"
check_lovable_territory
prune_merged "$FRONTEND" "Frontend" main

head1 "Frontend: Build + Deploy (wenn noetig)"
build_frontend_and_redeploy

head1 "Frontend: Smoketest"
run_frontend_smoketest

head1 "Status"
cd "$BACKEND"  && echo -e "${BOLD}Backend${NC}  $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)  [origin: $(git rev-parse --short '@{u}' 2>/dev/null || echo n/a)]"
cd "$FRONTEND" && echo -e "${BOLD}Frontend${NC} $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)  [origin: $(git rev-parse --short '@{u}' 2>/dev/null || echo n/a)]"

# Offene PRs falls gh verfuegbar
if command -v gh >/dev/null 2>&1; then
    echo ""
    cd "$BACKEND"  && open_be=$(gh pr list --state open --json number 2>/dev/null | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))' 2>/dev/null || echo "?")
    cd "$FRONTEND" && open_fe=$(gh pr list --state open --json number 2>/dev/null | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))' 2>/dev/null || echo "?")
    echo "Offene PRs — Backend: $open_be | Frontend: $open_fe"
fi

echo ""
ok "sync_all.sh fertig"
