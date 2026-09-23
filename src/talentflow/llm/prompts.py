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


def candidate_prompt_dirs() -> list[Path]:
    """Everywhere the prompt files might live, most specific first.

    The loader used to assume a source checkout, which is true in development
    and false inside a container: there the package sits in site-packages, so
    the path relative to this file points somewhere that does not exist. The
    search covers both layouts, and the explicit environment variable wins.
    """
    here = Path(__file__).resolve()
    candidates: list[Path] = []

    override = os.environ.get("TALENTFLOW_PROMPTS_DIR")
    if override:
        candidates.append(Path(override).expanduser())

    candidates.extend(
        [
            # Development checkout: src/talentflow/llm/prompts.py -> repo root
            here.parents[3] / "prompts",
            # Shipped as package data next to the package
            here.parents[1] / "prompts",
            # Container layout, and the working directory as a last resort
            Path("/app/prompts"),
            Path.cwd() / "prompts",
        ]
    )
    return candidates


def prompts_dir() -> Path:
    """Where the prompt files are.

    An explicit ``TALENTFLOW_PROMPTS_DIR`` wins unconditionally, even if it does
    not exist: it is a decision, and silently ignoring a typo in it would mean
    loading different prompts than the operator asked for. Without an override
    the first candidate that exists wins, so a source checkout and a container
    both work with no configuration.
    """
    override = os.environ.get("TALENTFLOW_PROMPTS_DIR")
    if override:
        return Path(override).expanduser()

    for candidate in candidate_prompt_dirs():
        if candidate.is_dir():
            return candidate
    return candidate_prompt_dirs()[0]


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Read ``prompts/<name>.md``, caching the result."""
    path = prompts_dir() / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        tried = "\n  ".join(str(c) for c in candidate_prompt_dirs())
        raise PromptNotFound(
            f"prompt {name!r} not found at {path}.\nSearched:\n  {tried}\n"
            "Set TALENTFLOW_PROMPTS_DIR to the directory holding the prompt files."
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
