import os
import json
import time
import logging
import math
import pytz
import boto3
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from botocore.exceptions import ClientError
from common import utils
from common.notifications import send_email_notification, create_simple_html_email
from aws_services.s3.uploads import upload_log_to_s3

# --- Setup ---
est_timezone = pytz.timezone('US/Eastern')
db_details = os.environ.get('db_details', 'prod_writer_db')
SCHEDULE_FILE = "/data/patching_v4/scheduled_patching.json"
os.makedirs('./logs', exist_ok=True)

log_date = datetime.now(est_timezone).strftime('%Y-%m-%d')
log_filename = f'./logs/backup_{log_date}.log'
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler(log_filename)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# --- Globals ---
instance_header = {}
instance_tracking = []
backup_ids = []
backup_time = []

SMTP_SERVER = "mailrelay.softeon.com"
SMTP_PORT = 25
SENDER_EMAIL = "Patching-Updates@softeon.com"
TO_EMAILS =["a80af5b5.softeon.com@in.teams.ms", "CloudOps@softeon.com"]
# --- Functions ---
def instances_result():
    sql = """SELECT INSTANCE_NAME, PLATFORM_TYPE, INSTANCE_ID, PRIVATE_IP, COST_CENTER, ACCOUNT, REGION
             FROM EC2_INSTANCE_INFO"""
    return utils.run_select_sql(db_details, sql)

def ec2_finder(ip_list, instance_data):
    instances = [i for i in instance_data if i[3] in ip_list]
    instance_ids = [i[2] for i in instances]
    accounts_sql = [i[5] for i in instances]
    profiles = {i[5] for i in instances}
    regions = [i[6] for i in instances]
    region = regions[0] if regions else None

    global instance_tracking
    instance_tracking = [
        [i[2], i[3], 'Pending', 'Pending', 'Pending', None, None, None, None, None, None, None, None, None, None, None, None]
        for i in instances
    ]
    return instances, instance_ids, accounts_sql, list(profiles), region

def load_accounts(file_path, accounts_sql):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        accounts = data.get("accounts", {})
        for acc_type in accounts_sql:
            if acc_type in accounts:
                return accounts[acc_type], acc_type
        logger.error("No valid account found.")
    except Exception as e:
        logger.error(f"Failed to load accounts: {e}")
    return None, None

def backup_instances(instance_ids, region, account_num, profile, ip_list, script_start_time, quarter_str):
    """Create backups for the given EC2 instances and log backup times."""
    global backup_ids
    insert_sql = []
    update_sql = []
    client = boto3.Session(profile_name=profile).client('backup', region_name=region)

    for ip in ip_list:
        for inst in instance_data:
            if inst[3] == ip:
                instance_id = inst[2]
                instance_header[instance_id] = ip
                logger.info(f'Creating backup for: {instance_id}')
                arn = f'arn:aws:ec2:{region}:{account_num}:instance/{instance_id}'
                response = client.start_backup_job(
                    BackupVaultName='Default',
                    ResourceArn=arn,
                    IamRoleArn=f'arn:aws:iam::{account_num}:role/service-role/AWSBackupDefaultServiceRole',
                    Lifecycle={'DeleteAfterDays': 15}
                )
                job_id = response['BackupJobId']
                create_time = response['CreationDate']
                est_time = create_time.astimezone(est_timezone).strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f'Backup Job ID: {job_id} started at {est_time}')
                backup_ids.append(job_id)
                insert_sql.append([profile, region, instance_id, ip, quarter_str, job_id])
                update_sql.append([script_start_time, create_time, instance_id, job_id])

    insert_stmt = '''INSERT INTO PATCHING_LOG (ACCOUNT, REGION, INSTANCE_ID, PRIVATE_IP, QUARTER_PATCHED, COMMAND_ID)
                     VALUES (%s, %s, %s, %s, %s, %s)'''
    update_stmt = '''UPDATE PATCHING_LOG 
                     SET SCRIPT_START_TIME=%s, BACKUP_START_TIME=%s
                     WHERE INSTANCE_ID=%s AND COMMAND_ID=%s'''

    utils.bulk_insert(db_details, insert_stmt, insert_sql)
    import traceback
    try:
        utils.bulk_insert(db_details, update_stmt, update_sql)
    except Exception as e:
        if 'duplicate key value' in str(e):
            logger.warning("Pending already exists in DB.")
        else:
            logger.error(f"Backup update failed: {str(e)}\n{traceback.format_exc()}")
            raise

