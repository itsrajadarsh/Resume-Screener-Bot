"""
main.py — Entry point for the Resume Screener Bot.

Displays a welcome banner and runs a persistent menu loop so the user
can perform multiple tasks without restarting the program.

Session tracking
────────────────
A SessionStats object accumulates data across the session and prints
a summary panel when the user exits (or Ctrl-C).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List

from rich.prompt    import Prompt, Confirm
from rich.panel     import Panel
from rich.table     import Table
from rich.text      import Text
from rich.progress  import Progress, SpinnerColumn, TextColumn
from rich           import box

# ── local imports ──────────────────────────────────────────────────────────────
from utils        import (console, divider, section_header, success_msg,
                           info_msg, error_msg, warning_msg, timestamp,
                           get_job_description)
from ai_provider  import (check_api_key, provider_display_name,
                           PROVIDER_ENV_KEYS, PROVIDER_NAMES)
from parser       import parse_resume, ParsedResume
from screener     import screen_resume, display_screening_result
from cover_letter import interactive_cover_letter_flow


# ══════════════════════════════════════════════════════════════════════════════
# Session tracking
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SessionStats:
    """Accumulates metrics across the user's session."""

    started_at:       str        = field(default_factory=timestamp)
    provider:         str        = "(not selected)"
    resumes_screened: int        = 0
    match_scores:     List[int]  = field(default_factory=list)
    cover_letters:    int        = 0
    files_saved:      List[str]  = field(default_factory=list)

    @property
    def avg_score(self) -> float | None:
        return round(sum(self.match_scores) / len(self.match_scores), 1) if self.match_scores else None

    def record_screening(self, score: int) -> None:
        self.resumes_screened += 1
        self.match_scores.append(score)

    def record_cover_letter(self, saved_path: str | None = None) -> None:
        self.cover_letters += 1
        if saved_path:
            self.files_saved.append(saved_path)


# Global session object — handlers update it directly
_session = SessionStats()


def _show_session_summary() -> None:
    """Print an end-of-session summary table."""
    console.print()
    divider()

    table = Table(
        title       = "📊  Session Summary",
        box         = box.ROUNDED,
        border_style= "cyan",
        header_style= "heading",
        min_width   = 54,
        show_lines  = True,
    )
    table.add_column("Metric", style="primary",    no_wrap=True, min_width=26)
    table.add_column("Value",  style="bold white", justify="right")

    table.add_row("Session started",     _session.started_at)
    table.add_row("AI provider",         _session.provider)
    table.add_row("Resumes screened",    str(_session.resumes_screened))

    avg = _session.avg_score
    if avg is not None:
        avg_str = f"{avg}/100"
        style   = "score_high" if avg >= 70 else ("score_mid" if avg >= 40 else "score_low")
        table.add_row("Average match score", f"[{style}]{avg_str}[/]")
    else:
        table.add_row("Average match score", "[muted]—[/muted]")

    table.add_row("Cover letters generated", str(_session.cover_letters))
    table.add_row("Files saved",             str(len(_session.files_saved)))

    for i, path in enumerate(_session.files_saved, 1):
        table.add_row(f"  └─ File {i}", os.path.basename(path))

    console.print(table, justify="center")
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# Banner
# ══════════════════════════════════════════════════════════════════════════════

BANNER = r"""
 ██████╗ ███████╗███████╗██╗   ██╗███╗   ███╗███████╗
 ██╔══██╗██╔════╝██╔════╝██║   ██║████╗ ████║██╔════╝
 ██████╔╝█████╗  ███████╗██║   ██║██╔████╔██║█████╗  
 ██╔══██╗██╔══╝  ╚════██║██║   ██║██║╚██╔╝██║██╔══╝  
 ██║  ██║███████╗███████║╚██████╔╝██║ ╚═╝ ██║███████╗
 ╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝
  ███████╗ ██████╗██████╗ ███████╗███████╗███╗   ██╗███████╗██████╗ 
  ██╔════╝██╔════╝██╔══██╗██╔════╝██╔════╝████╗  ██║██╔════╝██╔══██╗
  ███████╗██║     ██████╔╝█████╗  █████╗  ██╔██╗ ██║█████╗  ██████╔╝
  ╚════██║██║     ██╔══██╗██╔══╝  ██╔══╝  ██║╚██╗██║██╔══╝  ██╔══██╗
  ███████║╚██████╗██║  ██║███████╗███████╗██║ ╚████║███████╗██║  ██║
  ╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝
                      ██████╗  ██████╗ ████████╗
                      ██╔══██╗██╔═══██╗╚══██╔══╝
                      ██████╔╝██║   ██║   ██║   
                      ██╔══██╗██║   ██║   ██║   
                      ██████╔╝╚██████╔╝   ██║   
                      ╚═════╝  ╚═════╝    ╚═╝   
"""


