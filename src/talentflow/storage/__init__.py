"""Persistence layer.

Import from here rather than from the submodules:

- :mod:`talentflow.storage.db` — engine and session handling
- :mod:`talentflow.storage.tables` — SQLAlchemy tables (internal)
- :mod:`talentflow.storage.repository` — queries returning domain models
"""

from talentflow.storage.db import (
    create_engine,
    create_sessionmaker,
    dispose_engine,
    get_engine,
    get_session,
    get_sessionmaker,
    to_async_url,
)
from talentflow.storage.repository import (
    count_vacancies,
    create_application,
    decide_application,
    finish_run,
    get_vacancy,
    list_vacancies,
    save_score,
    save_vacancies,
    start_run,
)

__all__ = [
    "count_vacancies",
    "create_application",
    "create_engine",
    "create_sessionmaker",
    "decide_application",
    "dispose_engine",
    "finish_run",
    "get_engine",
    "get_session",
    "get_sessionmaker",
    "get_vacancy",
    "list_vacancies",
    "save_score",
    "save_vacancies",
    "start_run",
    "to_async_url",
]
