import os
from datetime import datetime
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from apscheduler.schedulers.blocking import BlockingScheduler

from wave_alert import CFG
from wave_alert import run as email_alert_on_wave


HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8080"))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz", "/ready"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    # Suppress default logging to stderr
    def log_message(self, format, *args):
        return


def start_health_server(port: int):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[health] Listening on 0.0.0.0:{port}")
    return server


# Define the task you want to run every day
def daily_task():
    """
    This is the function that will be executed daily.
    Replace this with your actual task logic.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Executing the daily task at: {timestamp}")
    email_alert_on_wave(limit=CFG.get("limit_locations"))


# Create an instance of the scheduler
scheduler = BlockingScheduler()

# Schedule the 'daily_task' to run every day at a specific time
# For example, at 16:00 UTC every day
scheduler.add_job(daily_task, "cron", hour=16, minute=0)


if __name__ == "__main__":
    # Start health endpoint first
    start_health_server(HEALTH_PORT)

    # Optional immediate run
    email_alert_on_wave(limit=CFG.get("limit_locations"))

    # Block with scheduler
    scheduler.start()