def backup_status(backup_ids, region, instance_ids, profile):
    """Check and log the status of backups for the given EC2 instances."""
    completed_instance_ids = []
    backup_end_time = []
    client = boto3.Session(profile_name=profile).client('backup', region_name=region)
    start_time = datetime.now(est_timezone)

    while backup_ids:
        for job_id in backup_ids[:]:
            try:
                resp = client.describe_backup_job(BackupJobId=job_id)
                state = resp['State']
                if state == 'COMPLETED':
                    logger.info(f'Backup completed: {job_id}')
                    now = datetime.now(est_timezone)
                    for inst in instance_tracking:
                        if inst[0] in instance_ids:
                            backup_end_time.append([now, profile, region, inst[0]])
                            inst[2] = 'Completed'
                            inst[9] = now
                            completed_instance_ids.append(inst[0])
                            instance_ids.remove(inst[0])
                    backup_ids.remove(job_id)
                elif state in ['FAILED', 'ABORTED']:
                    logger.error(f'Backup failed: {job_id}')
                    backup_ids.remove(job_id)
            except Exception as e:
                logger.error(f"Error checking job {job_id}: {e}")
            time.sleep(5)

    if backup_end_time:
        update_stmt = '''UPDATE PATCHING_LOG SET BACKUP_END_TIME = %s
                         WHERE ACCOUNT = %s AND REGION = %s AND INSTANCE_ID = %s'''
        utils.bulk_insert(db_details, update_stmt, backup_end_time)

    total_time = datetime.now(est_timezone) - start_time
    logger.info(f'Backup total time: {total_time}')
    return completed_instance_ids

# --- Main ---
if __name__ == '__main__':
    TARGET_TAG = os.environ.get("PATCH_TAG")
    if not TARGET_TAG:
        print("PATCH_TAG not set.")
        exit(1)

    logger.info(f"Running backup for tag: {TARGET_TAG}")
    print(f"Running backup for tag: {TARGET_TAG}")

    current_year = datetime.now(est_timezone).year
    current_month = datetime.now(est_timezone).month
    quarter = math.ceil(current_month / 3)
    patching_quarter = f"Q{quarter}-{current_year}"

    script_start_time = datetime.now(est_timezone)
    instance_data = instances_result()

    with open(SCHEDULE_FILE, 'r') as f:
        schedules = json.load(f)

    if TARGET_TAG not in schedules:
        print(f"No schedule found for {TARGET_TAG}")
        exit(1)

    schedule = schedules[TARGET_TAG]
    ip_list = schedule.get("ips", [])
    if not ip_list:
        print(f"No IPs found for tag {TARGET_TAG}")
        exit(1)

    # Email: Backup started with HTML formatting
    subject = f"Backup Started - Tag: {TARGET_TAG}"
    
    # Create simple HTML email for backup start
    details = f"""Target Tag: {TARGET_TAG}
Start Time: {datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}
Instances: {len(ip_list)}"""
    
    recipients = ["CloudOps@softeon.com"]
    html_body = create_simple_html_email(
        title="Backup Process Started",
        details=details,
        status="Started",
        timestamp=datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
    )
    
    send_email_notification(subject, html_body, recipients, is_html=True)

    instances, instance_ids, accounts_sql, profiles, region = ec2_finder(ip_list, instance_data)
    if not instances:
        print("No matching instances.")
        exit(1)

    account_num, _ = load_accounts('./accounts.json', accounts_sql)
    if not account_num:
        print("No account found.")
        exit(1)

    profile = profiles[0] if profiles else None
    if not profile:
        print("No AWS profile found.")
        exit(1)

    backup_instances(instance_ids, region, account_num, profile, ip_list, script_start_time, patching_quarter)
    print("Backups initiated. Monitoring...")

    # Email: Backup completed with HTML formatting
    completed_instance_ids = backup_status(backup_ids, region, instance_ids, profile)
    subject = f"Backup Completed - Tag: {TARGET_TAG}"
    
    # Create simple HTML email for backup completion
    details = f"""Target Tag: {TARGET_TAG}
Completion Time: {datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}
Completed Backups: {len(completed_instance_ids)}"""
    
    recipients = ["CloudOps@softeon.com"]
    html_body = create_simple_html_email(
        title="Backup Process Completed",
        details=details,
        status="success" if completed_instance_ids else "warning",
        timestamp=datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
    )
    
    send_email_notification(subject, html_body, recipients, is_html=True)

    logger.info(f"Completed backups: {completed_instance_ids}")
    print("Backup process complete.")

    # At the end of the script, after all backup steps and notifications:
    s3_log_bucket = "q3-2025-aws-security-patching"  # Change to your log bucket name if needed
    s3_log_prefix = f"{TARGET_TAG}_Patch_Backup/{log_date}"
    upload_log_to_s3(log_filename, s3_log_bucket, s3_log_prefix)
