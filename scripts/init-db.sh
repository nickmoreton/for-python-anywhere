#!/usr/bin/env bash
set -Eeuo pipefail

MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" mysql --host=localhost --protocol=socket --user=root <<SQL
GRANT ALL PRIVILEGES ON \`test_${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%';
SQL
