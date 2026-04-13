"""
cover_letter.py — AI cover letter generator using multiple AI providers.

Public API
───────────
    generate_cover_letter(
        resume_text: str,
        job_description: str,
        user_name: str,
        config: dict,
        tone: str,
        highlight: str,
    ) -> str
        Calls the selected AI and returns the cover letter as a plain string.

    interactive_cover_letter_flow(resume_text: str, job_description: str, config: dict) -> None
        Collects user preferences, generates, displays, and optionally saves
        the cover letter.  Called directly from main.py.
"""

from __future__ import annotations

import os
import textwrap
from datetime import datetime
from typing import Callable, Optional

import ai_provider
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text
from rich.prompt  import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich         import box

from utils import console, divider, section_header, success_msg, error_msg, warning_msg, info_msg


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

RESUME_LIMIT = 5000
JD_LIMIT     = 2500

TONES = {
    "1": ("Formal",          "professional, polished, and formal business language"),
    "2": ("Conversational",  "warm, natural, and personable while remaining professional"),
    "3": ("Enthusiastic",    "energetic, passionate, and excited — showing genuine enthusiasm for the role"),
}

SYSTEM_PROMPT = textwrap.dedent("""\
    You are an elite professional cover letter writer with 20+ years of experience
    helping candidates land roles at top companies.

    Your task is to write a tailored, compelling cover letter based on the provided
    resume and job description.

    Rules:
    - Write ONLY the cover letter body — no subject line, no email headers.
    - Start directly with "Dear Hiring Manager," (or similar appropriate salutation).
    - End with a professional sign-off followed by the applicant's name.
    - Keep it to exactly 3-4 paragraphs. Do NOT write more.
    - Reference specific, real details from the resume (job titles, technologies, achievements).
    - Mirror keywords from the job description naturally.
    - Do NOT use generic filler phrases like "I am writing to express my interest".
    - Do NOT use bullet points.
    - Output only the cover letter text — no extra commentary.
""")

USER_TEMPLATE = textwrap.dedent("""\
    ## APPLICANT NAME
    {user_name}

    ## TONE
    Write in a {tone_description} tone.

    ## HIGHLIGHT (something the applicant specifically wants to emphasise)
    {highlight}

    ## RESUME
    {resume_text}

    ## JOB DESCRIPTION
    {job_description}

    Write the cover letter now.
""")


# ══════════════════════════════════════════════════════════════════════════════
# Public generation function
# ══════════════════════════════════════════════════════════════════════════════

def generate_cover_letter(
    resume_text:     str,
    job_description: str,
    user_name:       str,
    config:          dict,
    tone:            str = "Formal",
    highlight:       str = "",
) -> str:
    """
    Generate a tailored cover letter using the configured AI.

    Args:
        resume_text:     Plain text from the parsed resume.
        job_description: Raw job description text.
        user_name:       Applicant's full name (used in sign-off).
        config:          Dict containing the provider selection.
        tone:            One of "Formal", "Conversational", "Enthusiastic".
        highlight:       Optional sentence the applicant wants emphasised.

    Returns:
        The generated cover letter as a plain string.

    Raises:
        RuntimeError: API key missing or API-level errors.
    """
    # Find tone description (default to Formal if unrecognised)
    tone_description = next(
        (desc for _, (label, desc) in TONES.items() if label == tone),
        TONES["1"][1],
    )

    highlight_text = highlight.strip() if highlight.strip() else "Nothing specific — write a balanced letter."

    # Trim before building prompt to stay within free-tier token limits
    resume_text      = resume_text[:3000]
    job_description  = job_description[:2000]

    user_msg = USER_TEMPLATE.format(
        user_name        = user_name,
        tone_description = tone_description,
        highlight        = highlight_text,
        resume_text      = resume_text[:RESUME_LIMIT],
        job_description  = job_description[:JD_LIMIT],
    )

    prompt = f"{SYSTEM_PROMPT}\n\n{user_msg}"

    letter = ai_provider.call_ai(prompt, config)
    return letter


# ══════════════════════════════════════════════════════════════════════════════
# Rich display helpers
# ══════════════════════════════════════════════════════════════════════════════

def _display_preferences_table(user_name: str, tone: str, highlight: str) -> None:
    """Show the user-selected options in a small summary table."""
    table = Table(
        show_header = False,
        box         = box.SIMPLE_HEAVY,
        border_style= "cyan",
        padding     = (0, 2),
        min_width   = 50,
    )
    table.add_column("Key",   style="bold cyan",  no_wrap=True, min_width=16)
    table.add_column("Value", style="bold white", overflow="fold")
    table.add_row("Name",      user_name)
    table.add_row("Tone",      tone)
    table.add_row("Highlight", highlight or "[muted](none)[/muted]")
    console.print(table)
    console.print()


def _display_cover_letter(letter: str, user_name: str, tone: str) -> None:
    """Render the finished cover letter inside a rich Panel."""
    word_count = len(letter.split())

    console.print(
        Panel(
            Text(letter, style="white"),
            title    = f"[bold magenta]✉  Cover Letter — {user_name}[/bold magenta]",
            subtitle = f"[muted]Tone: {tone}  ·  {word_count} words[/muted]",
            border_style = "magenta",
            box      = box.DOUBLE_EDGE,
            padding  = (1, 3),
        )
    )
    console.print()


