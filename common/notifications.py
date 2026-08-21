import difflib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from common.logger import logger
import pytz
from datetime import datetime


def send_email_notification(subject, body, recipients, is_html=False):
    """Send an email notification with the given subject and body to recipients."""
    smtp_server = 'mailrelay.softeon.com'  # or your SMTP server
    smtp_port = 25
    smtp_user = 'Patching-Updates@softeon.com'  # replace with your email
    sender = smtp_user
    
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject
    
    # Attach body as HTML or plain text
    if is_html:
        msg.attach(MIMEText(body, 'html'))
    else:
        msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.sendmail(sender, recipients, msg.as_string())
        server.quit()
        logger.info(f"Email sent successfully to {recipients}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def create_simple_html_email(title, status, details, timestamp):
    """Create a simple HTML email template."""
    # Determine status color
    if "started" in status.lower():
        status_color = "#2196F3"  # Blue
        status_bg = "#E3F2FD"
    elif "success" in status.lower() or "completed" in status.lower():
        status_color = "#4CAF50"  # Green
        status_bg = "#E8F5E8"
    elif "failed" in status.lower() or "error" in status.lower():
        status_color = "#F44336"  # Red
        status_bg = "#FFEBEE"
    else:
        status_color = "#FF9800"  # Orange
        status_bg = "#FFF3E0"
    
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background-color: {status_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 20px; }}
            .content {{ padding: 20px; }}
            .status-box {{ background-color: {status_bg}; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0; border-radius: 4px; }}
            .details {{ background-color: #f8f9fa; padding: 15px; border-radius: 4px; font-family: monospace; white-space: pre-line; }}
            .footer {{ background-color: #f8f9fa; padding: 15px 20px; border-radius: 0 0 8px 8px; font-size: 12px; color: #666; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
            </div>
            <div class="content">
                <div class="status-box">
                    <strong>Status:</strong> {status}
                </div>
                <div class="details">
{details}
                </div>
            </div>
            <div class="footer">
                <strong>Automated Patching System</strong> | {timestamp}<br>
                This is an automated notification from the patching system.
            </div>
        </div>
    </body>
    </html>
    """
    return html_template


def create_patching_report_html(title, summary_data, instance_data, timestamp):
    """Create an enhanced HTML patching report with better structure."""
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background-color: #FF9800; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 22px; }}
            .content {{ padding: 20px; }}
            .summary-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin: 20px 0; }}
            .summary-card {{ background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #FF9800; }}
            .summary-card h3 {{ margin: 0 0 10px 0; color: #FF9800; font-size: 16px; }}
            .summary-card .value {{ font-size: 24px; font-weight: bold; color: #333; }}
            .summary-card .label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
            .report-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .report-table th, .report-table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            .report-table th {{ background-color: #f8f9fa; font-weight: bold; color: #333; }}
            .report-table tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .status-success {{ color: #4CAF50; font-weight: bold; }}
            .status-failed {{ color: #F44336; font-weight: bold; }}
            /* .duration removed */
            .footer {{ background-color: #f8f9fa; padding: 15px 20px; border-radius: 0 0 8px 8px; font-size: 12px; color: #666; text-align: center; }}
            .section-title {{ color: #333; border-bottom: 2px solid #FF9800; padding-bottom: 5px; margin: 25px 0 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 {title}</h1>
            </div>
            <div class="content">
                <!-- Summary Cards -->
                <h2 class="section-title">Executive Summary</h2>
                <div class="summary-grid">
                    <div class="summary-card">
                        <div class="label">Total Instances</div>
                        <div class="value">{summary_data.get('total_instances', 0)}</div>
                        <h3>Instances Processed</h3>
                    </div>
                    <div class="summary-card">
                        <div class="label">Success Rate</div>
                        <div class="value">{summary_data.get('success_rate', 0)}%</div>
                        <h3>Success Rate</h3>
                    </div>
                    <div class="summary-card">
                        <div class="label">Total Time</div>
                        <div class="value">{summary_data.get('total_duration', 'N/A')}</div>
                        <h3>Patching Duration</h3>
                    </div>
                </div>
                
                <!-- Detailed Results Table -->
                <h2 class="section-title">Detailed Instance Results</h2>
                <table class="report-table">
                    <thead>
                        <tr>
                            <th>Instance ID</th>
                            <th>IP Address</th>
                            <th>Patch Status</th>
                            <th>Stop Time</th>
                            <th>Start Time</th>
                            <th>Health Check</th>
                            <th>Restarted</th>
                        </tr>
                    </thead>
                    <tbody>
                        {instance_data}
                    </tbody>
                </table>
            </div>
            <div class="footer">
                <strong>Automated Patching System</strong> | Generated at {timestamp}<br>
                For detailed logs, check CloudWatch or contact the DevOps team.
            </div>
        </div>
    </body>
    </html>
    """
    return html_template

def create_app_validation_diff_email(instance_id, validation_time, before_lines, after_lines):
    """Create an HTML email for app validation difference using difflib.HtmlDiff."""
    diff_html = difflib.HtmlDiff(wrapcolumn=80).make_table(
        before_lines, after_lines,
        fromdesc='Before', todesc='After',
        context=True, numlines=1  # Fewer context lines for compactness
    )
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='UTF-8'>
        <title>App Validation Difference Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
            .container {{ max-width: 900px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background: #1976d2; color: #fff; padding: 20px; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 22px; }}
            .summary {{ padding: 20px; }}
            .footer {{ background: #f8f9fa; padding: 15px 20px; border-radius: 0 0 8px 8px; font-size: 12px; color: #666; text-align: center; }}
            .diff-scroll {{ overflow-x: auto; max-width: 100%; }}
            table.diff {{ width: 100%; font-size: 11px; border-collapse: collapse; }}
            .diff_header {{ background: #e3e3e3; font-weight: bold; }}
            .diff_next {{ background: #f0f0f0; }}
            .diff_add {{ background: #e6ffe6; }}
            .diff_chg {{ background: #fffbe6; }}
            .diff_sub {{ background: #ffe6e6; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>App Validation Difference Report</h1>
            </div>
            <div class="summary">
                <strong>Instance ID:</strong> {instance_id}<br>
                <strong>Validation Time:</strong> {validation_time}<br>
                <strong>Compared:</strong> Before vs After Patching
            </div>
            <div class="diff-scroll">
                {diff_html}
            </div>
            <div class="footer">
                Automated Patching System | For details, contact DevOps.
            </div>
        </div>
    </body>
    </html>
    """
    return html_template
"""
Notification operations for the patching system.

This module contains email notification functionality for the patching system.
"""


def send_critical_alert(instance_id, error_message, tag):
    
    SMTP_SERVER = "mailrelay.softeon.com"
    SMTP_PORT = 25
    SENDER_EMAIL = "Patching-Updates@softeon.com"
    TO_EMAILS = ["kishlayk@softeon.com","CloudOps@softeon.com"]
    est_timezone = pytz.timezone('US/Eastern')
    timestamp = datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')

    msg = MIMEMultipart('alternative')
    msg["Subject"] = f"⚠️ [Patching Critical Alert] Script Failed - {tag}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(TO_EMAILS)

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
            .content {{ padding: 20px; }}
            .error-box {{ background-color: #FFEBEE; border-left: 4px solid #D32F2F; padding: 15px; margin: 15px 0; border-radius: 4px; font-family: monospace; font-size: 13px; word-break: break-all; line-height: 1.6; }}
            .info-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin: 20px 0; }}
            .info-card {{ background-color: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 3px solid #D32F2F; }}
            .info-card h4 {{ margin: 0 0 5px 0; color: #333; font-size: 13px; text-transform: uppercase; }}
            .info-card .value {{ font-size: 15px; font-weight: bold; color: #D32F2F; word-break: break-all; }}
            .footer {{ background-color: #f8f9fa; padding: 15px 20px; border-radius: 0 0 8px 8px; font-size: 12px; color: #666; text-align: center; }}
            .note {{ background-color: #FFEBEE; border-left: 4px solid #D32F2F; padding: 10px 15px; border-radius: 4px; font-size: 13px; margin-bottom: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚠️ Patching - Critical Error</h1>
            </div>
            <div class="content">
                <div class="note">
                    <strong>Alert:</strong> A critical error occurred and the patching process has stopped or skipped this instance.
                </div>

                <div class="info-grid">
                    <div class="info-card">
                        <h4>Client Tag</h4>
                        <div class="value">{tag}</div>
                    </div>
                    <div class="info-card">
                        <h4>Instance ID</h4>
                        <div class="value">{instance_id}</div>
                    </div>
                    <div class="info-card">
                        <h4>Detected At</h4>
                        <div class="value">{timestamp}</div>
                    </div>
                </div>

                <h3 style="color:#D32F2F;">Error Details</h3>
                <div class="error-box">{error_message}</div>

            </div>
            <div class="footer">
                <strong>Automated Patching System</strong> | {timestamp}<br>
                This alert was triggered automatically due to a critical error in the patching script.
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(SENDER_EMAIL, TO_EMAILS, msg.as_string())
        logger.info(f"Critical alert sent - tag: {tag}, instance: {instance_id}")
    except Exception as e:
        logger.error(f"Failed to send critical alert: {e}")