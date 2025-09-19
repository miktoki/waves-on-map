import os
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from wave_alert import CFG
from wave_alert import run as email_alert_on_wave


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
    email_alert_on_wave(limit=CFG.get("limit_locations"))
    scheduler.start()
