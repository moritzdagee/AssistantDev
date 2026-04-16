"""Dynamic Capabilities Injection fuer Agent-System-Prompts.

Jeder Agent-Prompt besteht aus zwei Teilen:
  1. USER SECTION   — vom Nutzer gepflegt, wird NIEMALS ueberschrieben.
  2. SYSTEM SECTION — vom Server gepflegt, wird bei jedem Start frisch gesetzt.

Die beiden Teile werden durch SEPARATOR getrennt. Alles oberhalb des
Separators gehoert dem Nutzer; alles ab (einschliesslich) dem Separator
wird bei jedem Server-Start regeneriert.

Oeffentliche API:
  - split_agent_prompt(content)          -> (user_section, system_section)
  - get_capabilities_block(agent_config) -> str
  - migrate_agent_file(path, block)      -> bool (True wenn geschrieben)
  - inject_capabilities_on_startup(...)  -> int (# aktualisierter Dateien)
"""
from __future__ import annotations

import json
import os
from typing import Tuple

# ─── Trennzeichen-Konvention ────────────────────────────────────────────────
# Muss im User-Content auf keinen Fall vorkommen — daher ASCII-Marker mit
# eindeutigem Hinweistext. Wird so in die Datei geschrieben, dass man beim
# Oeffnen sofort sieht: alles ab hier ist automatisch.
SEPARATOR = "--- SYSTEM CAPABILITIES (AUTO-GENERATED - DO NOT EDIT BELOW) ---"


# ─── Split / Merge ──────────────────────────────────────────────────────────

def split_agent_prompt(content: str) -> Tuple[str, str]:
    """Zerlegt einen Agent-Prompt in (user_section, system_section).

    - Trennzeichen vorhanden: user = alles VOR SEPARATOR (ohne trailing \n);
      system = SEPARATOR + alles dahinter.
    - Trennzeichen fehlt: user = gesamter Inhalt, system = "".

    Die zurueckgegebene user_section behaelt ihren Inhalt exakt bei,
    abgesehen davon, dass wir die eventuelle Leerzeile direkt vor dem
    Separator nicht mitschneiden (damit Merge sauber wird).
    """
    if content is None:
        return "", ""
    idx = content.find(SEPARATOR)
    if idx == -1:
        return content, ""
    user = content[:idx]
    system = content[idx:]
    # Trailing-Newlines im User-Teil kappen, damit Merge sauber ist.
    user = user.rstrip("\n").rstrip()
    return user, system


def merge_sections(user_section: str, system_section: str) -> str:
    """Fuegt User- und System-Sektion zu einer Datei-Ablage zusammen.

    Strikt: user_section bleibt byteweise erhalten, dazwischen kommen
    genau zwei Newlines plus die system_section.
    """
    user = user_section.rstrip("\n").rstrip()
    sys_ = (system_section or "").strip("\n")
    if not sys_:
        return user + "\n"
    return user + "\n\n" + sys_ + "\n"


# ─── Capabilities-Block ─────────────────────────────────────────────────────

_DEFAULT_DATALAKE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake"
)
_DEFAULT_CLAUDE_OUTPUTS = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_outputs"
)


def _active_providers(models_config: dict) -> list[dict]:
    """Extrahiert aktive Provider + Modelle aus dem geladenen models.json.

    Gibt eine Liste von Eintraegen zurueck:
      {"key": "anthropic", "name": "Anthropic", "models": [...], "image": str|None, "video": str|None}
    Provider ohne api_key oder mit Status-Hinweis "QUOTA_EXCEEDED" werden
    dennoch aufgefuehrt, aber markiert — der Agent soll wissen was nominal
    verfuegbar ist.
    """
    providers = []
    for key, cfg in (models_config or {}).get("providers", {}).items():
        if not isinstance(cfg, dict):
            continue
        name = cfg.get("name", key.title())
        models = [m.get("name") or m.get("id") for m in cfg.get("models", []) if isinstance(m, dict)]
        models = [m for m in models if m]
        status = cfg.get("_status") or ""
        providers.append({
            "key": key,
            "name": name,
            "models": models,
            "image": cfg.get("image_model"),
            "video": cfg.get("video_model"),
            "status": status.strip(),
        })
    return providers