def show_banner() -> None:
    """Display the application welcome banner."""
    console.print(Text(BANNER, style="bold cyan"), justify="center")
    console.print(
        Panel(
            "[bold white]AI-Powered Resume Screening & Cover Letter Generation[/bold white]\n"
            "[muted]Match candidates · Craft cover letters[/muted]",
            border_style="cyan",
            box=box.DOUBLE_EDGE,
            padding=(0, 4),
        ),
        justify="center",
    )
    console.print(f"[muted]  Session started: {timestamp()}[/muted]\n")


# ══════════════════════════════════════════════════════════════════════════════
# AI Provider Selection
# ══════════════════════════════════════════════════════════════════════════════

# Ordered list of (slug, menu label) for the selection table
_PROVIDER_OPTIONS = [
    ("claude", "Anthropic Claude"),
    ("gemini", "Google Gemini      [muted](Free)[/muted]"),
    ("groq",   "Groq / LLaMA       [muted](Free)[/muted]"),
]


def select_provider() -> dict:
    """
    Show a provider selection table, verify the API key exists, and
    return a config dict like {'provider': 'gemini'}.

    Loops until a valid (key-present) provider is chosen or the user exits.
    """
    while True:
        console.print()
        table = Table(
            title       = "🤖  Select Your AI Provider",
            show_header = False,
            box         = box.ROUNDED,
            border_style= "cyan",
            padding     = (0, 2),
            min_width   = 44,
        )
        table.add_column("Key",      style="bold magenta", justify="center", no_wrap=True)
        table.add_column("Provider", style="bold white")

        for i, (slug, label) in enumerate(_PROVIDER_OPTIONS, 1):
            env_key  = PROVIDER_ENV_KEYS[slug]
            key_set  = check_api_key(slug)
            status   = "[bold green]✓[/bold green]" if key_set else "[red]✗[/red]"
            table.add_row(f"[{i}]", f"{label}  {status}")

        console.print(table, justify="center")
        console.print(
            "  [muted]✓ = API key found   ✗ = key missing[/muted]\n"
        )

        choice = Prompt.ask(
            "  [bold cyan]Choose a provider[/bold cyan]",
            choices=[str(i) for i in range(1, len(_PROVIDER_OPTIONS) + 1)],
            show_choices=False,
        ).strip()

        slug, _ = _PROVIDER_OPTIONS[int(choice) - 1]
        env_key = PROVIDER_ENV_KEYS[slug]

        if not check_api_key(slug):
            error_msg(
                f"{env_key} not found.  "
                f"Set it with:  [bold cyan]export {env_key}=your_key[/bold cyan]"
            )
            retry = Confirm.ask(
                "  [bold cyan]Choose a different provider?[/bold cyan]",
                default=True,
            )
            if retry:
                continue
            _exit_gracefully()

        name = provider_display_name(slug)
        success_msg(f"Using [bold]{name}[/bold] for this session.")
        console.print()
        return {"provider": slug}


# ══════════════════════════════════════════════════════════════════════════════
# Menu
# ══════════════════════════════════════════════════════════════════════════════

MENU_ITEMS = [
    ("1", "🔍  Screen Resume Against Job Description"),
    ("2", "✉️   Generate Cover Letter"),
    ("3", "🚪  Exit"),
]


