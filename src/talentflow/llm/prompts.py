"""Loading and rendering the prompt files in ``prompts/``.

Prompts live in the repository rather than inside the package so they can be
edited and reviewed as prose. That means the path has to be resolved rather
than imported, and a missing directory must fail with a useful message instead
of a bare ``FileNotFoundError``.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from talentflow.llm.errors import LlmError

#: Matches our placeholder convention only: ``{lower_snake_case}``. Deliberately
#: does not match JSON in the prompt examples, which always has a quote or a
#: space after the brace, so ``str.format`` is not usable here and is not used.
_PLACEHOLDER = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


class PromptNotFound(LlmError):
    """A prompt file is missing."""


def prompts_dir() -> Path:
    """Directory holding the prompt files.

    ``TALENTFLOW_PROMPTS_DIR`` wins; otherwise the repository's ``prompts/``
    directory, resolved from this file's location.
    """
    override = os.environ.get("TALENTFLOW_PROMPTS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    # src/talentflow/llm/prompts.py -> repository root
    return Path(__file__).resolve().parents[3] / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Read ``prompts/<name>.md``, caching the result."""
    path = prompts_dir() / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptNotFound(
            f"prompt {name!r} not found at {path}. "
            "Set TALENTFLOW_PROMPTS_DIR if the prompts live elsewhere."
        ) from exc


def render(template: str, /, **values: str) -> str:
    """Substitute ``{placeholders}`` in ``template``.

    Only the named placeholders are replaced; JSON braces in the surrounding
    prompt text are left alone.
    """

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"prompt expects a value for {{{key}}} but none was given")
        return values[key]

    return _PLACEHOLDER.sub(replace, template)


def render_prompt(name: str, /, **values: str) -> str:
    """Load and render a prompt in one step."""
    return render(load_prompt(name), **values)
