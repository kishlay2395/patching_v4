import json
import re
from datetime import datetime, timedelta
import pytz
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys

# ------------------ Configuration ------------------

SCHEDULE_FILE = "/data/patching_v4/scheduled_patching.json"
PYTHON_SCRIPT_PATH = f"{sys.executable} /data/patching_v4/patching_main.py"
LOG_PATH = "/data/patching_v4/patching_cron.log"

est_timezone = pytz.timezone('US/Eastern')

# Email settings (Softeon internal relay)
SMTP_SERVER = "mailrelay.softeon.com"
SMTP_PORT = 25
SENDER_EMAIL = "Patching-Updates@softeon.com"
TO_EMAILS = ["CloudOps@softeon.com"] 


def main():
    ip_list = []
    while True:
        user_input = input('Enter the instance IP addresses (comma or space separated), or q to quit: ')
        if user_input.lower() == 'q':
            break
        ips = re.findall(r'\d+\.\d+\.\d+\.\d+', user_input)
        ip_list.extend(ips)

    if not ip_list:
        print("No IP addresses entered. Exiting.")
        return

    print(f"IP addresses entered: {ip_list}")
    confirm = input("Proceed with these IPs? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Aborting.")
        return

    tag = input("Enter a tag for the client: ").strip()
    while not tag:
        tag = input("Tag cannot be empty. Enter a tag: ").strip()

    while True:
        patching_date = input("Enter the patching date (YYYY-MM-DD): ").strip()
        try:
            datetime.strptime(patching_date, "%Y-%m-%d")
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    while True:
        patching_window_start = input("Enter the patching window start time (HH:MM, 24h): ").strip()
        if re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', patching_window_start):
            break
        print("Invalid time format. Please use HH:MM (24-hour).")

    while True:
        environment = input("Enter environment (prod/uat): ").strip().lower()
        if environment in ("prod", "uat"):
           break
        print("Invalid input. Please enter 'prod' or 'uat'.")


    # Save in new tag-based JSON structure
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, 'r') as f:
            try:
                schedule = json.load(f)
            except Exception:
                schedule = {}
    else:
        schedule = {}

    schedule[tag] = {
        "patching_date": patching_date,
        "patching_window_start": patching_window_start,
        "ips": ip_list,
        "environment": environment
    }

    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedule, f, indent=2)

    print(f"Schedule saved to {SCHEDULE_FILE} under tag '{tag}'.")
    print(f"Patching window: {patching_window_start}, IPs: {ip_list}")

    patching_datetime = datetime.strptime(f"{patching_date} {patching_window_start}", "%Y-%m-%d %H:%M")
    # Make patching_datetime timezone-aware
    patching_datetime = est_timezone.localize(patching_datetime)
 
    # Calculate backup time: 4 hours before patching, or 5 minutes from now if less than 4 hours
    now = datetime.now(est_timezone)  # This is already timezone-aware
    backup_datetime = patching_datetime - timedelta(hours=4)
 
    # Now the comparison will work since both are timezone-aware
    if backup_datetime <= now or (patching_datetime - now).total_seconds() < 4 * 3600:
        backup_datetime = now + timedelta(minutes=5)
        print(f"Backup scheduled in 5 minutes due to time constraints.")
    else:
        print(f"Backup scheduled 4 hours before patching.")
    # Schedule backup job first
    add_cron_job(backup_datetime, tag, job_type="backup")
    # Schedule main patching job at exact time
    add_cron_job(patching_datetime, tag, job_type="patching")

# ------------------ Cron Setup ------------------

