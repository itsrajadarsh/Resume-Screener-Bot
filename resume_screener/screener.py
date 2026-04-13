"""
screener.py — AI scoring engine using multiple AI providers.

Public API
───────────
    screen_resume(resume_text: str, job_description: str, config: dict) -> dict
        Calls the selected AI, parses JSON response, returns a structured dict.

    display_screening_result(result: dict) -> None
        Renders the result dict as rich tables, panels, badges, and a
        verdict banner.
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from typing import Any

import ai_provider
from rich.panel    import Panel
from rich.table    import Table
from rich.text     import Text
from rich.columns  import Columns
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich          import box

from utils import console, format_score_bar, score_style, error_msg, warning_msg, success_msg, divider


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

RESUME_LIMIT   = 6000   # characters sent to AI (keep cost low)
JD_LIMIT       = 3000

SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert technical recruiter and resume screening AI.
    Your job is to evaluate how well a candidate's resume matches a given job description.

    Respond with ONLY a valid JSON object — no markdown fences, no explanation, nothing else.
    The JSON must have exactly these keys:

    {
      "match_score": <integer 0-100>,
      "strengths": [<3-5 concise strings>],
      "weaknesses": [<3-5 concise strings>],
      "missing_keywords": [<up to 8 short keyword strings>],
      "suggestions": [<3-5 actionable improvement strings>],
      "verdict": "<exactly one of: Strong Match | Moderate Match | Weak Match>"
    }

    Scoring guide:
      70-100  → Strong Match   (ready to interview)
      40-69   → Moderate Match (worth considering with caveats)
      0-39    → Weak Match     (significant gaps)
""")

USER_TEMPLATE = textwrap.dedent("""\
    ## RESUME
    {resume_text}

    ## JOB DESCRIPTION
    {job_description}

    Evaluate the resume against the job description and return the JSON object.
""")


# ══════════════════════════════════════════════════════════════════════════════
# JSON parsing
# ══════════════════════════════════════════════════════════════════════════════

_REQUIRED_KEYS = {"match_score", "strengths", "weaknesses",
                  "missing_keywords", "suggestions", "verdict"}

_VALID_VERDICTS = {"Strong Match", "Moderate Match", "Weak Match"}


def _parse_response(raw: str) -> dict[str, Any]:
    """
    Parse the AI's raw text response into a validated Python dict.

    Handles common LLM quirks:
      • Strips accidental markdown code fences (```json … ```)
      • Falls back to regex extraction if outer JSON braces are missing
    """
    # Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    # Try to find the first {...} block if there is surrounding text
    if not cleaned.startswith("{"):
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            cleaned = m.group(0)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"AI returned invalid JSON.\n"
            f"Raw response:\n{raw}\n"
            f"Parse error: {exc}"
        ) from exc

    # ── Validate required keys ────────────────────────────────────────────────
    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"AI response is missing keys: {missing}")

    # ── Coerce and clamp types ────────────────────────────────────────────────
    data["match_score"] = max(0, min(100, int(data["match_score"])))

    for list_key in ("strengths", "weaknesses", "missing_keywords", "suggestions"):
        if not isinstance(data[list_key], list):
            data[list_key] = [str(data[list_key])]

    verdict = data.get("verdict", "").strip()
    if verdict not in _VALID_VERDICTS:
        # Normalise closest match
        vl = verdict.lower()
        if "strong" in vl:
            data["verdict"] = "Strong Match"
        elif "moderate" in vl or "medium" in vl:
            data["verdict"] = "Moderate Match"
        else:
            data["verdict"] = "Weak Match"

    return data


# ══════════════════════════════════════════════════════════════════════════════
# Rich display
# ══════════════════════════════════════════════════════════════════════════════

def _verdict_banner(verdict: str, score: int) -> None:
    """Print a large, colour-coded verdict banner."""
    if verdict == "Strong Match":
        color  = "bold green"
        icon   = "🟢"
        border = "green"
    elif verdict == "Moderate Match":
        color  = "bold yellow"
        icon   = "🟡"
        border = "yellow"
    else:
        color  = "bold red"
        icon   = "🔴"
        border = "red"

    text = Text(justify="center")
    text.append(f"\n  {icon}  {verdict}  {icon}\n", style=color)
    console.print(
        Panel(text, border_style=border, box=box.DOUBLE_EDGE, padding=(0, 6)),
        justify="center",
    )
    console.print()


def _score_section(score: int) -> None:
    """Display the match score with a progress bar."""
    style = score_style(float(score))

    title_text = Text()
    title_text.append("  Match Score  ", style="bold white")
    title_text.append(f"  {score} / 100  ", style=style)

    console.print(
        Panel(title_text, title="📊 Overall Score", border_style="cyan",
              box=box.ROUNDED, expand=False),
        justify="center",
    )
    console.print("  ", format_score_bar(float(score), width=44), "\n")


