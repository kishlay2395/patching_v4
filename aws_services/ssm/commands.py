"""
SSM (Systems Manager) operations for the patching system.

This module contains all SSM-related functions including:
- Running scripts via SSM
- Sending patch commands
- Scanning instances for compliance
- Command status monitoring
"""

import os
import boto3
import time
import shlex
import pytz
from datetime import datetime
from botocore.exceptions import ClientError
from common.logger import logger
from common import utils
from common.notifications import send_critical_alert



#health monitor cron management functions


def check_health_monitor_cron(instance_id, profile, region):

    ssm_client = boto3.Session(profile_name=profile).client('ssm', region_name=region)
    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands': [
                "crontab -l -u appadmin 2>/dev/null | grep 'start_healthmonitor' | grep -v '^#' || true"
            ]
        }
    )
    command_id = response['Command']['CommandId']
    time.sleep(5)
    output = ssm_client.get_command_invocation(
        CommandId=command_id,
        InstanceId=instance_id
    )
    return "start_healthmonitor" in output.get("StandardOutputContent", "")


# Disable - before patching
def disable_health_monitor_cron(instance_ids, profile, region):
    ssm_client = boto3.Session(profile_name=profile).client('ssm', region_name=region)
    ssm_client.send_command(
        InstanceIds=instance_ids,
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands': [
                "crontab -l -u appadmin | sed 's|.*start_healthmonitor.*|#&|' | crontab -u appadmin -"
            ]
        }
    )
    logger.info("Health monitor crontab disabled on all instances")

# Enable - after patching
def enable_health_monitor_cron(instance_ids, profile, region):
    ssm_client = boto3.Session(profile_name=profile).client('ssm', region_name=region)
    ssm_client.send_command(
        InstanceIds=instance_ids,
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands': [
                "crontab -l -u appadmin | sed 's|^#\\(.*start_healthmonitor.*\\)|\\1|' | crontab -u appadmin -"
                
            ]
        }
    )
    logger.info("Health monitor crontab enabled on all instances")


#Demon and cups upgrade functions

def run_daemon_restart_via_ssm(instance_id, profile, region):
    """Find and run all startall scripts via SSM"""
    ssm_client = boto3.Session(profile_name=profile).client('ssm', region_name=region)
    
    command = """
found=0
for base in /data/batchapp/softeon /data/softeon/batchapp; do
  if [ -d "$base" ]; then
    echo "Found base path: $base"
    found=1
    
    for app_dir in "$base"/*/; do
      if [ -d "$app_dir" ]; then
        folder_name=$(basename "$app_dir")
        echo "Checking folder: $folder_name"
        
        find "$app_dir" -maxdepth 1 \
          \( -iname "startall-${folder_name}-*.sh" \
          -o -iname "startall-${folder_name}*.sh" \) \
          ! -iname "*.bkp" \
          ! -iname "*.bkp.*" \
          -print -exec bash {} \\;
      fi
    done
  fi
done

if [ "$found" -eq 0 ]; then
    echo "WARNING: No valid base path found - neither /data/batchapp/softeon nor /data/softeon/batchapp exists!"
fi
"""
    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={'commands': [command]},
        TimeoutSeconds=300
    )
    command_id = response['Command']['CommandId']
    
    for _ in range(10):
        time.sleep(30)
        output = ssm_client.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id,
        )
        if output['Status'] in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
            stdout = output.get('StandardOutputContent', '')
            logger.info(f"Daemon restart output: {stdout}")
            
            if "WARNING: No valid base path found" in stdout:
                logger.warning(f"No daemon path found on {instance_id} - check server paths!")
            break

def run_cups_upgrade_via_ssm(instance_id, profile, region):
    """Install CUPS 1.7.5 from source via SSM"""
    ssm_client = boto3.Session(profile_name=profile).client('ssm', region_name=region)
    
    command = """
set -e
mkdir -p /tmp/cups-backup/cups1.7.5
cp -rvp /etc/cups /tmp/cups-backup/cups1.7.5
cd /tmp/
curl -OL https://github.com/apple/cups/releases/download/release-1.7.5/cups-1.7.5-source.tar.gz
yum groupinstall -y "Development Tools"
tar -xvzf cups-1.7.5-source.tar.gz
cd cups-1.7.5/
./configure
make
make install
systemctl enable cups.service
systemctl start cups.service
"""
    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={'commands': [command]},
        TimeoutSeconds=3600
    )
    command_id = response['Command']['CommandId']
    logger.info(f"CUPS upgrade command sent to {instance_id} (command_id: {command_id})")
    
    success = False
    for _ in range(10):
        time.sleep(30)
        output = ssm_client.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id,
        )
        if output['Status'] in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
            logger.info(f"CUPS upgrade output: {output.get('StandardOutputContent')}")
            if output['Status'] == 'Success':
                success = True
            else:
                logger.error(f"CUPS upgrade failed: {output.get('StandardErrorContent')}")
            break
    
    if not success:
        logger.error(f"CUPS upgrade did not succeed on {instance_id}")
    
    return success



