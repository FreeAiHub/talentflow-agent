#!/usr/bin/env bash
# Готовит изолированную рабочую копию под одного агента сетки.
#
# Зачем: два агента не должны писать в один каталог. Каждый исполнитель
# получает свой git worktree и свою ветку, поэтому его правки не мешают
# остальным, а проверяющему видно ровно то, что сделал один автор.
#
# Использование:
#   scripts/agent_worktree.sh <номер issue> <краткий-слаг>
#
# Пример:
#   scripts/agent_worktree.sh 40 parsers-save
#   → /Users/investing/GitHub/tf-wt-40, ветка fix/40-parsers-save
#
# Дальше: заполнить prompts/agents/08-repo-keeper.md, передать субагенту
# целиком, работать только в этой копии. Push и мерж делает координатор.

set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Использование: $0 <номер issue> <краткий-слаг>" >&2
    echo "Пример:        $0 40 parsers-save" >&2
    exit 2
fi

issue="$1"
slug="$2"

if ! [[ "$issue" =~ ^[0-9]+$ ]]; then
    echo "Номер issue должен быть числом, получено: $issue" >&2
    exit 2
fi

if ! [[ "$slug" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "Слаг пишется строчными латинскими буквами, цифрами и дефисом: $slug" >&2
    exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
base_branch="${BASE_BRANCH:-main}"
worktree_path="$(dirname "$repo_root")/tf-wt-$issue"
branch="fix/$issue-$slug"

if [ -e "$worktree_path" ]; then
    echo "Каталог уже существует: $worktree_path" >&2
    echo "Сначала убери его: git worktree remove $worktree_path" >&2
    exit 1
fi

if git -C "$repo_root" show-ref --verify --quiet "refs/heads/$branch"; then
    echo "Ветка уже существует: $branch" >&2
    exit 1
fi

# Ветка идёт от актуального origin, а не от локального состояния: иначе агент
# начнёт работу с устаревшего кода и его diff будет содержать чужие изменения.
git -C "$repo_root" fetch origin "$base_branch" --quiet
git -C "$repo_root" worktree add -b "$branch" "$worktree_path" "origin/$base_branch"

cat <<EOF

Готово.
  каталог: $worktree_path
  ветка:   $branch (от origin/$base_branch)
  задание: prompts/agents/08-repo-keeper.md

Что дальше:
  1. Заполнить шаблон задания: путь копии, номер issue, границы файлов, DoD.
  2. Передать субагенту целиком (он не видит чат координатора).
  3. После работы — проверить ветку и открыть PR. Мержит человек.

Проверка перед сдачей:
  git -C "$worktree_path" diff --stat "$base_branch"...HEAD
  git -C "$worktree_path" log --oneline "$base_branch"..HEAD
EOF
