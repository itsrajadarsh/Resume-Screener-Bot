"""
parser.py — PDF resume parsing using PyMuPDF (fitz).

Public API
──────────
    extract_resume_text(pdf_path: str) -> str
        Extract all text from a PDF.  Raises descriptive exceptions on error.

    parse_resume(pdf_path: str) -> ParsedResume | None
        High-level wrapper used by main.py.  Returns a populated ParsedResume
        or None on failure.  Never raises.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

import fitz  # PyMuPDF

from utils import console, success_msg, warning_msg, error_msg


# ══════════════════════════════════════════════════════════════════════════════
# Custom exceptions
# ══════════════════════════════════════════════════════════════════════════════

class ResumeParseError(Exception):
    """Base class for all parser errors."""


class FileNotFoundError_(ResumeParseError):
    """Raised when the given path does not exist."""


class NotAPDFError(ResumeParseError):
    """Raised when the file does not have a .pdf extension."""


class EmptyPDFError(ResumeParseError):
    """Raised when the PDF yields no extractable text."""


# ══════════════════════════════════════════════════════════════════════════════
# Data model
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ParsedResume:
    """Structured representation of an extracted resume."""

    file_path:   str           = ""
    raw_text:    str           = ""
    page_count:  int           = 0
    word_count:  int           = 0

    # ── structured fields (populated by _extract_* helpers) ──────────────────
    name:        Optional[str] = None
    email:       Optional[str] = None
    phone:       Optional[str] = None
    skills:      List[str]     = field(default_factory=list)
    experience:  List[str]     = field(default_factory=list)
    education:   List[str]     = field(default_factory=list)

    def is_valid(self) -> bool:
        return bool(self.raw_text.strip())

    def summary_dict(self) -> dict:
        return {
            "File":       os.path.basename(self.file_path),
            "Pages":      str(self.page_count),
            "Words":      str(self.word_count),
            "Name":       self.name       or "—",
            "Email":      self.email      or "—",
            "Phone":      self.phone      or "—",
            "Skills":     ", ".join(self.skills)     or "—",
            "Experience": ", ".join(self.experience) or "—",
            "Education":  ", ".join(self.education)  or "—",
        }


# ══════════════════════════════════════════════════════════════════════════════
# Core extraction  (PyMuPDF)
# ══════════════════════════════════════════════════════════════════════════════

def extract_resume_text(pdf_path: str) -> str:
    """
    Extract all text from a PDF resume using PyMuPDF.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        A single string containing the cleaned text of every page.

    Raises:
        FileNotFoundError_: The path does not exist.
        NotAPDFError:        The file is not a PDF.
        EmptyPDFError:       The PDF contains no extractable text.
        ResumeParseError:    Any other PyMuPDF error.
    """
    # ── 1. Validate path ─────────────────────────────────────────────────────
    expanded = os.path.expanduser(pdf_path.strip())
    if not os.path.exists(expanded):
        raise FileNotFoundError_(f"File not found: {expanded!r}")

    if not expanded.lower().endswith(".pdf"):
        raise NotAPDFError(f"Expected a .pdf file, got: {os.path.basename(expanded)!r}")

    # ── 2. Open with fitz ────────────────────────────────────────────────────
    try:
        doc = fitz.open(expanded)
    except fitz.FileDataError as exc:
        raise ResumeParseError(f"Cannot open PDF (it may be corrupt): {exc}") from exc
    except Exception as exc:
        raise ResumeParseError(f"Unexpected error opening PDF: {exc}") from exc

    # ── 3. Extract text page-by-page ─────────────────────────────────────────
    pages_text: list[str] = []
    with doc:                       # ensures doc.close() even on error
        page_count = doc.page_count
        for page_num in range(page_count):
            try:
                page = doc[page_num]
                text = page.get_text("text")   # plain text, preserving layout
                pages_text.append(text)
            except Exception as exc:
                warning_msg(f"Could not read page {page_num + 1}: {exc}")

    # ── 4. Join and clean ────────────────────────────────────────────────────
    raw = "\n".join(pages_text)
    cleaned = _clean_text(raw)

    if not cleaned.strip():
        raise EmptyPDFError(
            "No extractable text found. The PDF may be image-based (scanned). "
            "Try running it through an OCR tool first."
        )

    return cleaned


def _clean_text(text: str) -> str:
    """
    Light-touch cleaning of raw PDF text.

    • Collapse 3+ consecutive blank lines into 2.
    • Strip trailing whitespace from every line.
    • Remove null bytes and other control characters.
    """
    # Remove control characters except newlines and tabs
    text = re.sub(r"[^\S\n\t ]+", " ", text)        # collapse weird whitespace
    text = re.sub(r"\x00", "", text)                  # null bytes
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)            # max 2 consecutive blanks
    return text.strip()


# ══════════════════════════════════════════════════════════════════════════════
# Structured field extractors  (regex heuristics)
# ══════════════════════════════════════════════════════════════════════════════

def _extract_name(text: str) -> Optional[str]:
    """First non-empty line is almost always the candidate's name."""
    for match in re.finditer(r"^.*$", text, re.MULTILINE):
        line = match.group()
        s = line.strip()
        if s and len(s.split()) >= 2:      # at least two words (First Last)
            return s
    return None