def _save_cover_letter(
    letter: str,
    user_name: str,
    on_saved: Optional[Callable[[str], None]] = None,
) -> None:
    """Prompt the user to save the letter; write to cover_letter_<timestamp>.txt.

    Args:
        letter:    The cover letter text.
        user_name: Used to build the default filename.
        on_saved:  Optional callback invoked with the absolute save path on
                   success.  Used by main.py to track files in SessionStats.
    """
    save = Confirm.ask(
        "  [bold cyan]Save cover letter to a .txt file?[/bold cyan]",
        default=True,
    )
    if not save:
        info_msg("Cover letter not saved.")
        return

    # Build default filename
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = user_name.replace(" ", "_").lower()
    default_name = f"cover_letter_{safe_name}_{ts}.txt"

    filename = Prompt.ask(
        "  [bold cyan]Filename[/bold cyan]",
        default=default_name,
    ).strip() or default_name

    if not filename.endswith(".txt"):
        filename += ".txt"

    save_dir = Prompt.ask(
        "  [bold cyan]Save directory[/bold cyan]",
        default=os.path.expanduser("~"),
    ).strip()
    save_dir = os.path.expanduser(save_dir) if save_dir else os.path.expanduser("~")

    full_path = os.path.join(save_dir, filename)

    try:
        os.makedirs(save_dir, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as fh:
            fh.write(letter)
        success_msg(f"Cover letter saved → [bold]{full_path}[/bold]")
        if on_saved:
            on_saved(full_path)          # notify main.py for session tracking
    except OSError as exc:
        error_msg(f"Could not save file: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# User preference collection
# ══════════════════════════════════════════════════════════════════════════════

def _collect_preferences() -> tuple[str, str, str]:
    """
    Interactively ask the user for:
      1. Their full name
      2. Tone preference (1/2/3)
      3. Optional highlight sentence

    Returns (user_name, tone_label, highlight).
    """
    divider()
    console.print("[primary]Step 3 — Cover Letter Preferences[/primary]\n")

    # ── Name ──────────────────────────────────────────────────────────────────
    while True:
        user_name = Prompt.ask("  [bold cyan]Your full name[/bold cyan]").strip()
        if user_name:
            break
        error_msg("Name cannot be empty.")

    # ── Tone ──────────────────────────────────────────────────────────────────
    console.print()
    tone_table = Table(
        show_header  = False,
        box          = box.SIMPLE_HEAVY,
        border_style = "cyan",
        padding      = (0, 2),
        min_width    = 52,
    )
    tone_table.add_column("Key",  style="bold magenta", justify="center", no_wrap=True)
    tone_table.add_column("Tone", style="bold white")
    tone_table.add_column("Description", style="muted", overflow="fold")

    for key, (label, desc) in TONES.items():
        tone_table.add_row(f"[{key}]", label, desc)

    console.print(tone_table)
    console.print()

    tone_choice = Prompt.ask(
        "  [bold cyan]Choose a tone[/bold cyan]",
        choices=list(TONES.keys()),
        default="1",
        show_choices=False,
    ).strip()

    tone_label = TONES[tone_choice][0]
    console.print()

    # ── Highlight ─────────────────────────────────────────────────────────────
    highlight = Prompt.ask(
        "  [bold cyan]Anything specific to highlight?[/bold cyan]\n"
        "  [muted](e.g. 'my leadership experience', press Enter to skip)[/muted]\n  ",
        default="",
    ).strip()

    console.print()
    return user_name, tone_label, highlight


# ══════════════════════════════════════════════════════════════════════════════
# Main interactive flow  (called from main.py)
# ══════════════════════════════════════════════════════════════════════════════

def interactive_cover_letter_flow(
    resume_text:     str,
    job_description: str,
    config:          dict,
    on_saved:        Optional[Callable[[str], None]] = None,
) -> None:
    """
    High-level interactive cover letter generation flow.

    Steps:
      1. Collect user preferences (name, tone, highlight)
      2. Call AI with a spinner
      3. Display the letter in a Rich Panel
      4. Offer to save as .txt

    Args:
        resume_text:     Plain text from the parsed PDF resume.
        job_description: Raw job description string.
        config:          Dict containing the provider selection.
    """
    user_name, tone, highlight = _collect_preferences()

    # ── Confirm before calling API ────────────────────────────────────────────
    divider()
    console.print("[primary]Step 4 — Generating Cover Letter[/primary]\n")
    _display_preferences_table(user_name, tone, highlight)

    # ── Call AI with live spinner ─────────────────────────────────────────
    letter: str = ""
    provider_name = str(config.get("provider", "claude")).capitalize()

    with Progress(
        SpinnerColumn(spinner_name="bouncingBall", style="magenta"),
        TextColumn("[magenta]{task.description}"),
        transient = True,
        console   = console,
        expand    = True,
    ) as progress:
        progress.add_task(
            f"  Asking {provider_name} to write your cover letter…", total=None
        )
        try:
            letter = generate_cover_letter(
                resume_text     = resume_text,
                job_description = job_description,
                user_name       = user_name,
                tone            = tone,
                highlight       = highlight,
                config          = config,
            )
        except RuntimeError as exc:
            progress.stop()
            error_msg(str(exc))
            warning_msg("Cover letter could not be generated. Returning to menu.")
            return
        except Exception as exc:
            progress.stop()
            error_msg(f"Unexpected error: {exc}")
            return

    success_msg(
        f"Cover letter generated — [bold]{len(letter.split())}[/bold] words."
    )
    console.print()

    # ── Display ───────────────────────────────────────────────────────────────
    _display_cover_letter(letter, user_name, tone)

    # ── Save ──────────────────────────────────────────────────────────────────
    _save_cover_letter(letter, user_name, on_saved=on_saved)

