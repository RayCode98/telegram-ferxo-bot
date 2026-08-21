#!/bin/sh
set -eu
[ $# -eq 1 ] || { echo "Usage: $0 backup.sql.gz" >&2; exit 2; }
gunzip -c "$1" | psql -v ON_ERROR_STOP=1
