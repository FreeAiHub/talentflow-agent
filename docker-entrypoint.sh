#!/bin/sh
# Container entrypoint: migrate, then hand over to the command.
#
# Migrations run here rather than as a separate deploy step because a container
# that serves traffic against an unmigrated schema fails in confusing ways —
# missing-column errors at request time instead of a clear failure at boot.
#
# `alembic upgrade head` is idempotent, so restarting or scaling out is safe.
# With several replicas they may race, but Alembic takes a lock on the version
# table, so one wins and the others wait.
set -e

if [ -n "${TALENTFLOW_SKIP_MIGRATIONS:-}" ]; then
    echo "entrypoint: TALENTFLOW_SKIP_MIGRATIONS set, not migrating"
else
    echo "entrypoint: applying migrations"
    alembic upgrade head
fi

exec "$@"
