"""
ai_provider.py — Unified AI wrapper for multiple providers.

Public API
───────────
    call_ai(prompt: str, config: dict) -> str
        Routes to the correct SDK based on config["provider"] and returns
        plain response text. Raises RuntimeError on any API failure.

Supported providers
───────────────────
    "claude"  →  Anthropic   (ANTHROPIC_API_KEY)   model: claude-3-5-sonnet-20241022
    "gemini"  →  Google      (GEMINI_API_KEY)       model: gemini-1.5-flash
    "groq"    →  Groq/LLaMA  (GROQ_API_KEY)         model: llama3-8b-8192
"""

from __future__ import annotations

import os
from typing import Any, Dict

# ── Model identifiers ─────────────────────────────────────────────────────────
_MODELS = {
    "claude": "claude-3-5-sonnet-20241022",
    "gemini": "gemini-2.0-flash-lite",
    "groq":   "llama-3.3-70b-versatile",
}

# ── Human-readable display names ──────────────────────────────────────────────
PROVIDER_NAMES = {
    "claude": "Anthropic Claude",
    "gemini": "Google Gemini",
    "groq":   "Groq / LLaMA",
}

# ── Required env vars ─────────────────────────────────────────────────────────
PROVIDER_ENV_KEYS = {
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq":   "GROQ_API_KEY",
}


def provider_display_name(provider: str) -> str:
    """Return the human-readable name for a provider slug."""
    return PROVIDER_NAMES.get(provider, provider.capitalize())


def get_model(provider: str) -> str:
    """Return the model string for a given provider slug."""
    return _MODELS.get(provider, "unknown")


def check_api_key(provider: str) -> bool:
    """Return True if the required API key env var is set for this provider."""
    env_key = PROVIDER_ENV_KEYS.get(provider, "")
    return bool(os.environ.get(env_key, "").strip())


def _get_api_key(provider: str) -> str:
    """Fetch the API key from env, raising RuntimeError if missing."""
    env_key = PROVIDER_ENV_KEYS.get(provider, "")
    key = os.environ.get(env_key, "").strip()
    if not key:
        raise RuntimeError(
            f"{env_key} is not set.\n"
            f"Fix it with:  export {env_key}='your-key-here'"
        )
    return key


# ══════════════════════════════════════════════════════════════════════════════
# Provider implementations
# ══════════════════════════════════════════════════════════════════════════════

def _call_claude(prompt: str) -> str:
    """Call Anthropic Claude and return response text."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    api_key = _get_api_key("claude")
    model   = _MODELS["claude"]

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model      = model,
            max_tokens = 1500,
            messages   = [{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    except anthropic.AuthenticationError:
        raise RuntimeError(
            "Claude: API key invalid or expired.\n"
            "Get a new key at https://console.anthropic.com/settings/keys"
        )
    except anthropic.RateLimitError:
        raise RuntimeError(
            "Claude: Rate limit reached. Wait 30–60 s and try again."
        )
    except anthropic.APIConnectionError:
        raise RuntimeError(
            "Claude: Cannot reach Anthropic API. Check your internet connection."
        )
    except anthropic.APITimeoutError:
        raise RuntimeError(
            "Claude: Request timed out — the prompt may be too long. Try again."
        )
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Claude: API error {e.status_code}: {e.message}")
    except Exception as e:
        raise RuntimeError(f"Claude: Unexpected error — {e}")


def _call_gemini(prompt: str) -> str:
    """Call Google Gemini and return response text."""
    try:
        from google import genai
    except ImportError:
        raise RuntimeError(
            "google-genai package not installed.\n"
            "Run: pip install google-genai"
        )

    import time

    api_key = _get_api_key("gemini")
    model   = _MODELS["gemini"]

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        raise RuntimeError(f"Gemini: Failed to create client — {e}")

    # ── Retry loop with exponential backoff for rate-limit errors ─────────────
    last_exc: Exception = RuntimeError("Gemini: unknown error")

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model    = model,
                contents = prompt,
            )
            return response.text.strip()

        except Exception as e:
            err_str = str(e)
            is_rate  = ("429" in err_str
                        or "quota" in err_str.lower()
                        or "rate"  in err_str.lower())

            if is_rate:
                wait = 15 * (attempt + 1)   # 15 s, 30 s, 45 s
                from rich.console import Console as _C
                _C().print(
                    f"[yellow]  ⏳  Gemini rate limit hit. "
                    f"Waiting {wait}s before retry {attempt + 1}/3…[/yellow]"
                )
                time.sleep(wait)
                last_exc = RuntimeError(
                    f"Gemini: Rate limit — retry {attempt + 1}/3 after {wait}s"
                )
                continue

            # Non-rate-limit error — categorise and raise immediately
            is_auth    = ("api_key" in err_str.lower()
                          or "credential" in err_str.lower()
                          or "permission" in err_str.lower()
                          or "401" in err_str or "403" in err_str)
            is_network = ("connect" in err_str.lower()
                          or "timeout" in err_str.lower())

            if is_auth:
                raise RuntimeError(
                    "Gemini: API key invalid or not authorised.\n"
                    "Get a key at https://aistudio.google.com/app/apikey"
                )
            elif is_network:
                raise RuntimeError(
                    "Gemini: Network error. Check your internet connection."
                )
            else:
                raise RuntimeError(f"Gemini: API error — {e}")

    raise RuntimeError(
        "Gemini: Rate limit exceeded after 3 retries (waited up to 45 s).\n"
        "💡 Tip: Gemini free tier is very limited for long prompts.\n"
        "   Try switching to Groq (Option 3) — it's free and faster."
    )



def _call_groq(prompt: str) -> str:
    """Call Groq (LLaMA) and return response text."""
    try:
        from groq import Groq, AuthenticationError, RateLimitError
    except ImportError:
        raise RuntimeError(
            "groq package not installed. Run: pip install groq"
        )

    api_key = _get_api_key("groq")
    model   = _MODELS["groq"]

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model      = model,
            messages   = [{"role": "user", "content": prompt}],
            max_tokens = 1500,
        )
        return response.choices[0].message.content.strip()

    except AuthenticationError:
        raise RuntimeError(
            "Groq: API key invalid.\n"
            "Get a key at https://console.groq.com/keys"
        )
    except RateLimitError:
        raise RuntimeError(
            "Groq: Rate limit reached. Wait a moment and try again."
        )
    except Exception as e:
        err = str(e).lower()
        if "connect" in err or "timeout" in err:
            raise RuntimeError(
                "Groq: Network error. Check your internet connection."
            )
        raise RuntimeError(f"Groq: Unexpected error — {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def call_ai(prompt: str, config: Dict[str, Any]) -> str:
    """
    Call the AI provider specified in config and return response text.

    Args:
        prompt: The complete prompt string to send to the model.
        config: Dict with key "provider" — one of "claude", "gemini", "groq".

    Returns:
        Plain text response string from the model.

    Raises:
        RuntimeError:  Any API-level failure (auth, rate limit, network, etc.)
        ValueError:    Unknown provider slug.
    """
    provider = config.get("provider", "claude")

    if provider == "claude":
        return _call_claude(prompt)
    elif provider == "gemini":
        return _call_gemini(prompt)
    elif provider == "groq":
        return _call_groq(prompt)
    else:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Choose one of: claude, gemini, groq"
        )
