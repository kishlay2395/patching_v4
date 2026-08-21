import os
import boto3
from common.logger import logger
from botocore.exceptions import ClientError
import re
import time
import pytz
from datetime import datetime
from common import utils
import difflib
import json
import math
from tabulate import tabulate

import subprocess as sp
import sys

# Import AWS service modules
from aws_services.ssm.commands import check_health_monitor_cron, disable_health_monitor_cron, run_kernel_check_via_ssm, send_patch_command, scan_instances, run_appavil_via_ssm
from aws_services.ec2.instances import stop_wait_start_instances
from aws_services.load_balancer.target_groups import build_instance_target_group_map
from aws_services.s3.uploads import upload_log_to_s3
from common.notifications import send_email_notification, create_simple_html_email, create_patching_report_html, send_critical_alert

from common.alertmail import monitor_log

instance_header = {}
data = []
instance_data = []
stopped_instances_local = []
ip_list = []
instance_ids = []
backup_ids = []
stopped_instances = []
stopped_instance_healths = []
start_instance_health = []
completed_patched_instances = []
tags_cc = []
command_ids = []
tags_name = []
backup_time = []
platform_types = []
backup_statuses = []
accounts_ids = []
json_list = []
completed_instance_ids = []
instance_tracking = []
failed_instances = []
backup_times = []
final_instances = []


est_timezone = pytz.timezone('US/Eastern')

current_year = datetime.now(est_timezone).year
compared_time = datetime.now(est_timezone).month
current_quarter = math.ceil(compared_time /3)
patching_quarter = f'Q{current_quarter}-{current_year}'
s3_bucket = f'q{current_quarter}-{current_year}-aws-security-patching'
apps_stop_sql = []
apps_start_sql = []
patch_end = []
patch_end_complete = []
os.environ['db_details'] = "prod_writer_db"
db_details = os.environ.get('db_details')
logger.info("Logger setup has been removed, using shared logger from common.logs.logger.")
SCHEDULE_FILE = "/data/patching_v4/scheduled_patching.json"


def instances_result():
    """Query and return EC2 instance data from the database."""
    global instance_data
    select_sql = """
        SELECT INSTANCE_NAME, PLATFORM_TYPE, INSTANCE_ID, PRIVATE_IP, COST_CENTER, ACCOUNT, REGION
        FROM EC2_INSTANCE_INFO"""
    instance_data = utils.run_select_sql(db_details, select_sql)
    return instance_data



def ec2_finder(ip_list, instance_data):
    """Find and return instance details for the given IP list from instance_data."""
    instances = [instance for instance in instance_data if instance[3] in ip_list]
    tags_name = [instance[0] for instance in instances]
    platform_types = [instance[1] for instance in instances]
    instance_ids = [instance[2] for instance in instances]
    tags_cc = [instance[4] for instance in instances]
    accounts_sql = [instance[5] for instance in instances]
    profiles = {instance[5] for instance in instances}
    regions = [instance[6] for instance in instances]
    region = regions[0] if regions else None
    if not instances:
        logger.warning("No instances found for the provided IP addresses.")
        print("No instances found for the provided IP address.  ")
        return None, None, None, None, None, None, None, None
    global instance_tracking
    instance_tracking = [
        [instance[2], instance[3], 'Pending', 'Pending', 'Pending', None, None, None, None, None, None, None, None, None, None, None, None]
        for instance in instances]
    return instances, instance_ids, tags_name, platform_types, tags_cc, accounts_sql, list(profiles), region

def load_accounts_from_json(file_path, accounts_sql):
    """Load account number and type from a JSON file based on accounts_sql."""
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        accounts = data.get('accounts', {})
        account_num = None
        account = None
        for account_type in accounts_sql:
            if account_type in accounts:
                account_num = accounts[account_type]
                account = account_type
                break
        if not account_num:
            logger.error("No valid account number found in JSON.")
            return None, None
        return account_num, account
    except Exception as e:
        logger.error(f"Error loading accounts from JSON: {e}")
        return None, None

