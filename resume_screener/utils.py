"""
utils.py — Helper functions: colors, formatting, shared Rich console.
"""

from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.theme import Theme
from rich import box
import datetime
import os

# ──────────────────────────────────────────────
# Shared console with a custom theme
# ──────────────────────────────────────────────
custom_theme = Theme(
    {
        "primary":   "bold cyan",
        "secondary": "bold magenta",
        "success":   "bold green",
        "warning":   "bold yellow",
        "danger":    "bold red",
        "info":      "dim white",
        "heading":   "bold white on dark_blue",
        "score_high":   "bold green",
        "score_mid":    "bold yellow",
        "score_low":    "bold red",
        "muted":     "grey62",
    }
)

console = Console(theme=custom_theme)


# ──────────────────────────────────────────────
# Formatting helpers
# ──────────────────────────────────────────────

def divider(style: str = "muted") -> None:
    """Print a full-width horizontal divider."""
    console.rule(style=style)


def section_header(title: str) -> None:
    """Print a styled section header panel."""
    console.print(
        Panel(f"[heading] {title} [/heading]", box=box.HEAVY_HEAD, border_style="cyan"),
        justify="center",
    )


def success_msg(message: str) -> None:
    console.print(f"[success]✔  {message}[/success]")


def warning_msg(message: str) -> None:
    console.print(f"[warning]⚡  {message}[/warning]")


def error_msg(message: str) -> None:
    console.print(f"[danger]✘  {message}[/danger]")


def info_msg(message: str) -> None:
    console.print(f"[info]ℹ  {message}[/info]")


def score_style(score: float) -> str:
    """Return a Rich style string based on the numeric score (0-100)."""
    if score >= 75:
        return "score_high"
    elif score >= 45:
        return "score_mid"
    return "score_low"


def format_score_bar(score: float, width: int = 40) -> Text:
    """
    Return a Rich Text object representing a filled progress bar.

    Args:
        score: Numeric value between 0 and 100.
        width: Total character width of the bar.
    """
    filled = int((score / 100) * width)
    empty  = width - filled
    style  = score_style(score)

    bar = Text()
    bar.append("█" * filled, style=style)
    bar.append("░" * empty,  style="muted")
    bar.append(f"  {score:.1f}%", style=style)
    return bar


def timestamp() -> str:
    """Return the current date-time as a neatly formatted string."""
    return datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")


def pluralize(count: int, word: str) -> str:
    """Simple singular/plural helper. e.g. pluralize(3, 'match') → '3 matches'."""
    suffix = "es" if word.endswith(("s", "sh", "ch", "x", "z")) else "s"
    return f"{count} {word}{'' if count == 1 else suffix}"


# ══════════════════════════════════════════════════════════════════════════════
# Job-description input  (used by main.py)
# ══════════════════════════════════════════════════════════════════════════════

_MIN_JD_CHARS = 50   # minimum characters for a valid job description
_PREVIEW_CHARS = 200 # characters shown in the preview panel


def _jd_from_paste() -> str:
    """
    Read a multi-line job description from stdin.

    The user types (or pastes) text and signals completion by entering
    the word END on its own line.
    """
    console.print(
        "  [info]Paste or type the job description below.\n"
        "  When done, type [bold white]END[/bold white] on its own line "
        "and press [bold white]Enter[/bold white].[/info]\n"
    )
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _jd_from_file() -> str:
    """
    Read a job description from a .txt file supplied by the user.

    Keeps prompting until a valid, readable .txt file is provided or
    the user chooses to go back.
    """
    from rich.prompt import Prompt, Confirm

    while True:
        path = Prompt.ask("  [bold cyan]Path to job description .txt file[/bold cyan]").strip()
        expanded = os.path.expanduser(path)

        if not os.path.exists(expanded):
            error_msg(f"File not found: [bold]{expanded}[/bold]")
            if not Confirm.ask("  Try a different path?", default=True):
                return ""
            continue

        if not expanded.lower().endswith(".txt"):
            error_msg("Only [bold].txt[/bold] files are supported for job descriptions.")
            if not Confirm.ask("  Try a different path?", default=True):
                return ""
            continue

        try:
            with open(expanded, encoding="utf-8", errors="replace") as fh:
                content = fh.read().strip()
            success_msg(f"Loaded [bold]{os.path.basename(expanded)}[/bold] "
                        f"({len(content.split())} words).")
            return content
        except OSError as exc:
            error_msg(f"Could not read file: {exc}")
            if not Confirm.ask("  Try a different path?", default=True):
                return ""