def _extract_email(text: str) -> Optional[str]:
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    m = re.search(pattern, text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> Optional[str]:
    pattern = r"(\+?\d[\d\s\-\(\)\.]{6,}\d)"
    m = re.search(pattern, text)
    return m.group(0).strip() if m else None


def _extract_section(text: str, heading: str) -> List[str]:
    """
    Extract bullet lines from a named section (e.g. SKILLS, EXPERIENCE).

    Looks for the heading and collects non-empty lines until the next
    all-caps heading or end-of-text.
    """
    # Match section heading (case-insensitive, possibly followed by : or newline)
    pattern = re.compile(
        rf"(?im)^{re.escape(heading)}[\s:]*\n(.*?)(?=\n[A-Z]{{3,}}|\Z)",
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return []
    block = m.group(1)
    lines = [
        re.sub(r"^[\•\-\*\u2022\u25cf\u2013]+\s*", "", ln).strip()
        for ln in block.splitlines()
        if ln.strip()
    ]
    return [ln for ln in lines if len(ln) > 2]   # drop noise


def _extract_skills(text: str) -> List[str]:
    """Extract skills — tries SKILLS section first, then comma-heuristic."""
    lines = _extract_section(text, "SKILLS")
    if lines:
        # Skills are often comma-separated on one or two lines
        combined = " ".join(lines)
        items = [s.strip() for s in re.split(r"[,|/]", combined) if s.strip()]
        return items[:20]   # cap at 20 so the table stays readable
    return []


def _extract_experience(text: str) -> List[str]:
    """Extract job titles / employers from the EXPERIENCE / WORK section."""
    lines = _extract_section(text, "EXPERIENCE")
    if not lines:
        lines = _extract_section(text, "WORK EXPERIENCE")
    if not lines:
        lines = _extract_section(text, "PROFESSIONAL EXPERIENCE")
    return lines[:10]


def _extract_education(text: str) -> List[str]:
    """Extract degree / institution strings from the EDUCATION section."""
    lines = _extract_section(text, "EDUCATION")
    return lines[:6]


# ══════════════════════════════════════════════════════════════════════════════
# High-level public wrapper
# ══════════════════════════════════════════════════════════════════════════════

def parse_resume(pdf_path: str) -> Optional[ParsedResume]:
    """
    Parse a PDF resume and return a populated :class:`ParsedResume`.

    This is the function called by main.py.  It handles all errors internally
    and prints friendly messages via Rich.  Returns None on failure.
    """
    # ── Extract raw text ─────────────────────────────────────────────────────
    try:
        raw_text = extract_resume_text(pdf_path)
    except FileNotFoundError_ as exc:
        error_msg(str(exc))
        return None
    except NotAPDFError as exc:
        error_msg(str(exc))
        return None
    except EmptyPDFError as exc:
        error_msg(str(exc))
        return None
    except ResumeParseError as exc:
        error_msg(f"Parse error: {exc}")
        return None

    # ── Count pages (re-open briefly for metadata) ───────────────────────────
    try:
        with fitz.open(os.path.expanduser(pdf_path.strip())) as doc:
            page_count = doc.page_count
    except Exception:
        page_count = 0

    # ── Build structured object ───────────────────────────────────────────────
    resume = ParsedResume(
        file_path  = os.path.abspath(os.path.expanduser(pdf_path.strip())),
        raw_text   = raw_text,
        page_count = page_count,
        word_count = len(raw_text.split()),
        name       = _extract_name(raw_text),
        email      = _extract_email(raw_text),
        phone      = _extract_phone(raw_text),
        skills     = _extract_skills(raw_text),
        experience = _extract_experience(raw_text),
        education  = _extract_education(raw_text),
    )

    success_msg(
        f"Parsed [bold]{os.path.basename(pdf_path)}[/bold] — "
        f"[cyan]{page_count}[/cyan] page{'s' if page_count != 1 else ''}, "
        f"[cyan]{resume.word_count}[/cyan] words extracted."
    )
    return resume