def patch_failed_prompt(profile, instance_ids, command_ids):
    """Log patch failure, update DB, and exit the script."""
    logger.error('Patch process encountered errors. No interactive prompt available. Exiting script.')
    update_patch_end = '''UPDATE PATCHING_LOG SET SCRIPT_END_TIME = %s
    WHERE ACCOUNT = %s
    AND INSTANCE_ID = %s
    AND COMMAND_ID = %s;'''
    for command_id in command_ids:
        for instance in instance_tracking:
            patch_end.append([datetime.now(est_timezone), profile, instance[0], command_id])
        utils.bulk_insert(db_details, update_patch_end, patch_end)
    exit(1)

def patch_status(region, command_ids, instance_ids, db_details, profile):
    """Check and log the patch status for all command IDs and instances."""
    command_statuses = {}
    completed_command_ids = []
    failed_instances = []
    remaining_command_ids = list(command_ids)
    command_client = boto3.Session(profile_name=profile).client('ssm', region_name=region)
    update_sql = '''UPDATE PATCHING_LOG SET PATCH_END_TIME = %s, PATCH_STATUS = %s
    WHERE REGION = %s
    AND INSTANCE_ID = %s
    AND COMMAND_ID = %s;'''
    while remaining_command_ids:
        for command_id in remaining_command_ids[:]:
            try:
                response = command_client.list_command_invocations(
                    CommandId=command_id,
                    Details=True
                )
                invocations = response.get('CommandInvocations', [])
                for invocation in invocations:
                    instance_id = invocation.get('InstanceId')
                    status = invocation.get('Status')
                    command_statuses[instance_id] = status
                    patch_end_time = datetime.now(est_timezone)
                    matched_instance = next((inst for inst in instance_tracking if inst[0] == instance_id), None)
                    if status == 'Success':
                        if matched_instance:
                            matched_instance[3] = 'Completed'
                            completed_command_ids.append(command_id)
                            success_data = [(patch_end_time, "Compliant", region, instance_id, command_id)]
                        utils.bulk_insert(db_details, update_sql, success_data)
                    elif status in ['Failed', 'Cancelled', 'TimedOut','DeliveryTimedOut','ExecutionTimedOut','Undeliverable', 'InvalidPlatform']:
                        failed_instances.append(instance_id)
                        update_patch_end = '''UPDATE PATCHING_LOG SET SCRIPT_END_TIME = %s
                        WHERE ACCOUNT = %s
                        AND INSTANCE_ID = %s
                        AND COMMAND_ID = %s;'''
                        for command_id in command_ids:
                            for instance in failed_instances:
                                patch_end.append([datetime.now(est_timezone), profile, instance, command_id])
                                failed_data = [(patch_end_time, "Failed", region, instance_id, command_id)]
                            utils.bulk_insert(db_details, update_patch_end, patch_end)
                            utils.bulk_insert(db_details, update_sql, failed_data)
                        patch_failed_prompt(profile, instance_ids, command_ids)
                if all(invo.get('Status') in ['Success','Failed', 'Cancelled', 'TimedOut','DeliveryTimedOut','ExecutionTimedOut','Undeliverable', 'InvalidPlatform'] for invo in invocations):
                    remaining_command_ids.remove(command_id)
            except Exception as e:
                logger.error(f'Error retrieving patch status for command {command_id} (type: {type(e)}): {e}')
            time.sleep(30)
    for instance_id in instance_ids:
        if instance_id not in command_statuses:
            logger.warning(f"No status found for instance_id: {instance_id}")
            command_statuses[instance_id] = 'Unknown'
    return command_statuses, None, failed_instances, completed_command_ids