def _derive_agent_paths(agent_config: dict) -> dict:
    """Leite konkrete Pfade aus agent_config ab (mit sauberen Fallbacks)."""
    agent_name = agent_config.get("agent_name", "<agent>")
    parent = agent_config.get("parent_agent") or agent_name
    sub_label = agent_config.get("sub_label") or ""
    base = agent_config.get("datalake_base") or _DEFAULT_DATALAKE

    memory_dir = os.path.join(base, parent, "memory")
    working_memory = os.path.join(base, parent, "working_memory")
    if sub_label:
        working_memory = os.path.join(working_memory, f"_{sub_label}")
    contacts = os.path.join(memory_dir, "contacts.json")
    claude_outputs = agent_config.get("claude_outputs_path") or _DEFAULT_CLAUDE_OUTPUTS
    return {
        "memory_dir": memory_dir,
        "working_memory": working_memory,
        "contacts": contacts,
        "claude_outputs": claude_outputs,
        "is_subagent": bool(sub_label),
    }


def get_capabilities_block(agent_config: dict) -> str:
    """Generiert den vollstaendigen Capabilities-Block fuer einen Agent.

    agent_config (alle Felder optional):
      agent_name:         z.B. "privat", "signicat_lamp"
      parent_agent:       z.B. "signicat" (fuer Sub-Agents)
      sub_label:          z.B. "lamp" (fuer Sub-Agents)
      datalake_base:      Abweichender Datalake-Pfad (default iCloud)
      claude_outputs_path: Abweichender Output-Pfad
      models_config:      geladenes models.json Dict (fuer aktive Provider/Modelle)
    """
    agent_config = dict(agent_config or {})
    agent_name = agent_config.get("agent_name", "<agent>")
    paths = _derive_agent_paths(agent_config)
    providers = _active_providers(agent_config.get("models_config") or {})

    lines: list[str] = []
    lines.append(SEPARATOR)
    lines.append("")
    lines.append(
        "Dieser Block wird bei jedem Server-Start automatisch aktualisiert. "
        "Bearbeitungen oberhalb des Trennzeichens bleiben erhalten, alles "
        "unterhalb wird ueberschrieben."
    )
    lines.append("")

    # MEMORY & SUCHE
    lines.append("## MEMORY & SUCHE")
    lines.append(f"- Agent-Memory: `{paths['memory_dir']}`")
    if paths["is_subagent"]:
        lines.append(
            "  (Sub-Agents teilen sich das Memory des Parent-Agents.)"
        )
    lines.append(
        "- Inhalte im Memory: E-Mails (IN_/OUT_ im Dateinamen), Web Clips "
        "(web_ im Dateinamen), Dokumente (.docx/.xlsx/.pdf/.pptx), Konversationen "
        "(konversation_*.txt), Screenshots, Kontakte (contacts.json)."
    )
    lines.append(
        "- Kontakte: `" + paths["contacts"] + "` — Name, E-Mail, Firma, "
        "Haeufigkeit; wird vom Email Watcher gepflegt."
    )
    lines.append(
        "- Suche im Memory: das System triggert automatisch bei Such-Intent. "
        "Zusaetzlich kannst du explizit aufrufen:"
    )
    lines.append(
        "  MEMORY_SEARCH: {\"query\":\"<keywords>\", \"date_from\":\"YYYY-MM-DD\", "
        "\"date_to\":\"YYYY-MM-DD\", \"file_type\":\"email|webclip|doc\"}"
    )
    lines.append(
        "- Globale Suche ueber alle Agenten: Trigger-Phrasen wie \"suche ueberall\", "
        "\"erweitertes Gedaechtnis\", \"global search\" schalten den Cross-Agent-Modus "
        "ein (BM25 + Embeddings + RRF-Fusion)."
    )
    lines.append(
        "- Slash-Commands fuer Suche: `/find <begriff>` bzw. `\\find <begriff>` "
        "oeffnen einen Auswahl-Dialog mit Treffern aus dem Memory."
    )
    lines.append("")

    # KONVERSATIONEN
    lines.append("## KONVERSATIONEN")
    lines.append(
        "- Jede Konversation wird als `konversation_YYYY-MM-DD_HH-MM-SS_<agent>.txt` "
        "im Parent-Agent-Ordner gespeichert (Lazy-Create: erst beim ersten Prompt)."
    )
    lines.append(
        "- Format: Plaintext-Dialog mit Rollen-Markern. Ueber die History-Sidebar "
        "kann der Nutzer alte Konversationen fortsetzen."
    )
    lines.append("")

    # DATEI-ERSTELLUNG
    lines.append("## DATEI-ERSTELLUNG")
    lines.append(
        "Verwende diese Aktions-Tags im Antwort-Text. Das Backend erzeugt "
        f"die Datei automatisch in `{paths['claude_outputs']}` mit Namensschema "
        f"`{agent_name}_<beschreibung>_YYYY-MM-DD.<ext>`."
    )
    lines.append("- CREATE_FILE:docx  — Word-Dokument (.docx)")
    lines.append("- CREATE_FILE:xlsx  — Excel (.xlsx)")
    lines.append("- CREATE_FILE:pdf   — PDF")
    lines.append("- CREATE_FILE:pptx  — PowerPoint (.pptx)")
    lines.append(
        "- CREATE_EMAIL:{...}       — Apple-Mail Draft (neue E-Mail)"
    )
    lines.append(
        "- CREATE_EMAIL_REPLY:{...} — Apple-Mail Reply mit korrektem Threading "
        "(Feld `message_id` aus Original-E-Mail noetig)"
    )
    lines.append(
        "- CREATE_WHATSAPP:{\"to\":\"Vorname\",\"message\":\"...\"} — oeffnet "
        "WhatsApp mit vorgefuellter Nachricht (3-Stufen Kontakt-Lookup)."
    )
    lines.append(
        "- CREATE_SLACK:{\"channel\":\"#kanal\"|\"@user\",\"text\":\"...\"} — "
        "sendet via Slack-API, falls Bot-Token gesetzt ist."
    )
    lines.append("")

    # BILD & VIDEO
    lines.append("## BILD & VIDEO")
    image_providers = [p for p in providers if p["image"]]
    video_providers = [p for p in providers if p["video"]]
    if image_providers:
        img_summary = ", ".join(f"{p['name']} ({p['image']})" for p in image_providers)
        lines.append(f"- Bildgenerierung: `CREATE_IMAGE: <Prompt>` — aktiv: {img_summary}")
    else:
        lines.append("- Bildgenerierung: `CREATE_IMAGE: <Prompt>`")
    if video_providers:
        vid_summary = ", ".join(f"{p['name']} ({p['video']})" for p in video_providers)
        lines.append(f"- Videogenerierung: `CREATE_VIDEO: <Prompt>` — aktiv: {vid_summary}")
    else:
        lines.append("- Videogenerierung: `CREATE_VIDEO: <Prompt>` (Google Veo)")
    lines.append(
        "- Ausgabe: " + paths["claude_outputs"] + " (PNG/MP4). Du sagst NIEMALS "
        "\"ich kann keine Bilder/Videos erzeugen\" — bei Fehler Meldung zeigen "
        "und erneuten Versuch anbieten."
    )
    lines.append("")

    # KALENDER & TOOLS
    lines.append("## KALENDER & TOOLS")
    lines.append(
        "- Kalender: `/calendar-today`, `/calendar-week`, `/calendar-search <term>` "
        "(Fantastical/Apple Calendar via taeglichem Export)."
    )
    lines.append(
        "- Web-Suche: wird automatisch getriggert bei Fragen nach aktuellen "
        "Informationen (Anthropic-natives Web-Tool). Quellen-Links werden mitgeliefert."
    )
    lines.append(
        "- Canva: `/canva-search`, `/canva-create`, `/canva-templates`, "
        "`/canva-campaign`, `/canva-export` (OAuth2 mit Auto-Refresh)."
    )
    lines.append(
        "- Slack: lesen/senden via `/api/slack` bzw. CREATE_SLACK."
    )
    lines.append("")

    # AKTIVE MODELLE & PROVIDER
    lines.append("## AKTIVE MODELLE & PROVIDER")
    if providers:
        for p in providers:
            if not p["models"]:
                continue
            suffix = f"  [{p['status']}]" if p["status"] else ""
            models_str = ", ".join(p["models"])
            lines.append(f"- {p['name']}: {models_str}{suffix}")
    else:
        lines.append("- (models.json nicht geladen — Provider-Liste unbekannt)")
    lines.append("")

    # WORKING MEMORY
    lines.append("## WORKING MEMORY")
    lines.append(f"- Pfad: `{paths['working_memory']}` (mit `_manifest.json`).")
    lines.append(
        "- Selbst-gepflegt via: WORKING_MEMORY_ADD {\"filename\",\"content\","
        "\"priority\":1-10,\"description\"}, WORKING_MEMORY_REMOVE {\"filename\"}, "
        "WORKING_MEMORY_LIST {}."
    )
    lines.append(
        "- Persistiert ueber Sessions. Priority 10 = hoechste Prioritaet "
        "(wird als Letztes entfernt)."
    )
    lines.append("")

    # PFADE
    lines.append("## PFADE (WICHTIG)")
    lines.append(f"- Memory-Root: `{paths['memory_dir']}`")
    lines.append(f"- Working Memory: `{paths['working_memory']}`")
    lines.append(f"- Kontakte: `{paths['contacts']}`")
    lines.append(f"- Claude-Outputs: `{paths['claude_outputs']}`")
    lines.append("")

    # OUTPUT-KONVENTION
    lines.append("## OUTPUT-KONVENTION")
    lines.append(
        "Wenn deine Antwort einen isolierten, kopierbaren Output enthaelt "
        "(E-Mail, Skript, Dokument, Config, Prompt), dann wrap ihn in "
        "`<output>...</output>`. Das Frontend rendert den Block visuell "
        "hervorgehoben; der Kopier-Button kopiert NUR den Block-Inhalt. "
        "Pro Antwort maximal ein Block."
    )

    # Trailing newline fuer saubere Merges
    return "\n".join(lines).rstrip() + "\n"


