"""
EC2 instance operations for the patching system.

This module contains all EC2-related functions including:
- Starting and stopping instances
- Instance state management
- Instance health monitoring
"""


import json
import re
import boto3
import time
import os
import subprocess
from datetime import datetime
from common.logger import logger
from common import utils
from aws_services.ssm.commands import run_appavil_via_ssm, run_daemon_restart_via_ssm, run_cups_upgrade_via_ssm, enable_health_monitor_cron
import threading


def get_daemon_counts_from_html(html_content):
    m = re.search(
        r'<td>Daemon / Batch App Processes</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>',
        html_content, re.DOTALL
    )
    if m:
        before = m.group(1).strip()
        after = m.group(2).strip()
        try:
            pre = int(before)
        except:
            pre = 0
        try:
            post = int(after)
        except:
            post = 0
        return pre, post
    return 0, 0


def get_cups_status_from_html(html_content):
    m = re.search(
        r'<td>Cups Service Status</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>',
        html_content, re.DOTALL
    )
    if m:
        before = m.group(1).strip().lower()
        after = m.group(2).strip().lower()
    else:
        before, after = "", ""

    # Version  (Only-Before)
    v = re.search(
        r'<td>CUPS Service Version</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>',
        html_content, re.DOTALL
    )
    cups_version = v.group(1).strip() if v else ""

    return before, after, cups_version


