#!/bin/sh
# PostgreSQL backup and restore.
#
#   ./scripts/backup.sh backup            # dump to ./backups
#   ./scripts/backup.sh restore <file>    # restore from a dump
#   ./scripts/backup.sh list              # show existing dumps
#
# A backup nobody has restored is not a backup, so `restore` exists and is
# exercised in docs/DEPLOY.md rather than left as an exercise for the reader.

set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups}"
POSTGRES_USER="${POSTGRES_USER:-talentflow}"
POSTGRES_DB="${POSTGRES_DB:-talentflow}"
# Keep a fortnight by default: long enough to notice a problem, short enough
# that the disk does not fill with dumps nobody will ever use.
RETENTION_DAYS="${RETENTION_DAYS:-14}"
COMPOSE_SERVICE="${COMPOSE_SERVICE:-db}"

timestamp() {
    date -u +%Y%m%dT%H%M%SZ
}

require_compose() {
    if ! docker compose version >/dev/null 2>&1; then
        echo "error: docker compose is not available" >&2
        exit 1
    fi
}

do_backup() {
    require_compose
    mkdir -p "$BACKUP_DIR"
    target="${BACKUP_DIR}/${POSTGRES_DB}_$(timestamp).sql.gz"

    echo "Backing up ${POSTGRES_DB} to ${target}"
    # --clean --if-exists makes the dump restorable over an existing database.
    docker compose exec -T "$COMPOSE_SERVICE" \
        pg_dump --clean --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB" \
        | gzip > "$target"

    # A dump that is a few bytes is an error message, not a backup.
    size=$(wc -c < "$target" | tr -d ' ')
    if [ "$size" -lt 1024 ]; then
        echo "error: dump is only ${size} bytes; treating as failed" >&2
        rm -f "$target"
        exit 1
    fi

    echo "Wrote ${target} (${size} bytes)"
    do_prune
}

do_restore() {
    require_compose
    source_file="${1:-}"
    if [ -z "$source_file" ] || [ ! -f "$source_file" ]; then
        echo "usage: $0 restore <dump file>" >&2
        exit 1
    fi

    echo "Restoring ${source_file} into ${POSTGRES_DB}"
    echo "This overwrites the current contents. Ctrl-C within 5 seconds to abort."
    sleep 5

    gunzip -c "$source_file" | docker compose exec -T "$COMPOSE_SERVICE" \
        psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"

    echo "Restore finished."
}

do_list() {
    if [ ! -d "$BACKUP_DIR" ]; then
        echo "No backups in ${BACKUP_DIR}"
        return
    fi
    ls -lh "$BACKUP_DIR" 2>/dev/null || echo "No backups in ${BACKUP_DIR}"
}

do_prune() {
    # Only delete files this script created, and only older than the window.
    find "$BACKUP_DIR" -name "${POSTGRES_DB}_*.sql.gz" -type f \
        -mtime "+${RETENTION_DAYS}" -print -delete 2>/dev/null \
        | sed 's/^/Pruned /' || true
}

case "${1:-}" in
    backup) do_backup ;;
    restore) shift; do_restore "$@" ;;
    list) do_list ;;
    *)
        echo "usage: $0 {backup|restore <file>|list}" >&2
        exit 2
        ;;
esac
