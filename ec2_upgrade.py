import os
import boto3
import re
import argparse
import logging
from logging.handlers import TimedRotatingFileHandler
from common import utils
from validator import *
from precheck import *

parser = argparse.ArgumentParser()
pid = os.getpid()
os.environ['db_details'] = "prod_reader_db"
db_details = os.environ.get('db_details')
parser.add_argument('-i', '--instance-id', help="Instance ID.", required=False)
parser.add_argument('-p', '--pre-run', action='store_true', help="Run pre-run tasks.")
parser.add_argument('-u', '--upgrade-os', action='store_true', help="Upgrade the OS as part of the process.")
args = parser.parse_args()
instance_id = args.instance_id


def stop_instance(instance_id, profile, region):
    error_flag = False
    stop_cmd = f"aws ec2 stop-instances --instance-ids {instance_id} --profile {profile} --region {region}"
    try:
        message = (f"Stopping instance {instance_id}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        print(f"Stopping instance {instance_id}")
        utils.execute_shell_command(stop_cmd)[0]
        message = (f"Successfully stopped instance {instance_id}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
    except Exception as e:
        error_flag = True
        message = (f"Error stopping instance {instance_id}: {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return
    
def wait_ec2_stopped(instance_id, profile, region):
    try:
        message = (f'Waiting for {instance_id} to fully stop.')
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        wait_stopped_cmd = f"aws ec2 wait instance-stopped --instance-ids {instance_id} --profile {profile} --region {region}"
        output = utils.run_cmd(wait_stopped_cmd)
        if output:
            message = (f'Command output: {output}')
            log_level = "INFO"
            utils.write_cw_logs(pid, log_level, message)
        else:
            message = (f'Instance {instance_id} has stopped, no output expected.')
            log_level = "INFO"
            utils.write_cw_logs(pid, log_level, message)
        return True
    except Exception as e:
        message = (f'Failed to wait for {instance_id} to stop: {e}')
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False

        
def detach_volumes(volume_ids, instance_id, profile, region):
    error_flag = False
    for volume_id in volume_ids:
        detach_volume_cmd = f"aws ec2 detach-volume --volume-id {volume_id} --instance-id {instance_id} --profile {profile} --region {region}"
        try:
            message = (f"Detaching volume {volume_id} from instance {instance_id}")
            log_level = "INFO"
            utils.write_cw_logs(pid, log_level, message)
            print(f"Detaching volume {volume_id} from instance {instance_id}")
            utils.execute_shell_command(detach_volume_cmd)[0]
            message = (f"Successfully detached volume {volume_id} from instance {instance_id}")
            log_level = "INFO"
            utils.write_cw_logs(pid, log_level, message)
        except Exception as e:
            error_flag = True
            message = (f"Error detaching volume {volume_id} from instance {instance_id}: {e}")
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
            return

def turn_off_termination_protection(instance_id, profile, region):
    error_flag = False
    turnoff_termination_cmd = f"aws ec2 modify-instance-attribute --instance-id {instance_id} --no-disable-api-termination --profile {profile} --region {region}"
    try:
        message = (f"Turning off termination protection for instance {instance_id}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        print(f"Turning off termination protection for instance {instance_id}")
        utils.execute_shell_command(turnoff_termination_cmd)[0]
        message = (f"Successfully turned off termination protection for instance {instance_id}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
    except Exception as e:
        error_flag = True
        message = (f"Error turning off termination protection for instance {instance_id}: {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return 
        

def terminate_instances(instance_id, profile, region):
    error_flag = False
    terminate_instance_cmd = f"aws ec2 terminate-instances --instance-ids {instance_id} --profile {profile} --region {region}"
    try:
        message = (f"Terminating instance {instance_id}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        print(f"Terminating instance {instance_id}")
        utils.execute_shell_command(terminate_instance_cmd)[0]
        message = (f"Successfully terminated instance {instance_id}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
    except Exception as e:
        error_flag = True
        message = (f"Error terminating instance {instance_id}: {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return

def wait_for_instance_termination(instance_id, profile, region):
    try:
        message = ('Waiting for instance to be terminated completely.')
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        wait_instance_cmd = f"aws ec2 wait instance-terminated --instance-ids {instance_id} --profile {profile} --region {region}"
        utils.execute_shell_command(wait_instance_cmd)[0]
    except Exception as e:
        print(f"Instance wait failed during termination")
        message = (f"Error while waiting for old instance: {instance_id} to terminate {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return
def create_instance(profile, region, os_upgrade_info):
    error_flag = False
    session = boto3.Session(profile_name=profile)
    ec2_client = session.client('ec2', region_name=region)  
    ami_id = None
    try:
        message = ("Fetching latest Amazon Linux 2023 AMI")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        ami_cmd = f'aws ec2 describe-images --region {region} --profile {profile} --owners amazon --filters "Name=description,Values=Amazon Linux 2023 AMI 2023.7.20250512.0 x86_64 HVM kernel-6.1"'
        ami_output = utils.execute_shell_command(ami_cmd)
        if not ami_output or 'Images' not in ami_output[0]:
            message = ("AMI command returned empty or invalid output")
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
            return None
        latest_ami = None
        latest_date = None
        for ami in ami_output[0]['Images']:
            architecture = ami.get('Architecture')
            description = ami.get('Description')
            usage = ami.get('UsageOperation')
            name = ami.get('Name')
            creation_date = ami.get('CreationDate')
            if os_upgrade_info["ec2_instance"]["architecture"] == architecture and usage == 'RunInstances' and name == 'al2023-ami-2023.6.20250203.1-kernel-6.1-x86_64':
                if latest_date is None or creation_date > latest_date:
                    latest_date = creation_date
                    latest_ami = ami['ImageId']
        if latest_ami:
            ami_id = latest_ami
            message = (f"Using latest Amazon Linux 2023 AMI: {ami_id}")
            log_level = "INFO"
            utils.write_cw_logs(pid, log_level, message)
        else:
            message = ("Amazon Linux 2023 AMI not found")
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
            return None
    except Exception as e:
        message = (f"Error fetching AMI details: {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return None 

    instance_type = os_upgrade_info['ec2_instance']['instance_type']
    instance_type_cmd = f'aws ec2 describe-instance-type-offerings --profile {profile} --filters Name=instance-type,Values=r* --region {region} --location-type availability-zone'
    try:
        instance_types_output = utils.execute_shell_command(instance_type_cmd)[0]
        if instance_types_output:
            instance_types_data = instance_types_output.get('InstanceTypeOfferings', [])
            available_instance_types = [
                instance.get('InstanceType') 
                for instance in instance_types_data 
                if instance.get('Location') == os_upgrade_info['ec2_instance']['availability_zone']
            ]
            instance_pattern = re.compile(r'^([a-z]+\d+[a-z]?)\.(micro|small|medium|large|xlarge|[2-9]xlarge|[1-9][0-9]xlarge)$')
            r_instances = {}
            for inst in available_instance_types:
                if match := instance_pattern.match(inst):
                    family, size = match.groups()
                    if family.startswith("r"):
                        if family not in r_instances:
                            r_instances[family] = {}
                        r_instances[family][size] = inst
            current_instance_match = instance_pattern.match(instance_type)
            if current_instance_match:
                current_family, current_size = current_instance_match.groups()
                if current_family.startswith("r"):
                    upgrade_priority = ['r7a', 'r7', 'r6a', 'r6']
                    for r_family in upgrade_priority:
                        if r_family in r_instances and current_size in r_instances[r_family]:
                            instance_type = r_instances[r_family][current_size]
                            break
    except Exception as e:
        message = f"Error determining upgraded instance type: {e}"
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)

    instance_data = os_upgrade_info["ec2_instance"]
    tag_name = instance_data["tag_name"]
    cost_center = instance_data["tag_cc"]
    workload_type = instance_data["tag_wlt"]
    private_ip = instance_data["private_ip"]
    key_name = instance_data["key_pair"]
    security_groups = instance_data["security_groups"]
    subnet_id = instance_data["subnet_id"]
    public_ip = instance_data["public_ip"]
    volume_sizes = instance_data["volume_sizes"][0]
    account_num = instance_data["account_num"]
    iam_role = f'arn:aws:iam::{account_num}:instance-profile/AmazonEC2RoleforSSM'
    public_ip = public_ip != 'N/A'
    tag_backup = instance_data["tag_backup"]
    volume_type = 'gp3'
    volume_encrypted = instance_data["volume_encrypted"]
    volume_key = instance_data["volume_key"] if instance_data["volume_key"] else None
    eni_id = instance_data["eni_id"]
    if volume_sizes < 20:
        volume_sizes = 20
    else:
        volume_sizes = instance_data["volume_sizes"][0]
    ebs_block_device = {
        'Encrypted': volume_encrypted,
        'DeleteOnTermination': True,
        'VolumeSize': volume_sizes,
        'VolumeType': volume_type
    }
    if volume_key:
        ebs_block_device['KmsKeyId'] = volume_key
    try:
        message = ("Creating a new instance")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        response = ec2_client.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            KeyName=key_name,
            DisableApiTermination=True,
            NetworkInterfaces=[{
                'SubnetId': subnet_id,
                'AssociatePublicIpAddress': public_ip,
                'DeviceIndex': 0,
                'PrivateIpAddresses': [{'Primary': True, 'PrivateIpAddress': private_ip}],
                'Groups': security_groups,
            }],
            BlockDeviceMappings=[{
                'DeviceName': '/dev/xvda',
                'Ebs': ebs_block_device
            }],
            TagSpecifications=[
            {
            'ResourceType': 'instance',
            'Tags': [
                {'Key': 'Name', 'Value': tag_name},
                {'Key': 'CostCenter', 'Value': cost_center},
                {'Key': 'WorkloadType', 'Value': workload_type},
                {'Key': 'AwsBackup', 'Value': tag_backup}
            ]
            }],
            IamInstanceProfile={'Arn': iam_role},
            MetadataOptions={
                'HttpEndpoint': 'enabled',
                'HttpTokens': 'required'
            },
            MinCount=1,
            MaxCount=1)
        if 'Instances' in response:
            new_instance_id = response['Instances'][0]['InstanceId']
            message = (f"Successfully launched EC2 instance with type {instance_type}")
            log_level = "INFO"
            utils.write_cw_logs(pid, log_level, message)
            return new_instance_id, profile, region, eni_id
        else:
            message = ("Instances key not found in response")
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
            return None
    except Exception as e:
        message = (f"Error creating instance: {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return None

def wait_create_instance(new_instance_id, profile, region):
    try:
        message = ('Waiting for new instance to be created completely')
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        wait_create_instance_cmd = f"aws ec2 wait instance-running --instance-ids {new_instance_id} --profile {profile} --region {region}"
        utils.execute_shell_command(wait_create_instance_cmd)
    except Exception as e:
        print(f'Error while waiting for new instance to create.')
        message = (f'Error while waiting for new instance {new_instance_id} to create {e}.')
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return
    
def allocate_id(profile, region, private_ip):
    print('Entering allocate_id function')
    session = boto3.Session(profile_name=profile)
    ec2_client = session.client('ec2', region_name=region)
    try:
        addresses = ec2_client.describe_addresses()['Addresses']
        for address in addresses:
            if address.get('PrivateIpAddress') == private_ip:
                print(f"Matching EIP found: {private_ip}")
                return address['AllocationId']
        print(f"No Elastic IP found matching {private_ip}")
        return None
    except Exception as e:
        print(f"Error finding Elastic IP: {e}")
        return None

def associate_eip(profile, region, new_instance_id, eip_allocation_id, private_ip):
    print('Entering associate_eip function')
    if not eip_allocation_id:
        print("No valid Elastic IP Allocation ID found. Skipping association.")
        return None
    session = boto3.Session(profile_name=profile)
    ec2_client = session.client('ec2', region_name=region)
    try:
        association = ec2_client.associate_address(
            InstanceId=new_instance_id,
            AllocationId=eip_allocation_id,
            PrivateIpAddress=private_ip
        )
        print(f"EIP {eip_allocation_id} associated with instance {new_instance_id}")
        return association
    except Exception as e:
        print(f"Error associating Elastic IP: {e}")
        return None


def attach_old_volumes(os_upgrade_info, new_instance_id, profile, region):
    error_flag = False
    volume_ids = [os_upgrade_info["ec2_instance"]["data_volume_id"]]
    device_name = os_upgrade_info["ec2_instance"]["data_device_name"]
    for volume_id in volume_ids:
        attach_volumes_cmd = f"aws ec2 attach-volume --device {device_name} --volume-id {volume_id} --instance-id {new_instance_id} --profile {profile} --region {region}"
        try:
            message = (f"Attaching volume {volume_id} to instance {new_instance_id}")
            log_level = "INFO"
            utils.write_cw_logs(pid, log_level, message)
            print(f"Attaching volume {volume_id} to instance {new_instance_id}")
            utils.execute_shell_command(attach_volumes_cmd)
            message = (f"Successfully attached volume {volume_id} to instance {new_instance_id}")
            log_level = "INFO"
            utils.write_cw_logs(pid, log_level, message)
        except Exception as e:
            error_flag = True
            message = (f"Error attaching volume {volume_id} to instance {new_instance_id}: {e}")
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
            return

def attach_instance_to_target_group(target_group_arn, new_instance_id, profile, region):
    error_flag = False
    add_instance_targetgroups_cmd = f"aws elbv2 register-targets --target-group-arn {target_group_arn} --targets Id={new_instance_id} --profile {profile} --region {region}"
    try:
        message = (f"Attaching instance {new_instance_id} to target group {target_group_arn}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        print(f"Attaching instance {new_instance_id} to target group {target_group_arn}")
        utils.execute_shell_command(add_instance_targetgroups_cmd)
        message = (f"Successfully attached instance {new_instance_id} to target group {target_group_arn}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
    except Exception as e:
        error_flag = True
        if error_flag:
            validate_target_group_arn(target_group_arn)
        message = (f"Error attaching instance {new_instance_id} to target group {target_group_arn}: {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return

def attach_instance_to_elb(profile, region, new_instance_id, classic_load_balancer_name):
    error_flag = False
    attach_to_lb_cmd = f"aws elb register-instances-with-load-balancer --load-balancer-name {classic_load_balancer_name} --instances {new_instance_id} --profile {profile} --region {region}"
    try:
        message = (f"Attaching instance {new_instance_id} to load balancer {classic_load_balancer_name}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        print(f"Attaching instance {new_instance_id} to load balancer {classic_load_balancer_name}")
        utils.execute_shell_command(attach_to_lb_cmd)
        message = (f"Successfully attached instance {new_instance_id} to load balancer {classic_load_balancer_name}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
    except Exception as e:
        error_flag = True
        message = (f"Error attaching instance {new_instance_id} to load balancer {classic_load_balancer_name}: {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return

def upgrade_os(profile, region, os_upgrade_info, instance_info):
    try:
        message = ("Starting OS upgrade process")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        instance_id = os_upgrade_info["ec2_instance"]["instance_id"]
        root_volume_id = os_upgrade_info["ec2_instance"]["root_volume_id"]
        data_volume_id = os_upgrade_info["ec2_instance"]["data_volume_id"]
        public_ip = os_upgrade_info["ec2_instance"]["public_ip"]
        private_ip = os_upgrade_info["ec2_instance"]["private_ip"]
        volume_ids = [root_volume_id, data_volume_id]
        target_group_arns = [tg["target_group_arn"] for tg in os_upgrade_info["load_balancers"]["application"]]
        classic_load_balancer_names = [lb["name"] for lb in os_upgrade_info["load_balancers"]["classic"]]
        message = ("Stopping and terminating instance")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        eip_allocation_id = allocate_id(profile, region, private_ip)
        stop_instance(instance_id, profile, region)
        wait_ec2_stopped(instance_id, profile, region)
        detach_volumes(volume_ids, instance_id, profile, region)
        turn_off_termination_protection(instance_id, profile, region)
        terminate_instances(instance_id, profile, region)
        wait_for_instance_termination(instance_id, profile, region)
        print("Creating a new instance.")
        message = ("Creating a new instance and attaching old volumes")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        new_instance_id, profile, region, eni_id = create_instance(profile, region, os_upgrade_info)
        wait_create_instance(new_instance_id, profile, region)
        print(f'New Instance Id: {new_instance_id}')
        attach_old_volumes(os_upgrade_info, new_instance_id, profile, region)
        associate_eip(profile, region, new_instance_id, eip_allocation_id, private_ip)
        for target_group_arn in target_group_arns:
            attach_instance_to_target_group(target_group_arn, new_instance_id, profile, region)
        for classic_load_balancer_name in classic_load_balancer_names:
            attach_instance_to_elb(profile, region, new_instance_id, classic_load_balancer_name)
    except Exception as e:
        message = (f"Error during OS upgrade: {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)