def background_retry_validation(instance_id, ip, instance_name, before_log_file, 
                                 ip_dir, profile, region, est_timezone, Manage_cron, environment, lb_health_before=None, lb_health_after=None):

    MAX_TOTAL_WAIT = 1800  
    total_waited = 0
    
    try:
        attempt = 1
        while True:
            wait_time = 300
            logger.info(f"[Retry-{attempt}] Waiting {wait_time}s for {instance_id}...")
            time.sleep(wait_time)
            total_waited += wait_time

            # Refresh lb_health_after for UAT
            if environment == "uat" and lb_health_before:
                try:
                    elbv2_client = boto3.Session(profile_name=profile).client('elbv2', region_name=region)
                    lb_health_after = {}
                    for tg_arn in lb_health_before.keys():
                        try:
                            lb_arn = elbv2_client.describe_target_groups(TargetGroupArns=[tg_arn])['TargetGroups'][0]['LoadBalancerArns'][0]
                            lb_name = elbv2_client.describe_load_balancers(LoadBalancerArns=[lb_arn])['LoadBalancers'][0]['LoadBalancerName']
                            health_resp = elbv2_client.describe_target_health(TargetGroupArn=tg_arn)
                            for target in health_resp['TargetHealthDescriptions']:
                                if target['Target']['Id'] == instance_id:
                                    lb_health_after[tg_arn] = {
                                        "lb_name": lb_name,
                                        "state": target['TargetHealth']['State']
                                    }
                        except Exception as e:
                            logger.warning(f"Could not refresh after health for {tg_arn}: {e}")
                except Exception as e:
                    logger.warning(f"Could not create elbv2 client for refresh: {e}")

            # After log generate
            output_retry = run_appavil_via_ssm(instance_id, profile, region)
            retry_now = datetime.now(est_timezone).strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]
            after_log_retry = os.path.join(ip_dir, f'{ip}-AfterPatching-Retry{attempt}-{retry_now}.log')
            with open(after_log_retry, 'w') as f:
                f.write(output_retry)
            logger.info(f"[Retry-{attempt}] After log saved: {after_log_retry}")

            # Compare
            report_retry = os.path.join(ip_dir, f'{ip}-Validation-Retry{attempt}-{retry_now}.html')
            if environment == "uat" and (lb_health_before or lb_health_after):
                lb_data = json.dumps({"before": lb_health_before, "after": lb_health_after})
                subprocess.run([
                    'python3', 'compare_validation_logs.py',
                    before_log_file, after_log_retry, report_retry
                ], input=lb_data, text=True, check=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            else:
                subprocess.run([
                    'python3', 'compare_validation_logs.py',
                    before_log_file, after_log_retry, report_retry
                ], check=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

            # Status check
            with open(report_retry, 'r', encoding='utf-8') as f:
                html_content = f.read()
            status_flag = "Red❌" if "Need Attention" in html_content else "Green✅"

            # Rename report
            new_report = os.path.join(ip_dir, f'{ip}-{status_flag}-HM-Retry{attempt}-{retry_now}.html')
            os.rename(report_retry, new_report)

            with open(new_report, 'r', encoding='utf-8') as f:
                html_content = f.read()

            from common.notifications import send_email_notification

            if status_flag == "Green✅":
                if Manage_cron:
                    enable_health_monitor_cron([instance_id], profile, region)
                    logger.info(f"[Retry] Green - cron enabled for {instance_id}")
                    html_content = html_content[::-1].replace(
                        "<td>Disabled</td>"[::-1],
                        "<td>Active</td>"[::-1],
                        1
                    )[::-1]
                else:
                    logger.info(f"{instance_id}: Cron was not active - skipping enable")

                send_email_notification(
                    subject=f"[HM][{status_flag}]App Validation Report -{instance_name}-({ip})",
                    body=html_content,
                    recipients=["kishlayk@softeon.com","CloudOps@softeon.com"],
                    is_html=True
                )
                logger.info(f"[Retry] GREEN mail sent for {instance_id}")
                break

            if total_waited >= MAX_TOTAL_WAIT:
                if Manage_cron:
                    enable_health_monitor_cron([instance_id], profile, region)
                    logger.warning(f"[Retry] Timeout - auto cron enabled for {instance_id}")
                else:
                    logger.warning(f"{instance_id}: Timeout - cron was not active, skipping enable")
                break

            logger.info(f"[Retry-{attempt}] RED for {instance_name} ({ip}), retrying... (Total waited: {total_waited}s)")
            attempt += 1

    except Exception as e:
        logger.error(f"Background retry failed for {instance_id}: {e}")

####################### background retry validation function end ##########################
def daemon_restart_and_revalidate(instance_id, profile, region, ip, ip_dir, before_log_file, instance_name, est_timezone, pre_count, post_count, cups_before, cups_after, cups_version, Manage_cron, environment, lb_health_before=None, lb_health_after=None):
    try:
        
        if pre_count > 0 and post_count < pre_count:
            logger.info(f"Background: restarting daemons on {instance_id}")
            run_daemon_restart_via_ssm(instance_id, profile, region)
            logger.info(f"Waiting 100 sec for daemons to start on {instance_id}")
            time.sleep(100)
        
        if cups_before == "running" and cups_after == "not running" and cups_version == "1.7.5":
            logger.info(f"CUPS was running (v1.7.5) before, not running after - reinstalling on {instance_id}")
            success = run_cups_upgrade_via_ssm(instance_id, profile, region)
            if success:
                logger.info(f"CUPS reinstall successful on {instance_id}")
            else:
                logger.error(f"CUPS reinstall failed on {instance_id}")

        elif cups_before == "not running" and cups_version == "1.7.5":
            logger.info(f"CUPS was not running before (v1.7.5) - skipping reinstall for {instance_id}")

        elif cups_before == "running" and cups_after == "not running" and cups_version != "1.7.5":
            logger.info(f"CUPS version is {cups_version} (not 1.7.5) - skipping reinstall for {instance_id}")
        
        else:
            logger.info(f"CUPS no action needed for {instance_id} - before:{cups_before} after:{cups_after} version:{cups_version}")

        # Refresh lb_health_after for UAT
        if environment == "uat" and lb_health_before:
            try:
                elbv2_client = boto3.Session(profile_name=profile).client('elbv2', region_name=region)
                lb_health_after = {}
                for tg_arn in lb_health_before.keys():
                    try:
                        lb_arn = elbv2_client.describe_target_groups(TargetGroupArns=[tg_arn])['TargetGroups'][0]['LoadBalancerArns'][0]
                        lb_name = elbv2_client.describe_load_balancers(LoadBalancerArns=[lb_arn])['LoadBalancers'][0]['LoadBalancerName']
                        health_resp = elbv2_client.describe_target_health(TargetGroupArn=tg_arn)
                        for target in health_resp['TargetHealthDescriptions']:
                            if target['Target']['Id'] == instance_id:
                                lb_health_after[tg_arn] = {
                                    "lb_name": lb_name,
                                    "state": target['TargetHealth']['State']
                                }
                    except Exception as e:
                        logger.warning(f"Could not refresh after health for {tg_arn}: {e}")
            except Exception as e:
                logger.warning(f"Could not create elbv2 client for refresh: {e}")
        
        # Re-validation
        output_revalidated = run_appavil_via_ssm(instance_id, profile, region)
        
        revalidated_now = datetime.now(est_timezone).strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]
        revalidated_log = os.path.join(ip_dir, f'{ip}-ReValidation-{revalidated_now}.log')
        with open(revalidated_log, 'w') as f:
            f.write(output_revalidated)
        
        revalidated_report = os.path.join(ip_dir, f'{ip}-Daemon-ReValidation-{revalidated_now}.html')
        if environment == "uat" and (lb_health_before or lb_health_after):
            lb_data = json.dumps({"before": lb_health_before, "after": lb_health_after})
            subprocess.run([
                'python3', 'compare_validation_logs.py',
                before_log_file, revalidated_log, revalidated_report
            ], input=lb_data, text=True, check=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        else:
            subprocess.run([
                'python3', 'compare_validation_logs.py',
                before_log_file, revalidated_log, revalidated_report
            ], check=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        with open(revalidated_report, 'r', encoding='utf-8') as f:
            revalidated_html = f.read()
        
        if "Need Attention" in revalidated_html:
            re_status = "Red❌"
        else:
            re_status = "Green✅"
        
        from common.notifications import send_email_notification

        if re_status == "Green✅":
            if Manage_cron:
                enable_health_monitor_cron([instance_id], profile, region)
                logger.info(f"Green after restart - cron enabled for {instance_id}")
                revalidated_html = revalidated_html[::-1].replace(
                    "<td>Disabled</td>"[::-1],
                    "<td>Active</td>"[::-1],
                    1
                )[::-1]
            else:
                logger.info(f"{instance_id}: Cron was not active - skipping enable")

            send_email_notification(
                subject=f"[{re_status}] App Validation Report -{instance_name}-({ip})",
                body=revalidated_html,
                recipients=["kishlayk@softeon.com","CloudOps@softeon.com"],
                is_html=True
            )
            logger.info(f"GREEN re-validation mail sent for {instance_id}")

        else:
            send_email_notification(
                subject=f"[{re_status}] App Validation Report -{instance_name}-({ip})",
                body=revalidated_html,
                recipients=["kishlayk@softeon.com","CloudOps@softeon.com"],
                is_html=True
            )
            logger.info(f"RED re-validation mail sent for {instance_id}")

            logger.info(f"Still Red after restart - starting retry for {instance_id}")
            background_retry_validation(
                instance_id, ip, instance_name, before_log_file,
                ip_dir, profile, region, est_timezone, Manage_cron, environment, lb_health_before, lb_health_after
            )

    except Exception as e:
        logger.error(f"Daemon restart/revalidation failed for {instance_id}: {e}")

from concurrent.futures import ThreadPoolExecutor, as_completed

def check_tg_health(elbv2, tg_arn, instance_id, environment):
    max_tries = 16 if environment == "prod" else 14
    for _ in range(max_tries):
        try:
            response = elbv2.describe_target_health(TargetGroupArn=tg_arn)
            for target in response['TargetHealthDescriptions']:
                if target['Target']['Id'] == instance_id and target['TargetHealth']['State'] == 'healthy':
                    return tg_arn, True
            time.sleep(30)
        except Exception as e:
            logger.warning(f"Error checking TG health for {instance_id} in {tg_arn}: {e}")
    logger.warning(f"{instance_id} not healthy in {tg_arn} after timeout.")
    return tg_arn, False



def stop_wait_start_instances(instance_ids, stopped_instances_local, region, profile, command_ids, instance_tracking, db_details, est_timezone, instance_tg_map, instance_header, before_log_files, cron_was_active, environment):
    """Stop, wait, and start EC2 instances, handling deregistration and health checks."""
    session = boto3.Session(profile_name=profile)
    ec2_resource = session.resource('ec2', region_name=region)
    elbv2 = session.client('elbv2', region_name=region)

    stopped_instance_healths = []
    stopped_instances_local = []
    start_instance_health = []
    final_instances = []
    stopped_total_time = None
    start_total_time = None
    customer_tag = os.environ.get("PATCH_TAG", "UNKNOWN")


    for instance_id in instance_ids:
        ec2_instance = ec2_resource.Instance(instance_id)
        ip = instance_header.get(instance_id, instance_id)


        lb_health_before = {}
        if environment == "uat":
            for tg_arn in instance_tg_map.get(instance_id, []):
                try:
                    tg_name = tg_arn.split("/")[-2]
                    lb_arn = elbv2.describe_target_groups(TargetGroupArns=[tg_arn])['TargetGroups'][0]['LoadBalancerArns'][0]
                    lb_name = elbv2.describe_load_balancers(LoadBalancerArns=[lb_arn])['LoadBalancers'][0]['LoadBalancerName']
                    health_resp = elbv2.describe_target_health(TargetGroupArn=tg_arn)
                    for target in health_resp['TargetHealthDescriptions']:
                        if target['Target']['Id'] == instance_id:
                            lb_health_before[tg_arn] = {
                                "tg_name": tg_name,
                                "lb_name": lb_name,
                                "state": target['TargetHealth']['State']
                            }
                except Exception as e:
                    logger.warning(f"Could not capture before health for {tg_arn}: {e}")

        
        
        # Deregister from all target groups before stop
        # Deregister from all target groups before stop
        for tg_arn in instance_tg_map.get(instance_id, []):
            try:
                logger.info(f"Deregistering {instance_id} from TG {tg_arn}")
                elbv2.deregister_targets(TargetGroupArn=tg_arn, Targets=[{'Id': instance_id}])
            except Exception as e:
                logger.warning(f"Failed to deregister {instance_id} from {tg_arn}: {e}")
        # STOP
        try:
            stop_start_time = datetime.now(est_timezone)
            logger.info(f"Stopping EC2 instance: {instance_id} at {stop_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            ec2_instance.stop(DryRun=False)
            ec2_instance.wait_until_stopped()
            logger.info(f"Instance {instance_id} stopped successfully.")
            stopped_instances_local.append(instance_id)
            stopped_instance_healths.append("Stopped")

            update_sql = '''UPDATE PATCHING_LOG SET EC2_STOP_TIME = %s WHERE ACCOUNT = %s AND INSTANCE_ID = %s AND COMMAND_ID = %s'''
            for command_id in command_ids:
                for instance in instance_tracking:
                    if instance[0] == instance_id:
                        instance[4] = 'Stopped'
                        instance[11] = datetime.now(est_timezone)
                        utils.bulk_insert(db_details, update_sql, [[instance[11], profile, instance_id, command_id]])
                        break
            stop_end_time = datetime.now(est_timezone)
            stopped_total_time = stop_end_time - stop_start_time
            logger.info(f"Stopped {instance_id} in {stopped_total_time}")

        except Exception as e:
            logger.error(f"Error stopping instance {instance_id}: {e}")
            continue

        # START
        try:
            start_start_time = datetime.now(est_timezone)
            logger.info(f"Starting EC2 instance: {instance_id}")
            ec2_instance.start(DryRun=False)
            ec2_instance.wait_until_running()
            logger.info(f"Instance {instance_id} started successfully.")
            # Wait for SSM agent to be ready
            ssm_wait_seconds = 100
            logger.info(f"Waiting {ssm_wait_seconds} seconds for SSM agent to be ready on {instance_id}...")
            time.sleep(ssm_wait_seconds)

            # Re-register to all TGs
            # Re-register to all TGs
            for tg_arn in instance_tg_map.get(instance_id, []):
                try:
                    logger.info(f"Registering {instance_id} to TG {tg_arn}")
                    elbv2.register_targets(TargetGroupArn=tg_arn, Targets=[{'Id': instance_id}])
                except Exception as e:
                    logger.warning(f"Failed to register {instance_id} to {tg_arn}: {e}")

            # Health check in all TGs
            


            healthy = True
            failed_tgs = []
            tg_list = instance_tg_map.get(instance_id, [])

            with ThreadPoolExecutor(max_workers=max(1, len(tg_list))) as executor:
                futures = {
                    executor.submit(check_tg_health, elbv2, tg_arn, instance_id, environment): tg_arn
                    for tg_arn in tg_list
                }
                for future in as_completed(futures):
                    tg_arn, is_healthy = future.result()
                    if not is_healthy:
                        failed_tgs.append(tg_arn)
                        healthy = False            


            #if not healthy:
                # Send notification and abort
                #from common.notifications import send_email_notification
                #ip = instance_header.get(instance_id, "Unknown")
                #subject = f"Aborting patching workflow"
                #body = f"Instance {instance_id} with IP {ip} failed health check in one or more target groups after restart.\nAborting patching workflow."
                #send_email_notification(subject, body, ["kishlayk@softeon.com"] ) #["CloudOps@softeon.com"]
                #logger.error(f"Aborting workflow: {instance_id} is not healthy after restart.")

            if not healthy and environment == "prod":
                from common.notifications import send_email_notification


                for iid in instance_ids:
                    if cron_was_active.get(iid, False):
                        try:
                            enable_health_monitor_cron([iid], profile, region)
                            logger.info(f"Cron enabled for {iid} before abort")
                        except Exception as e:
                            logger.error(f"Failed to enable cron for {iid}: {e}")
                

                

                failed_tg_details = ""
                for failed_tg in failed_tgs:
                    try:
                        tg_name = failed_tg.split("/")[-2]
                        lb_response = elbv2.describe_load_balancers(
                            LoadBalancerArns=[
                                elbv2.describe_target_groups(
                                    TargetGroupArns=[failed_tg]
                                )['TargetGroups'][0]['LoadBalancerArns'][0]
                            ]
                        )
                        lb_name = lb_response['LoadBalancers'][0]['LoadBalancerName']
                    except Exception as e:
                        tg_name = failed_tg.split("/")[-2]
                        lb_name = "Unable to fetch"
                        logger.warning(f"Could not fetch LB details for {failed_tg}: {e}")

                    failed_tg_details += (
                        f"\n  - TG Name : {tg_name}"
                        f"\n    TG ARN  : {failed_tg}"
                        f"\n    LB Name : {lb_name}\n"
                    )

                subject = f" Aborting patching workflow."
                body = (
                    f"Instance ID  : {instance_id}\n"
                    f"IP Address   : {ip}\n\n"
                    f"Failed Health Check Target Groups:\n"
                    f"{failed_tg_details}\n"
                    f"Aborting patching workflow."
                )

                send_email_notification(subject, body, ["kishlayk@softeon.com","CloudOps@softeon.com"])
                logger.warning(f"Aborting workflow: {instance_id} is not healthy after restart.")

                return (
                    stopped_instances_local,
                    stopped_instance_healths,
                    stopped_total_time,
                    instance_tracking,
                    start_instance_health,
                    start_total_time,
                    final_instances,
                    command_ids
                )
                #continue
            if not healthy and environment == "uat":
                logger.warning(f"{instance_id}: Unhealthy in one or more Target Groups, but environment is UAT, continuing process without abort.")
            
            lb_health_after = {}
            if environment == "uat":
                for tg_arn in instance_tg_map.get(instance_id, []):
                    try:
                        tg_name = tg_arn.split("/")[-2]
                        lb_arn = elbv2.describe_target_groups(TargetGroupArns=[tg_arn])['TargetGroups'][0]['LoadBalancerArns'][0]
                        lb_name = elbv2.describe_load_balancers(LoadBalancerArns=[lb_arn])['LoadBalancers'][0]['LoadBalancerName']
                        health_resp = elbv2.describe_target_health(TargetGroupArn=tg_arn)
                        for target in health_resp['TargetHealthDescriptions']:
                            if target['Target']['Id'] == instance_id:
                                lb_health_after[tg_arn] = {
                                    "tg_name": tg_name,
                                    "lb_name": lb_name,
                                    "state": target['TargetHealth']['State']
                                }
                    except Exception as e:
                        logger.warning(f"Could not capture after health for {tg_arn}: {e}")    


            final_instances.append(instance_id)
            start_instance_health.append("Running")

            before_log_file = before_log_files.get(instance_id)
            ip_dir = os.path.dirname(before_log_file)
            
            
            # Run validation after start and save to file
            output_after_start = run_appavil_via_ssm(
                instance_id,
                profile,
                region
            )
            
            # Save after patching validation to file
            after_now = datetime.now(est_timezone).strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]  # Include milliseconds
            after_log_file = os.path.join(ip_dir, f'{ip}-AfterPatching-{after_now}.log')
            with open(after_log_file, 'w') as f:
                f.write(output_after_start)
            logger.info(f"After patching validation saved to: {after_log_file}")
            
            # Generate comparison report
            validation_report_file = os.path.join(ip_dir, f'{ip}-Validation-details-{after_now}.html')
            try:
                # Call the comparison script               
                if environment == "uat" and (lb_health_before or lb_health_after):
                    lb_data = json.dumps({"before": lb_health_before, "after": lb_health_after})
                    subprocess.run([
                        'python3', 'compare_validation_logs.py',
                        before_log_file, after_log_file, validation_report_file,
                        ], input=lb_data, text=True, check=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                else:
                    subprocess.run([
                        'python3', 'compare_validation_logs.py',
                        before_log_file, after_log_file, validation_report_file
                    ], check=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                logger.info(f"Validation comparison report generated: {validation_report_file}")
                
                
                #############################change report  R and G ###############################################
                
                with open(validation_report_file, 'r', encoding='utf-8') as f:
                   html_report_content = f.read()

                # Decide R / G
                if "Need Attention" in html_report_content:
                   status_flag = "Red❌"
                else:
                   status_flag = "Green✅"          
                   
                new_validation_report_file = os.path.join(ip_dir,f"{ip}-{status_flag}-Validation-details-{after_now}.html")
                os.rename(validation_report_file, new_validation_report_file)
                validation_report_file = new_validation_report_file
                
                ##################################################################################################
                
                ec2 = session.resource('ec2', region_name=region)
                instance = ec2.Instance(instance_id)

                instance_name = None
                for tag in instance.tags or []:
                    if tag['Key'] == 'Name':
                      instance_name = tag['Value']
                      break

                if not instance_name:
                   instance_name = "N/A"
                


                if status_flag == "Green✅":
                    Manage_cron = cron_was_active.get(instance_id, False)
                    if Manage_cron:
                        enable_health_monitor_cron([instance_id], profile, region)
                        
                        html_report_content = html_report_content[::-1].replace(
                        "<td>Disabled</td>"[::-1],
                        "<td>Active</td>"[::-1],
                         1 
                        )[::-1]

                        logger.info(f"Green - cron enabled for {instance_id}")
                    else:
                        logger.info(f"{instance_id}: Cron was not active - skipping enable")


                    from common.notifications import send_email_notification
                    send_email_notification(
                        subject=f"[{status_flag}]App Validation Report -{instance_name}-({ip})",
                        body=html_report_content,
                        recipients=["kishlayk@softeon.com","CloudOps@softeon.com"],
                        is_html=True
                    )
                    logger.info(f"GREEN mail sent for {instance_id}")

                if status_flag == "Red❌":
                    Manage_cron = cron_was_active.get(instance_id, False)
                    pre_count, post_count = get_daemon_counts_from_html(html_report_content)
                    cups_before, cups_after, cups_version= get_cups_status_from_html(html_report_content)

                    logger.info(f"Daemon count - Pre: {pre_count}, Post: {post_count}")
                    logger.info(f"CUPS: before={cups_before} after={cups_after} version={cups_version}")

                    daemon_action = pre_count > 0 and post_count < pre_count
                    cups_action = (
                        cups_before == "running" and 
                        cups_after == "not running" and 
                        cups_version == "1.7.5"  
                    )

                    logger.info(f"Manage_cron: {Manage_cron}, daemon_action: {daemon_action}, cups_action: {cups_action}")

                    if  daemon_action or cups_action:
                        thread = threading.Thread(
                            target=daemon_restart_and_revalidate,
                            args=(instance_id, profile, region, ip, ip_dir, before_log_file, instance_name, est_timezone, pre_count, post_count, cups_before, cups_after, cups_version, Manage_cron, environment, lb_health_before, lb_health_after),
                            daemon=False
                        )
                        thread.start()
                        logger.info(f"Background thread started for {instance_id} - daemon:{daemon_action} cups:{cups_action}")
                    else:
                        from common.notifications import send_email_notification
                        send_email_notification(
                            subject=f"[{status_flag}]App Validation Report -{instance_name}-({ip})",
                            body=html_report_content,
                            recipients=["kishlayk@softeon.com","CloudOps@softeon.com"],
                            is_html=True
                        )
                        logger.info(f"RED mail sent for {instance_id} - no daemon/cups issue")

                        
                        retry_thread = threading.Thread(
                            target=background_retry_validation,
                            args=(instance_id, ip, instance_name, before_log_file,
                                   ip_dir, profile, region, est_timezone, Manage_cron, environment, lb_health_before, lb_health_after),
                            daemon=False
                        )
                        retry_thread.start()
                        logger.info(f"Retry thread started for {instance_id}")
                                      
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to generate validation comparison report: {e}")
            except Exception as e:
                logger.error(f"Failed to send validation report email: {e}")

            update_sql = '''UPDATE PATCHING_LOG SET EC2_START_TIME = %s WHERE ACCOUNT = %s AND INSTANCE_ID = %s AND COMMAND_ID = %s'''
            for command_id in command_ids:
                for instance in instance_tracking:
                    if instance[0] == instance_id:
                        instance[4] = 'Running'
                        instance[12] = datetime.now(est_timezone)
                        utils.bulk_insert(db_details, update_sql, [[instance[12], profile, instance_id, command_id]])
                        break
            start_end_time = datetime.now(est_timezone)
            start_total_time = start_end_time - start_start_time
            logger.info(f"Started {instance_id} in {start_total_time}")

            #Add delay before moving to next instance
            if instance_id != instance_ids[-1]:
                delay_seconds = 120  # Set your delay here
                logger.info(f"Waiting {delay_seconds} seconds before proceeding to the next instance...")
                time.sleep(delay_seconds)

        except Exception as e:
            logger.error(f"Error starting instance {instance_id}: {e}")
            continue

    logger.info("All instances processed.")
    return (
        stopped_instances_local,
        stopped_instance_healths,
        stopped_total_time,
        instance_tracking,
        start_instance_health,
        start_total_time,
        final_instances,
        command_ids
    )
