import sys
from unittest.mock import MagicMock
import textwrap

# Mock dependencies that are not present in the environment
sys.modules["fitz"] = MagicMock()
sys.modules["rich"] = MagicMock()
sys.modules["rich.console"] = MagicMock()
sys.modules["rich.text"] = MagicMock()
sys.modules["rich.panel"] = MagicMock()
sys.modules["rich.theme"] = MagicMock()
sys.modules["rich.box"] = MagicMock()

# Add the directory to sys.path so we can import the module
sys.path.append("resume_screener")

import parser

def test_extract_education_basic():
    text = textwrap.dedent("""
        EDUCATION
        University of Technology
        Bachelor of Science in Computer Science
        GPA: 3.9
    """).strip()
    result = parser._extract_education(text)
    assert "University of Technology" in result
    assert "Bachelor of Science in Computer Science" in result
    assert "GPA: 3.9" in result

def test_extract_education_case_insensitive():
    text = textwrap.dedent("""
        Education
        Stanford University
        Master of Arts
    """).strip()
    result = parser._extract_education(text)
    assert "Stanford University" in result
    assert "Master of Arts" in result

def test_extract_education_bullets():
    text = textwrap.dedent("""
        EDUCATION
        • MIT
        * Harvard
        - Oxford
    """).strip()
    result = parser._extract_education(text)
    assert "MIT" in result
    assert "Harvard" in result
    assert "Oxford" in result

def test_extract_education_limit():
    text = textwrap.dedent("""
        EDUCATION
        Line 1
        Line 2
        Line 3
        Line 4
        Line 5
        Line 6
        Line 7
    """).strip()
    result = parser._extract_education(text)
    assert len(result) == 6
    assert "Line 6" in result
    assert "Line 7" not in result

def test_extract_education_missing():
    text = textwrap.dedent("""
        SKILLS
        Python, Java
    """).strip()
    result = parser._extract_education(text)
    assert result == []

def test_extract_education_section_boundary():
    text = textwrap.dedent("""
        EDUCATION
        University A
        EXPERIENCE
        Software Engineer at Google
    """).strip()
    result = parser._extract_education(text)
    assert "University A" in result
    assert "Software Engineer at Google" not in result

def test_extract_education_noise_filtering():
    text = textwrap.dedent("""
        EDUCATION
        University of Alpha
        XY
        A
        Valid Degree
    """).strip()
    result = parser._extract_education(text)
    assert "University of Alpha" in result
    assert "Valid Degree" in result
    assert "XY" not in result
    assert "A" not in result