# ─── Migration ──────────────────────────────────────────────────────────────

def migrate_agent_file(agent_path: str, capabilities_block: str) -> bool:
    """Aktualisiert die SYSTEM-Sektion einer Agent-Datei.

    - Fehlendes Trennzeichen: Block wird an den bestehenden Inhalt angehaengt.
    - Vorhandenes Trennzeichen: System-Sektion wird vollstaendig ersetzt.
    - Byte-identischer Output wird nicht neu geschrieben (idempotent).

    Returniert True wenn die Datei tatsaechlich geschrieben wurde.
    """
    if not os.path.isfile(agent_path):
        return False
    with open(agent_path, "r", encoding="utf-8", errors="replace") as f:
        original = f.read()

    user, _existing_system = split_agent_prompt(original)
    new_content = merge_sections(user, capabilities_block)

    if new_content == original:
        return False

    tmp = agent_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new_content)
    os.replace(tmp, agent_path)
    return True


# ─── Server-Startup-Hook ────────────────────────────────────────────────────

def _load_models_config(models_file: str) -> dict:
    if not models_file or not os.path.isfile(models_file):
        return {}
    try:
        with open(models_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _parent_of(agent_name: str, known_names: set[str]) -> tuple[str, str]:
    """Liefert (parent, sub_label). Sub-Agents erkenne ich daran, dass ihr
    Name mit "<parent>_" beginnt, wobei <parent> selbst ein bekannter Agent
    ist.
    """
    if "_" in agent_name:
        candidate_parent, _, sub = agent_name.partition("_")
        if candidate_parent in known_names and candidate_parent != agent_name:
            return candidate_parent, sub
    return agent_name, ""


def inject_capabilities_on_startup(
    agents_dir: str,
    models_file: str | None = None,
    datalake_base: str | None = None,
    claude_outputs_path: str | None = None,
    verbose: bool = True,
) -> int:
    """Iteriert ueber alle `*.txt` in agents_dir, aktualisiert die
    System-Sektion jeder Agent-Datei.

    Returniert die Anzahl tatsaechlich geschriebener Dateien.
    """
    if not agents_dir or not os.path.isdir(agents_dir):
        if verbose:
            print(f"[CAPABILITIES] Skip — Ordner nicht vorhanden: {agents_dir}")
        return 0

    models_config = _load_models_config(models_file) if models_file else {}

    # Agent-Dateien sammeln (ohne *.backup_* usw.)
    entries = []
    for fname in os.listdir(agents_dir):
        if not fname.endswith(".txt"):
            continue
        # Nur die "Haupt"-Dateien, keine Backups. Backups enthalten ".backup"
        # vor ".txt" nicht, sondern *nach* ".txt", also z.B. "privat.txt.backup_...".
        # Sie landen also ohnehin nicht hier. Zur Sicherheit trotzdem pruefen:
        if ".backup" in fname:
            continue
        entries.append(fname)

    known_names = {f[:-4] for f in entries}
    updated = 0
    scanned = 0
    for fname in sorted(entries):
        agent_name = fname[:-4]
        parent, sub = _parent_of(agent_name, known_names)
        agent_cfg = {
            "agent_name": agent_name,
            "parent_agent": parent,
            "sub_label": sub,
            "models_config": models_config,
        }
        if datalake_base:
            agent_cfg["datalake_base"] = datalake_base
        if claude_outputs_path:
            agent_cfg["claude_outputs_path"] = claude_outputs_path

        block = get_capabilities_block(agent_cfg)
        fpath = os.path.join(agents_dir, fname)
        try:
            changed = migrate_agent_file(fpath, block)
            scanned += 1
            if changed:
                updated += 1
        except Exception as e:
            if verbose:
                print(f"[CAPABILITIES] Fehler bei {fname}: {e}")

    if verbose:
        print(
            f"[CAPABILITIES] {updated}/{scanned} Agent-Datei(en) aktualisiert "
            f"(Verzeichnis: {agents_dir})"
        )
    return updated
