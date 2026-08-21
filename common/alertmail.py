import sys
import time
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pytz

SMTP_SERVER = "mailrelay.softeon.com"
SMTP_PORT = 25
SENDER_EMAIL = "Patching-Updates@softeon.com"
TO_EMAILS = ["kishlayk@softeon.com","CloudOps@softeon.com"]

est_timezone = pytz.timezone('US/Eastern')
IDLE_TIMEOUT = 800

def send_alert_email(tag, error_line, log_file):
    msg = MIMEMultipart('alternative')
    msg["Subject"] = f"⚠️ [Patching Alert] Error Detected - {tag}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(TO_EMAILS)

    timestamp = datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='UTF-8'>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 700px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background-color: #FF9800; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 20px; }}
            .header .subtitle {{ margin: 6px 0 0 0; font-size: 13px; opacity: 0.9; }}
            .content {{ padding: 20px; }}
            .status-box {{ background-color: #FFF3E0; border-left: 4px solid #FF9800; padding: 12px 15px; margin-bottom: 20px; border-radius: 4px; font-size: 14px; }}
            .status-box strong {{ color: #E65100; }}
            .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }}
            .info-card {{ background-color: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 3px solid #FF9800; }}
            .info-card h4 {{ margin: 0 0 5px 0; color: #555; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
            .info-card .value {{ font-size: 15px; font-weight: bold; color: #E65100; word-break: break-all; }}
            .error-label {{ font-size: 14px; font-weight: bold; color: #333; margin: 20px 0 8px 0; }}
            .error-box {{ background-color: #FFF8E1; border-left: 4px solid #FFA000; padding: 15px; border-radius: 4px; font-family: monospace; font-size: 12px; word-break: break-all; line-height: 1.7; color: #333; }}
            .footer {{ background-color: #f8f9fa; padding: 15px 20px; border-radius: 0 0 8px 8px; font-size: 12px; color: #666; text-align: center; border-top: 1px solid #eee; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚠️ Patching Process Alert</h1>
                <div class="subtitle">An error was detected during the patching process</div>
            </div>
            <div class="content">
                <div class="status-box">
                    <strong>Status:</strong> IN PROGRESS &nbsp;|&nbsp; An error occurred but the process is continuing
                </div>

                <div class="info-grid">
                    <div class="info-card">
                        <h4>Client Tag</h4>
                        <div class="value">{tag}</div>
                    </div>
                    <div class="info-card">
                        <h4>Detected At</h4>
                        <div class="value">{timestamp}</div>
                    </div>
                </div>

                <div class="error-label">Error Details</div>
                <div class="error-box">{error_line}</div>

            </div>
            <div class="footer">
                <strong>Automated Patching Monitor</strong> | {timestamp}<br>
                This alert was triggered automatically when an error was detected in the patching log.
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(SENDER_EMAIL, TO_EMAILS, msg.as_string())
        print(f"Alert email sent for tag: {tag}")
    except Exception as e:
        print(f"Failed to send alert email: {e}")


def monitor_log(log_file, tag):
    waited = 0
    while not os.path.exists(log_file):
        time.sleep(5)
        waited += 5
        if waited > 120:
            print(f"Log file not found after 2 min: {log_file}")
            return

    print(f"Monitoring log file: {log_file}")

    with open(log_file, 'r') as f:
        f.seek(0, 2)
        last_activity_time = time.time()

        while True:
            line = f.readline()

            if line:
                line = line.strip()
                if not line:
                    continue

                last_activity_time = time.time()

                if ' - ERROR - ' in line:
                    print(f"ERROR detected, sending alert: {line}")
                    send_alert_email(tag, line, log_file)

            else:
                current_time = time.time()
                idle_time = current_time - last_activity_time

                if idle_time >= IDLE_TIMEOUT:
                    print(f"No log activity for {IDLE_TIMEOUT//60} minutes. Stopping monitor for {tag}")
                    return

                time.sleep(5)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 alertmail.py <log_file> <tag>")
        sys.exit(1)

    log_file = sys.argv[1]
    tag = sys.argv[2]
    monitor_log(log_file, tag)