def _bullet_panel(items: list[str], title: str,
                  bullet_style: str, border_style: str) -> Panel:
    """Build a Panel containing a bulleted list."""
    body = Text()
    for item in items:
        body.append("  • ", style=bullet_style)
        body.append(item + "\n", style="white")
    return Panel(body, title=title, border_style=border_style,
                 box=box.ROUNDED, padding=(0, 1))


def _keywords_row(keywords: list[str]) -> None:
    """Display missing keywords as yellow badge-like inline spans."""
    if not keywords:
        return

    console.print("[bold yellow]  🏷  Missing Keywords[/bold yellow]")
    console.print()

    badge_texts = []
    for kw in keywords:
        t = Text()
        t.append(f"  {kw}  ", style="bold black on yellow")
        badge_texts.append(t)

    # Print badges in rows using Columns
    console.print(Columns(badge_texts, padding=(0, 1), equal=False))
    console.print()


def _suggestions_section(suggestions: list[str]) -> None:
    """Display suggestions as a numbered list inside a panel."""
    body = Text()
    for i, sug in enumerate(suggestions, 1):
        body.append(f"  {i}. ", style="bold cyan")
        body.append(sug + "\n", style="white")

    console.print(
        Panel(body, title="💡 Suggestions for Improvement",
              border_style="cyan", box=box.ROUNDED, padding=(0, 1))
    )
    console.print()


def display_screening_result(result: dict[str, Any]) -> None:
    """
    Render a screening result dict as beautiful Rich output.

    Layout:
      1. Verdict banner (colour-coded by verdict string)
      2. Match score + progress bar
      3. Strengths (green) | Weaknesses (red)  side-by-side
      4. Missing keywords as yellow badges
      5. Suggestions numbered list
    """
    console.print()
    divider()

    score    = result["match_score"]
    verdict  = result["verdict"]
    strengths   = result["strengths"]
    weaknesses  = result["weaknesses"]
    keywords    = result["missing_keywords"]
    suggestions = result["suggestions"]

    # 1 ── Verdict banner ──────────────────────────────────────────────────────
    _verdict_banner(verdict, score)

    # 2 ── Score + bar ─────────────────────────────────────────────────────────
    _score_section(score)

    # 3 ── Strengths / Weaknesses side-by-side ─────────────────────────────────
    str_panel  = _bullet_panel(strengths,  "✅  Strengths",  "bold green", "green")
    weak_panel = _bullet_panel(weaknesses, "❌  Weaknesses", "bold red",   "red")
    console.print(Columns([str_panel, weak_panel], equal=True, padding=(0, 1)))
    console.print()

    # 4 ── Missing keywords ────────────────────────────────────────────────────
    _keywords_row(keywords)

    # 5 ── Suggestions ─────────────────────────────────────────────────────────
    _suggestions_section(suggestions)

    divider()
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def screen_resume(resume_text: str, job_description: str, config: dict) -> dict[str, Any]:
    """
    Screen a resume against a job description using the configured AI.

    Args:
        resume_text:     Plain text extracted from the candidate's PDF.
        job_description: Raw text of the job description.
        config:          Dict containing the provider selection.

    Returns:
        A dict with keys: match_score, strengths, weaknesses,
        missing_keywords, suggestions, verdict.

    Raises:
        RuntimeError: If the API key is missing or API fails.
        ValueError:   If AI returns unparseable output.
    """
    if not resume_text.strip():
        warning_msg("Resume text is empty — results may be inaccurate.")
    if not job_description.strip():
        warning_msg("Job description is empty — results may be inaccurate.")

    # Trim before building prompt to stay within free-tier token limits
    resume_text      = resume_text[:3000]
    job_description  = job_description[:2000]

    # Build prompt
    prompt = f"{SYSTEM_PROMPT}\n\n" + USER_TEMPLATE.format(
        resume_text=resume_text[:RESUME_LIMIT],
        job_description=job_description[:JD_LIMIT],
    )

    provider_name = str(config.get("provider", "claude")).capitalize()

    # ── Call AI with a live spinner ───────────────────────────────────────
    raw_response: str = ""

    with Progress(
        SpinnerColumn(spinner_name="bouncingBar", style="cyan"),
        TextColumn("[cyan]{task.description}"),
        BarColumn(bar_width=None, style="cyan", complete_style="green"),
        transient=True,
        console=console,
        expand=True,
    ) as progress:
        task = progress.add_task(
            f"  Asking {provider_name} to analyse the resume…", total=None
        )
        try:
            raw_response = ai_provider.call_ai(prompt, config)
            progress.update(task, description=f"  Parsing {provider_name} response…")
        except RuntimeError as exc:
            progress.stop()
            error_msg(str(exc))
            raise

    # ── Parse ─────────────────────────────────────────────────────────────────
    try:
        result = _parse_response(raw_response)
    except ValueError as exc:
        error_msg(str(exc))
        raise

    success_msg(
        f"Analysis complete — score: [bold]{result['match_score']}[/bold]/100  |  "
        f"verdict: [bold]{result['verdict']}[/bold]"
    )
    return result