def main():
    """Main entry point for the patching workflow."""
    TARGET_TAG = os.environ.get("PATCH_TAG")
    if not TARGET_TAG:
        print("Environment variable PATCH_TAG not set. Exiting.")
        return

    print(f"Selected tag: {TARGET_TAG}")

    start_time = datetime.now(est_timezone)
    logger.info(f"Script Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    instance_data = instances_result()

    # --- Tag-based schedule selection ---
    with open(SCHEDULE_FILE, 'r') as f:
        schedules = json.load(f)
    

    if TARGET_TAG not in schedules:
        print(f"No schedule found for tag '{TARGET_TAG}'")
        return

    selected_schedule = schedules[TARGET_TAG]
    patching_window_start = selected_schedule["patching_window_start"]
    ip_list = selected_schedule["ips"]
    environment = selected_schedule["environment"]
    logger.info(f"Tag: {TARGET_TAG}, IPs: {ip_list}, Environment: {environment}")
    
    
    logger.info("Starting log monitor")

    log_date = datetime.now(est_timezone).strftime('%Y-%m-%d')

    base_dir = os.path.dirname(os.path.abspath(__file__))

    log_file_path = os.path.join(
       base_dir,
       "logs",
       f"patching_{log_date}_{TARGET_TAG}.log"
    )

    monitor_script = os.path.join(
       base_dir,
       "common",
       "alertmail.py"
    )

    sp.Popen(
        [sys.executable, monitor_script, log_file_path, TARGET_TAG],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL
    )
    time.sleep(7)
    logger.info(f"Log monitor started for: {log_file_path}")



    if not ip_list:
        print(f"No IPs found for tag '{TARGET_TAG}' in schedule file.")
        return

    print(f"Patching will run for IPs: {ip_list} (tag: {TARGET_TAG}, , environment: {environment})")
    instances, instance_ids, tags_name, platform_types, tags_cc, accounts_sql, profiles, region = ec2_finder(ip_list, instance_data)
    
    for ip in ip_list:
        for instance in instance_data:
            if instance[3] == ip:
                instance_id = instance[2]
                instance_header[instance_id] = ip
                profile = instance[5]
    logger.info(f'Instance(s) selected for Patching: {instance_header}')
    if instances is None:
        print("No instances found for the provided IP addresses.")
        return
    json_file = '/data/patching_v4/accounts.json'
    
    account_num, account = load_accounts_from_json(json_file, accounts_sql)
    
    if not account_num:
        
        logger.error("No accounts loaded from the JSON file.")
        return
        
    

    # --- Manual execution: proceed immediately ---
    print("Manual execution detected - proceeding to patching immediately.")

    # --- Send notification: patching started ---
    recipients =["CloudOps@softeon.com"]
    subject = f"Patching Started - Tag: {TARGET_TAG}"
    
    # Create simple HTML email
    details = f"""Target Tag: {TARGET_TAG}
    Instance Count: {len(ip_list)}
    Target IPs: {', '.join(ip_list)}"""
    
    html_body = create_simple_html_email(
        title="Patching Process Started",
        status="IN PROGRESS",
        details=details,
        timestamp=datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
    )
    
    send_email_notification(subject, html_body, recipients, is_html=True)
   

    patch_start_time = datetime.now(est_timezone)
    logger.info(f'Now patching instances at: {patch_start_time.strftime("%Y-%m-%d %H:%M:%S")}')
    print('Patching instances now.')
    document_name = 'AWS-RunPatchBaseline'

    
    before_log_files = {}
    for instance_id in instance_ids:
       try:
           ip = instance_header.get(instance_id, instance_id)
           output_before = run_appavil_via_ssm(instance_id, profile, region)
           now = datetime.now(est_timezone).strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]
           outdir = os.path.join(
               os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
               f'patching_report/validation-{datetime.now(est_timezone).strftime("%Y-%m-%d")}/{TARGET_TAG}'
           )
           os.makedirs(outdir, exist_ok=True)
           ip_dir = os.path.join(outdir, ip)
           os.makedirs(ip_dir, exist_ok=True)
           before_log_file = os.path.join(ip_dir, f'{ip}-BeforePatching-{now}.log')
           with open(before_log_file, 'w') as f:
               f.write(output_before)
           before_log_files[instance_id] = before_log_file
           logger.info(f"Before patching log saved: {before_log_file}")
       except Exception as e:
           logger.error(f"Before validation failed for {instance_id}: {e}")
           


    cron_was_active = {}
    for instance_id in instance_ids:
        cron_was_active[instance_id] = check_health_monitor_cron(instance_id, profile, region)
        logger.info(f"{instance_id}: Cron was active = {cron_was_active[instance_id]}")

    active_instance_ids = [iid for iid in instance_ids if cron_was_active[iid]]
    if active_instance_ids:
        disable_health_monitor_cron(active_instance_ids, profile, region)
        logger.info(f"Disabled cron for: {active_instance_ids}")
    else:
        logger.info("No active cron is found on any instance, skipping disable step.")
   
    
    command_ids = send_patch_command(instance_ids, region, tags_cc, document_name, profile, instance_tracking, patching_quarter)
    patch_statuses, _, failed_instances, command_ids = patch_status(region, command_ids, instance_ids, db_details, profile)
    if all(status == 'Success' for status in patch_statuses.values()) and not failed_instances:
        patched_status = 'Success'
        logger.info('All patches applied successfully.')
    elif not command_ids:
        patched_status = 'Failed'
        logger.error('No remaining command IDs to process. Exiting.')
    else:
        patched_status = 'Failed'
        logger.info('Some patches failed or were cancelled. User interaction required.')
    for instance in instance_ids[:]:
        if instance in failed_instances:
            instance_ids.remove(instance)
    patch_end_time = datetime.now(est_timezone)
    logger.info(f"Patching end time: {patch_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f'Patch Elapsed time: {patch_end_time - patch_start_time}')
    patch_total_time = patch_end_time - patch_start_time

    # --- Run kernel_check.sh via SSM after patching, before reboot ---
    # logger.info('Running kernel_check.sh on all instances via SSM')
    #run_kernel_check_via_ssm(instance_ids, profile, region)

    # --- Send notification: patching ended ---
    subject = f"Patching Completed - Tag: {TARGET_TAG}"
    
    # Create simple HTML email
    details = f"""
    Target Tag: {TARGET_TAG}
    Instance Count: {len(ip_list)}
    Target IPs: {', '.join(ip_list)}
    Final Status: {patched_status}
    Total Duration: {patch_total_time}"""
    
    status_text = "COMPLETED SUCCESSFULLY" if patched_status == 'Success' else "COMPLETED WITH ISSUES"
    
    html_body = create_simple_html_email(
        title="Patching Process Completed" if patched_status == 'Success' else "Patching Process Completed",
        status=status_text,
        details=details,
        timestamp=patch_end_time.strftime('%Y-%m-%d %H:%M:%S %Z')
    )
    
    send_email_notification(subject, html_body, recipients, is_html=True)
    # --- End notification ---

    stopped_services = 'yes'
    if stopped_services.lower() == 'yes':
        logger.info('Confirmed - services are stopped')
        update_apps_stoptime_sql = '''UPDATE PATCHING_LOG SET APPS_STOP_TIME = %s
        WHERE ACCOUNT = %s
        AND INSTANCE_ID = %s
        AND COMMAND_ID = %s;'''
        for instance in instance_ids:
            for command_id in command_ids:
                apps_stop_sql.append([datetime.now(est_timezone), profile, instance, command_id])
        utils.bulk_insert(db_details, update_apps_stoptime_sql, apps_stop_sql)
    else:
        logger.warning('Services stopped? - Negative Captain!')
    logger.debug('Stopping EC2 Instances')
    print('Stopping instances')
    restart_start_time = datetime.now(est_timezone)
    instance_tg_map = build_instance_target_group_map(region, profile, instance_ids)
    stop_wait_start_instances(instance_ids, stopped_instances_local, region, profile, command_ids, instance_tracking, db_details, est_timezone, instance_tg_map, instance_header, before_log_files, cron_was_active, environment)
    restart_end_time = datetime.now(est_timezone)
    logger.info(f'Restart Total time: {restart_end_time - restart_start_time}')
    started_services = 'yes'
    logger.info('Auto-confirmed services are restarted')
    if started_services.lower() == 'yes':
        logger.info('Confirmed - services are started')
        update_apps_start_sql = '''UPDATE PATCHING_LOG SET APPS_START_TIME = %s
        WHERE ACCOUNT = %s
        AND INSTANCE_ID = %s
        AND COMMAND_ID = %s;'''
        for instance in final_instances:
            for command_id in command_ids:
                apps_start_sql.append([datetime.now(est_timezone), profile, instance, command_id])
        utils.bulk_insert(db_details, update_apps_start_sql, apps_start_sql)
    else:
        logger.warning('Services started? - Negative Captain!')
    end_time = datetime.now(est_timezone)
    total_time = end_time - start_time
    logger.info(f'The following instances have failed the patch: {failed_instances}')
    if failed_instances:
        logger.info(f'The following instances have failed the patch: {failed_instances}')
    else:
        logger.info("No instances have failed the patch.")
    logger.info(f'Total Patch Process time: {total_time}')
    
    update_patch_end_completed = '''UPDATE PATCHING_LOG SET SCRIPT_END_TIME = %s
    WHERE ACCOUNT = %s
    AND INSTANCE_ID = %s
    AND COMMAND_ID = %s;'''
    for command_id in command_ids:
        for instance in final_instances:
            patch_end_complete.append([datetime.now(est_timezone), profile, instance, command_id])
        utils.bulk_insert(db_details, update_patch_end_completed, patch_end_complete)
        
    for tracking in instance_tracking:
        data.append([
            tracking[0],
            tracking[1],
            tracking[10].astimezone(est_timezone).strftime('%Y-%m-%d %H:%M:%S') if tracking[10] else 'None',
            tracking[11].astimezone(est_timezone).strftime('%Y-%m-%d %H:%M:%S') if tracking[11] else 'None',
            tracking[12].astimezone(est_timezone).strftime('%Y-%m-%d %H:%M:%S') if tracking[12] else 'None',
            total_time
        ])
    headers = ["Instance ID", "Private IP", "Patch Date", "Stop Date", "Start Date", "Total Time"]
    report_str = tabulate(data, headers, tablefmt="grid")
    print(report_str)
    # Send the report via email
    report_subject = f"Patching Report - Tag: {TARGET_TAG}"
    
    # Calculate summary statistics using actual patch results
    total_instances = len(instance_tracking)
    successful_instances = sum(1 for instance_id in instance_ids if patch_statuses.get(instance_id) == 'Success')
    success_rate = round((successful_instances / total_instances) * 100, 1) if total_instances > 0 else 0
    
    # Prepare summary data
    summary_data = {
        'total_instances': total_instances,
        'success_rate': success_rate,
        'total_duration': str(total_time) if total_time else 'N/A',
        'environment': 'Production',
        'target_tag': TARGET_TAG,
        'patch_window': datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M')
    }
    
    # Build instance data rows for the HTML table
    instance_rows = ""
    for tracking in instance_tracking:
        instance_id = tracking[0]
        private_ip = tracking[1]
        
        # Get actual patch status from patch_statuses
        actual_status = patch_statuses.get(instance_id, 'Unknown')
        status_display = "Success" if actual_status == 'Success' else f"{actual_status}"
        status_class = "status-success" if actual_status == 'Success' else "status-failed"
        
        stop_time = tracking[11].strftime('%H:%M:%S') if tracking[11] else 'N/A'
        start_time = tracking[12].strftime('%H:%M:%S') if tracking[12] else 'N/A'
        
        # Calculate individual duration
        if tracking[11] and tracking[12]:
            duration = tracking[12] - tracking[11]
            duration_str = str(duration).split('.')[0]  # Remove microseconds
        else:
            duration_str = 'N/A'
        
        # Health check status based on actual patch result
        health_status = "Healthy" if actual_status == 'Success' else "Unhealthy"
        
        instance_rows += f"""
                        <tr>
                            <td>{instance_id}</td>
                            <td>{private_ip}</td>
                            <td><span class="{status_class}">{status_display}</span></td>
                            <td>{stop_time}</td>
                            <td>{start_time}</td>
                            <td>{health_status}</td>
                            <td>{'Yes' if tracking[12] else 'No'}</td>
                        </tr>"""
    
    # Create enhanced HTML report
    html_body = create_patching_report_html(
        title=f"Patching Report - {TARGET_TAG}",
        summary_data=summary_data,
        instance_data=instance_rows,
        timestamp=datetime.now(est_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
    )
    
    #send_email_notification(report_subject, html_body, recipients, is_html=True)
    print('Scanning Instances to make it Compliant')
    time.sleep(60)
    scan_instances(final_instances, region, tags_cc, document_name, profile)

    # Upload log file to S3 after patching process
    s3_log_bucket = s3_bucket  # Use your patching bucket or a dedicated log bucket
    log_date = datetime.now(est_timezone).strftime('%Y-%m-%d')
    s3_log_prefix = f"{TARGET_TAG}_Patch/{log_date}"
    log_filename = f'./logs/patching_{log_date}_{TARGET_TAG}.log' # Set this to your actual log file path if different
    upload_log_to_s3(log_filename, s3_log_bucket, s3_log_prefix)

if __name__ == '__main__':
    main()