def _validate_jd(text: str) -> bool:
    """
    Return True when *text* meets the minimum length requirement.
    Prints a friendly error message on failure.
    """
    if not text:
        error_msg("Job description is empty.")
        return False
    if len(text) < _MIN_JD_CHARS:
        error_msg(
            f"Job description is too short "
            f"([bold]{len(text)}[/bold] chars). "
            f"Please provide at least [bold]{_MIN_JD_CHARS}[/bold] characters."
        )
        return False
    return True


def _show_jd_preview(text: str) -> None:
    """Display the first _PREVIEW_CHARS characters of the JD in a Rich Panel."""
    preview = text[:_PREVIEW_CHARS]
    if len(text) > _PREVIEW_CHARS:
        preview += " …"
    console.print(
        Panel(
            f"[white]{preview}[/white]",
            title="[bold cyan]📋  Job Description Preview[/bold cyan]",
            subtitle=f"[muted]{len(text):,} chars · {len(text.split()):,} words[/muted]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def get_job_description() -> str:
    """
    Interactively collect a job description from the user.

    The user chooses between two input modes:

      [1] Paste directly  — multi-line, terminated by typing END
      [2] Load from file  — path to a UTF-8 .txt file

    Validates that the result is at least ``_MIN_JD_CHARS`` characters long,
    then displays a preview panel.  Loops until valid input is received.

    Returns:
        The raw job-description string (guaranteed non-empty, ≥ 50 chars).
    """
    from rich.prompt import Prompt
    from rich.table  import Table

    divider()
    console.print("[primary]Step 2 — Job Description[/primary]\n")

    # ── Mode selection menu ───────────────────────────────────────────────────
    mode_table = Table(
        show_header=False,
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        padding=(0, 2),
        min_width=46,
    )
    mode_table.add_column("Key",  style="bold magenta", justify="center", no_wrap=True)
    mode_table.add_column("Mode", style="bold white")
    mode_table.add_row("[1]", "📋  Paste job description directly")
    mode_table.add_row("[2]", "📂  Load from a .txt file")
    console.print(mode_table)
    console.print()

    while True:
        mode = Prompt.ask(
            "  [bold cyan]Choose input mode[/bold cyan]",
            choices=["1", "2"],
            show_choices=False,
        ).strip()

        console.print()

        # ── Collect raw text ──────────────────────────────────────────────────
        if mode == "1":
            raw = _jd_from_paste()
        else:
            raw = _jd_from_file()

        # ── Validate ──────────────────────────────────────────────────────────
        if not _validate_jd(raw):
            retry = Prompt.ask(
                "  [bold cyan]Try again?[/bold cyan]",
                choices=["y", "n"],
                default="y",
            )
            if retry.lower() == "n":
                # Return whatever we have (even if short) — caller decides
                warning_msg("Proceeding with the job description as-is.")
                break
            console.print()
            # Re-show the mode menu for the retry
            console.print(mode_table)
            console.print()
            continue

        # ── Preview ───────────────────────────────────────────────────────────
        console.print()
        _show_jd_preview(raw)
        console.print()
        success_msg(
            f"Job description ready — "
            f"[cyan]{len(raw.split())}[/cyan] words, "
            f"[cyan]{len(raw):,}[/cyan] characters."
        )
        return raw

    return raw
