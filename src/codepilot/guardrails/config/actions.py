"""NeMo Guardrails action implementations.

Pure Python regex checks — no additional LLM calls needed.
These are invoked by the Colang 2.0 flows in rails.co.
"""

from __future__ import annotations

import re
from typing import Any


def check_prompt_injection(user_input: str, **kwargs: Any) -> bool:
    """Check for prompt injection patterns in user input.

    Returns True if injection detected.
    """
    patterns = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+your\s+instructions",
        r"forget\s+your\s+training",
        r"you\s+are\s+now",
        r"new\s+instructions:",
        r"system\s+prompt\s+override",
        r"act\s+as\s+if",
        r"pretend\s+you\s+are",
    ]
    text = user_input.lower()
    return any(re.search(p, text) for p in patterns)


def check_hardcoded_secrets(bot_message: str, **kwargs: Any) -> bool:
    """Check for hardcoded secrets in generated output.

    Returns True if secrets detected.
    """
    patterns = [
        r"api_key\s*=",
        r"secret_key\s*=",
        r'password\s*=\s*"',
        r"BEGIN\s+RSA\s+PRIVATE\s+KEY",
        r"BEGIN\s+OPENSSH\s+PRIVATE\s+KEY",
        r"sk-[a-zA-Z0-9]{20,}",
        r"ghp_[a-zA-Z0-9]{36}",
    ]
    return any(re.search(p, bot_message) for p in patterns)


def check_unsafe_file_paths(bot_message: str, **kwargs: Any) -> bool:
    """Check for unsafe file path references in generated output.

    Returns True if unsafe paths detected.
    """
    patterns = [
        r"/etc/",
        r"/usr/",
        r"/bin/",
        r"/sbin/",
        r"/sys/",
        r"/proc/",
        r"/boot/",
        r"C:\\Windows",
        r"C:\\Program Files",
    ]
    return any(re.search(p, bot_message) for p in patterns)