def add_cron_job(cron_time, tag, job_type="patching"):
    minute = cron_time.minute
    hour = cron_time.hour
    day = cron_time.day
    month = cron_time.month
    weekday = '*'

    cron_expr = f"{minute} {hour} {day} {month} {weekday}"

    if job_type == "backup":
        unique_tag = f"# backup_job_{tag}_{cron_time.strftime('%Y%m%d_%H%M')}"
        script_path = "/data/patching_v4/patching_backup.py"
        job_description = "Backup"
    else:
        unique_tag = f"# patching_job_{tag}_{cron_time.strftime('%Y%m%d_%H%M')}"
        script_path = "/data/patching_v4/patching_main.py"
        job_description = "Patching"

    # Updated command: cd to directory, then run with PATCH_TAG and always DELETE_AFTER_RUN=1
    cron_command = (
        f"cd /data/patching_v4/ && "
        f"PATCH_TAG={tag} DELETE_AFTER_RUN=1 {sys.executable} {script_path} ; "
        f"(crontab -l | grep -v \"{unique_tag}\" | crontab -)"
    )
    cron_line = f"{cron_expr} {cron_command} >> {LOG_PATH} 2>&1 {unique_tag}"

    result = subprocess.run(['crontab', '-l'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    current_cron = result.stdout if result.returncode == 0 else ""

    if unique_tag not in current_cron:
        new_cron = current_cron.strip() + '\n' + cron_line + '\n'
        subprocess.run(['crontab', '-'], input=new_cron, text=True)
        print(f"{job_description} cron job added for {cron_time.strftime('%Y-%m-%d %H:%M %Z')}.")

        # Log the cron job scheduling
        with open(LOG_PATH, "a") as logf:
            logf.write(
                f"{datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')} - {job_description} cron job scheduled for tag '{tag}' at {cron_time.strftime('%Y-%m-%d %H:%M %Z')}\n"
            )

        # Get IPs for email if it's a patching job
        schedule_ips = None
        if job_type == "patching":
            try:
                with open(SCHEDULE_FILE, 'r') as f:
                    schedule = json.load(f)
                    schedule_ips = schedule.get(tag, {}).get('ips', [])
            except Exception:
                pass
        
        # Email body and send
        body = (
            f"{job_description} job has been scheduled.\n\n"
            f"Cron Job Time: {cron_time.strftime('%Y-%m-%d %H:%M %Z')}\n"
            f"Tag: {tag}\n"
        )
        if schedule_ips:
            body += f"Target IPs: {', '.join(schedule_ips)}\n"
            
        send_email_notification(
            f"🔔 {job_description} Cron Job Scheduled", 
            body, 
            job_type=job_description, 
            tag=tag, 
            cron_time=cron_time, 
            ips=schedule_ips
        )
    else:
        print(f"{job_description} cron job already exists. Skipping duplicate.")


def create_scheduling_html_email(job_type, tag, cron_time, ips=None):
    """Create a professional HTML email for cron job scheduling."""
    
    # Determine colors based on job type
    if job_type.lower() == "backup":
        header_color = "#2196F3"  # Blue
        status_color = "#2196F3"
        status_bg = "#E3F2FD"
        icon = "💾"
    else:  # Patching
        header_color = "#FF9800"  # Orange
        status_color = "#FF9800"
        status_bg = "#FFF3E0"
        icon = "🔧"
    
    # Format IP list if provided
    ip_section = ""
    if ips:
        ip_list = "</li><li>".join(ips)
        ip_section = f"""
        <div class="details-section">
            <h3>Target Servers</h3>
            <ul class="ip-list">
                <li>{ip_list}</li>
            </ul>
        </div>
        """
    
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='UTF-8'>
        <title>{job_type} Job Scheduled</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background-color: {header_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 20px; }}
            .content {{ padding: 20px; }}
            .status-box {{ background-color: {status_bg}; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0; border-radius: 4px; }}
            .status-box h3 {{ margin: 0 0 5px 0; color: {status_color}; }}
            .details-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }}
            .detail-card {{ background-color: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 3px solid {status_color}; }}
            .detail-card h4 {{ margin: 0 0 5px 0; color: #333; font-size: 14px; text-transform: uppercase; }}
            .detail-card .value {{ font-size: 16px; font-weight: bold; color: {status_color}; }}
            .details-section {{ margin: 20px 0; }}
            .details-section h3 {{ color: #333; border-bottom: 2px solid {status_color}; padding-bottom: 5px; }}
            .ip-list {{ background-color: #f8f9fa; padding: 10px; border-radius: 4px; margin: 10px 0; }}
            .ip-list li {{ margin: 5px 0; font-family: monospace; color: #333; }}
            .footer {{ background-color: #f8f9fa; padding: 15px 20px; border-radius: 0 0 8px 8px; font-size: 12px; color: #666; text-align: center; }}
            .cron-info {{ background-color: #e8f5e9; padding: 10px; border-radius: 4px; font-family: monospace; color: #2e7d32; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{icon} {job_type} Job Scheduled Successfully</h1>
            </div>
            <div class="content">
                <!-- Status -->
                <div class="status-box">
                    <h3>Scheduling Status</h3>
                    <strong>Cron job has been successfully scheduled and is ready to execute</strong>
                </div>
                
                <!-- Job Details -->
                <div class="details-grid">
                    <div class="detail-card">
                        <h4>Job Type</h4>
                        <div class="value">{job_type}</div>
                    </div>
                    <div class="detail-card">
                        <h4>Client Tag</h4>
                        <div class="value">{tag}</div>
                    </div>
                    <div class="detail-card">
                        <h4>Scheduled Time</h4>
                        <div class="value">{cron_time.strftime('%Y-%m-%d')}</div>
                    </div>
                    <div class="detail-card">
                        <h4>Execution Time</h4>
                        <div class="value">{cron_time.strftime('%H:%M %Z')}</div>
                    </div>
                </div>
                
                {ip_section}
                
                <!-- Cron Information -->
                <div class="details-section">
                    <h3>Execution Details</h3>
                    <div class="cron-info">
                        The job will automatically execute at the scheduled time and remove itself from cron upon completion.
                    </div>
                </div>
            </div>
            <div class="footer">
                <strong>Automated Patching System</strong> | Scheduled at {datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}<br>
                This is an automated notification from the patching scheduling system.
            </div>
        </div>
    </body>
    </html>
    """
    return html_template

def send_email_notification(subject, body, job_type="Patching", tag="", cron_time=None, ips=None):
    """Send a professional HTML email notification."""
    msg = MIMEMultipart('alternative')
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(TO_EMAILS)
    
    # Create HTML version
    if cron_time:
        html_body = create_scheduling_html_email(job_type, tag, cron_time, ips)
        msg.attach(MIMEText(body, 'plain'))  # Plain text fallback
        msg.attach(MIMEText(html_body, 'html'))  # HTML version
    else:
        # Fallback to plain text for other notifications
        msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(SENDER_EMAIL, TO_EMAILS, msg.as_string())
        print("Email notification sent.")
    except Exception as e:
        print(f"Failed to send email: {e}")

# ------------------ Entry Point ------------------

if __name__ == '__main__':
    main()

