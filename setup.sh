#!/bin/sh
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
cmd="/home/miktoki/waves-on-map/.venv/bin/uvicorn --app-dir /home/miktoki/waves-on-map --uds \"${DOMAIN_SOCKET}\" app_map:app"
pa website create --domain miktoki.pythonanywhere.com --command "$cmd"
# pa website create-autorenew-cert --domain YOURCUSTOMDOMAIN
# pa website reload --domain YOURUSERNAME.pythonanywhere.com