def show_menu() -> None:
    """Render the main menu as a Rich table."""
    table = Table(
        show_header=False,
        box=box.ROUNDED,
        border_style="cyan",
        padding=(0, 2),
        min_width=54,
    )
    table.add_column("Key",    style="bold magenta", justify="center", no_wrap=True)
    table.add_column("Action", style="bold white")

    for key, label in MENU_ITEMS:
        table.add_row(f"[{key}]", label)

    console.print(table, justify="center")
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# Resume loading helper  (shared by both handlers)
# ══════════════════════════════════════════════════════════════════════════════

def _load_resume() -> ParsedResume | None:
    """
    Prompt the user for a PDF path, validate it, parse it, and show a summary.
    """
    divider()
    console.print("[primary]Step 1 — Load Resume PDF[/primary]\n")

    while True:
        pdf_path = Prompt.ask(
            "  [bold cyan]Enter path to resume PDF[/bold cyan]"
        ).strip()

        expanded = os.path.expanduser(pdf_path)

        # ── Does the file exist? ───────────────────────────────────────────────
        if not os.path.exists(expanded):
            error_msg(f"File not found: [bold]{expanded}[/bold]")
            console.print(
                "  [muted]Tip: drag the file into your terminal to auto-fill its path.[/muted]"
            )
            if not Confirm.ask("  Try a different path?", default=True):
                return None
            continue

        # ── Is it a PDF? ───────────────────────────────────────────────────────
        if not expanded.lower().endswith(".pdf"):
            error_msg(
                f"[bold]{os.path.basename(expanded)}[/bold] is not a PDF file.\n"
                "  Only [bold].pdf[/bold] files are supported."
            )
            if not Confirm.ask("  Try a different path?", default=True):
                return None
            continue

        break

    # ── Parse with spinner ─────────────────────────────────────────────────────
    console.print()
    resume: ParsedResume | None = None

    with Progress(
        SpinnerColumn(spinner_name="dots", style="cyan"),
        TextColumn("[cyan]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("Reading and parsing PDF…", total=None)
        resume = parse_resume(pdf_path)

    if resume is None or not resume.is_valid():
        console.print(
            Panel(
                "[white]The PDF could not be read. Common causes:[/white]\n\n"
                "  [bold]•[/bold] The file is a scanned image PDF (no text layer)\n"
                "  [bold]•[/bold] The PDF is password-protected\n"
                "  [bold]•[/bold] The file is corrupt or not a real PDF\n\n"
                "[muted]Try running the PDF through an OCR tool first (e.g. Adobe Acrobat, "
                "tesseract, or smallpdf.com).[/muted]",
                title="[bold red]⚠  Could Not Parse PDF[/bold red]",
                border_style="red",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        return None

    # ── Summary table ──────────────────────────────────────────────────────────
    console.print()
    table = Table(
        title="📄  Parsed Resume Summary",
        box=box.ROUNDED,
        header_style="heading",
        border_style="cyan",
        min_width=58,
        show_lines=True,
    )
    table.add_column("Field", style="primary",   no_wrap=True, min_width=14)
    table.add_column("Value", style="bold white", overflow="fold")

    for field_name, value in resume.summary_dict().items():
        table.add_row(field_name, value)

    console.print(table)
    console.print()
    return resume


# ══════════════════════════════════════════════════════════════════════════════
# Task handlers
# ══════════════════════════════════════════════════════════════════════════════

def handle_screen_resume(config: dict) -> None:
    """Flow: load resume → loop(get JD → screen → display → post-action menu)."""
    section_header("Screen Resume Against Job Description")

    resume = _load_resume()
    if resume is None:
        warning_msg("No resume loaded — returning to menu.")
        return

    # ── Inner loop — reuse the same resume until user says go back ────────────
    while True:
        jd = get_job_description()

        divider()
        console.print("[primary]Step 3 — AI Analysis[/primary]\n")

        try:
            result = screen_resume(resume.raw_text, jd, config)
        except (RuntimeError, ValueError):
            warning_msg("Screening could not complete.")
            result = None
        except Exception as exc:
            error_msg(f"Unexpected error: {exc}")
            result = None

        if result:
            display_screening_result(result)
            _session.record_screening(result["match_score"])
            success_msg(
                f"Session total: [bold]{_session.resumes_screened}[/bold] resume(s) screened  |  "
                f"avg score: [bold]{_session.avg_score}[/bold]/100"
            )

        # ── Post-screening action menu ────────────────────────────────────────
        console.print()
        action_table = Table(
            title       = f"📄  Resume loaded: [bold cyan]{resume.name or 'your resume'}[/bold cyan]",
            show_header = False,
            box         = box.ROUNDED,
            border_style= "cyan",
            padding     = (0, 2),
            min_width   = 52,
        )
        action_table.add_column("Key",    style="bold magenta", justify="center", no_wrap=True)
        action_table.add_column("Action", style="bold white")
        action_table.add_row("[1]", "🔄  Screen same resume against a new job description")
        action_table.add_row("[2]", "✉️   Generate cover letter for this resume")
        action_table.add_row("[3]", "🔙  Return to main menu")
        console.print(action_table, justify="center")
        console.print()

        next_action = Prompt.ask(
            "  [bold cyan]What would you like to do next?[/bold cyan]",
            choices=["1", "2", "3"],
            show_choices=False,
        ).strip()

        if next_action == "1":
            # Loop back — same resume, new JD
            section_header("Screen Resume Against Job Description")
            console.print(
                f"  [muted]Reusing resume: [bold]{resume.name or 'your resume'}[/bold][/muted]\n"
            )
            continue

        elif next_action == "2":
            # Hand off to cover letter flow with the already-loaded resume
            section_header("Generate Cover Letter")
            console.print(
                f"  [muted]Using resume: [bold]{resume.name or 'your resume'}[/bold][/muted]\n"
            )
            jd_for_letter = get_job_description()
            saved_path: list[str] = []

            def _on_saved(path: str) -> None:
                saved_path.append(path)
                _session.files_saved.append(path)

            interactive_cover_letter_flow(
                resume.raw_text, jd_for_letter, config, on_saved=_on_saved
            )
            _session.record_cover_letter(saved_path[0] if saved_path else None)
            break   # return to main menu after cover letter

        else:
            break   # return to main menu



def handle_generate_cover_letter(config: dict) -> None:
    """Flow: load resume → get JD → prefs → AI generation → save → track."""
    section_header("Generate Cover Letter")

    resume = _load_resume()
    if resume is None:
        warning_msg("No resume loaded — returning to menu.")
        return

    jd = get_job_description()

    # Pass a callback so cover_letter.py can report the saved path back to us
    saved_path: list[str] = []   # mutable container for the callback

    def _on_saved(path: str) -> None:
        saved_path.append(path)
        _session.files_saved.append(path)

    interactive_cover_letter_flow(resume.raw_text, jd, config, on_saved=_on_saved)

    # ── Track in session ───────────────────────────────────────────────────────
    _session.record_cover_letter(saved_path[0] if saved_path else None)


# ══════════════════════════════════════════════════════════════════════════════
# Main loop
# ══════════════════════════════════════════════════════════════════════════════

def _exit_gracefully() -> None:
    """Show session summary then goodbye banner, then exit."""
    _show_session_summary()
    console.print(
        Panel(
            "[bold cyan]Thank you for using Resume Screener Bot. Goodbye! 👋[/bold cyan]",
            border_style="cyan",
            box=box.DOUBLE_EDGE,
            padding=(0, 4),
        ),
        justify="center",
    )
    sys.exit(0)


def main() -> None:
    """Application entry point — shows banner, picks provider, runs menu."""
    try:
        show_banner()
        global_config = select_provider()
        _session.provider = provider_display_name(global_config["provider"])

        while True:
            show_menu()

            choice = Prompt.ask(
                "  [bold cyan]Select an option[/bold cyan]",
                choices=["1", "2", "3"],
                show_choices=False,
            ).strip()

            if choice == "1":
                handle_screen_resume(global_config)

            elif choice == "2":
                handle_generate_cover_letter(global_config)

            elif choice == "3":
                _exit_gracefully()

            else:
                error_msg("Invalid option. Please choose 1, 2, or 3.")

            # ── Pause before redisplaying the menu ────────────────────────────
            console.print()
            Confirm.ask("[muted]Press Enter to return to the main menu[/muted]", default=True)
            console.clear()
            show_banner()

    except KeyboardInterrupt:
        console.print()
        _exit_gracefully()


if __name__ == "__main__":
    main()
