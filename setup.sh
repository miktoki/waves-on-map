#!/bin/sh
pip install uv
#curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
# shellcheck disable=SC2016
uv run pa website create --domain miktoki.pythonanywhere.com --command '/home/miktoki/waves-on-map/.venv/bin/uvicorn --app-dir /home/miktoki/waves-on-map --uds ${DOMAIN_SOCKET} app_map:app'
# pa website create-autorenew-cert --domain YOURCUSTOMDOMAIN
# pa website reload --domain YOURUSERNAME.pythonanywhere.com