def run_appavil_via_ssm(instance_id, profile, region):
    """Run app_validation.sh on the instance via SSM to check application availability."""
    ssm_client = boto3.Session(profile_name=profile).client('ssm', region_name=region)
    
    # Read the app_validation_v1.sh script from file
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'app_validation_v1.py')
        with open(script_path, 'r') as f:
            appavil_script = f.read()
    except FileNotFoundError:
        logger.error(f"app_validation.py script not found at {script_path}")
        return "ERROR: app_validation.py script file not found"
    except Exception as e:
        logger.error(f"Error reading app_validation.py script: {e}")
        return f"ERROR: Failed to read app_validation.py script: {e}"
    
    # Execute the script directly via SSM
    command = f'echo {shlex.quote(appavil_script)} | python3 -'                  
    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={'commands': [command]},
        TimeoutSeconds=600
    )
    command_id = response['Command']['CommandId']
    logger.info(f"Sent app_validation.py to {instance_id} (command_id: {command_id})")
    output_content = ""
    for _ in range(10):  # Wait up to 5 minutes (10*30s)
        time.sleep(30)
        output = ssm_client.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id,
        )
        status = output['Status']
        if status in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
            output_content = output.get('StandardOutputContent', '')
            error_content = output.get('StandardErrorContent', '')
            logger.info(f"SSM Command Status: {status}")
            logger.info(f"app_validation.py output for {instance_id}:\n{output_content}")
            if status != "Success":
                logger.error(f"app_validation.py failed for {instance_id}:\n{error_content}")
            break
    return output_content

def run_kernel_check_via_ssm(instance_ids, profile, region):
    """Run kernel_check.sh on each instance via SSM and log the output."""
    ssm_client = boto3.Session(profile_name=profile).client('ssm', region_name=region)
    
    # Read the kernel_check.sh script from file
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'kernel_check.sh')
        with open(script_path, 'r') as f:
            kernel_script = f.read()
    except FileNotFoundError:
        logger.error(f"kernel_check.sh script not found at {script_path}")
        return
    except Exception as e:
        logger.error(f"Error reading kernel_check.sh script: {e}")
        return
    
    for instance_id in instance_ids:
        logger.info(f"Running kernel_check.sh on {instance_id} via SSM")
        
        # Execute the script directly via SSM
        command = f'echo {shlex.quote(kernel_script)} | bash'
        response = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={'commands': [command]},
            TimeoutSeconds=900
        )
        command_id = response['Command']['CommandId']
        logger.info(f"Sent kernel_check.sh to {instance_id} (command_id: {command_id})")
        output_content = ""
        for _ in range(10):  # Wait up to 5 minutes (10*30s)
            time.sleep(30)
            output = ssm_client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
            status = output['Status']
            if status in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
                output_content = output.get('StandardOutputContent', '')
                logger.info(f"kernel_check.sh output for {instance_id}:\n{output_content}")
                logger.error(f"kernel_check.sh errors for {instance_id}:\n{output.get('StandardErrorContent')}")
                break


def send_patch_command(instance_ids, region, tags_cc, document_name, profile, instance_tracking, patching_quarter):
    """Send patching SSM command to all instances and log command IDs."""
    command_client = boto3.Session(profile_name=profile).client('ssm', region_name=region)
    command_ids = []
    est_timezone = pytz.timezone('US/Eastern')

    for instance_id in instance_ids:
        try:
            logger.info(f'Sending patch command to instance {instance_id}')
            
 
            command_response = command_client.send_command(
                InstanceIds=[instance_id],
                DocumentName=document_name,
                DocumentVersion='1',
                TimeoutSeconds=120,
                Comment='PatchingScript',
                Parameters={'Operation': ['Install'], 'RebootOption': ['NoReboot']},
                MaxConcurrency='50',
                MaxErrors='0',
            )

            command_id = command_response['Command']['CommandId']
            command_ids.append(command_id)

            update_statement = '''UPDATE PATCHING_LOG
            SET COMMAND_ID = %s,
                PATCH_START_TIME = %s
            WHERE ctid IN (
                SELECT ctid
                FROM PATCHING_LOG
                WHERE INSTANCE_ID = %s
                  AND QUARTER_PATCHED = %s
                  AND PATCH_START_TIME IS NULL
                ORDER BY BACKUP_START_TIME DESC NULLS LAST, SCRIPT_START_TIME DESC NULLS LAST
                LIMIT 1
            );
            '''

            patch_sent = datetime.now(est_timezone)

            for instance in instance_tracking:
                if instance[0] == instance_id:
                    instance[10] = patch_sent
                    break

            record = [(command_id, patch_sent, instance_id, patching_quarter)]

            logger.info(f'Command sent successfully to instance {instance_id}. Command ID: {command_id}')

            db_details = os.environ.get('db_details')
            utils.bulk_insert(db_details, update_statement, record)

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f'Error sending command to instance {instance_id}: {error_message} (Code: {error_code})')
            send_critical_alert(instance_id, f"{error_message} (Code: {error_code})", os.environ.get("PATCH_TAG", "UNKNOWN"))
            exit(1)

        except Exception as e:
            logger.error(f'Failed to update PATCHING_LOG for instance {instance_id}: {e}')
            send_critical_alert(instance_id, str(e), os.environ.get("PATCH_TAG", "UNKNOWN"))
            exit(1)

    return command_ids


def scan_instances(final_instances, region, tags_cc, document_name, profile):
    """Send compliance scan SSM command to all final instances."""
    command_ids = []
    command_client = boto3.Session(profile_name=profile).client('ssm', region_name=region)
    
    for i, instance_id in enumerate(final_instances):
        try:
            logger.info(f'Scanning instance {instance_id}')
            command_response = command_client.send_command(
                InstanceIds=[instance_id],
                DocumentName=document_name,
                DocumentVersion='1',
                TimeoutSeconds=120,
                Comment='PatchingScript',
                Parameters={'Operation': ['Scan'], 'RebootOption': ['NoReboot']},
                MaxConcurrency='50',
                MaxErrors='0',
            )
            command_id = command_response['Command']['CommandId']
            command_ids.append(command_id)
            logger.info(f'Command sent successfully to instance {instance_id}. Command ID: {command_id}')
        except Exception as e:
            logger.error(f'Error sending command to instance {instance_id}: {e}')
    
    return command_ids
