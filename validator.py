import logging
from logging.handlers import TimedRotatingFileHandler
import boto3
import re
from common import utils
import os

pid = os.getpid()
#----
#PRE
#----
def validate_instance_id(instance_id):
    if not instance_id or not re.match(r"i-[0-9a-fA-F]{8,17}", instance_id):
        message = (f"Invalid instance ID: {instance_id}. Instance IDs must start with 'i-' followed by 8-17 alphanumeric characters.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    return True

def validate_profile(profile):
    if not isinstance(profile, str) or not profile:
        message = (f"Invalid AWS profile: {profile}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    return True

def validate_region(region):
    if not region:
        message = ("Region is required but not provided.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    valid_regions = [region['RegionName'] for region in boto3.client('ec2').describe_regions()['Regions']]
    if region not in valid_regions:
        message = (f"Invalid region: {region}. Please check the region and try again.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    return True

def validate_instance_info(instance_info):
    if not isinstance(instance_info, list) or len(instance_info) == 0:
        message = ("Invalid instance info: Must be a non-empty list")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    for instance in instance_info:
        if not isinstance(instance, list) or len(instance) != 18:
            message = (f"Invalid instance structure: {instance}")
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
            return False
    return True

def validate_efs_info(efs_info):
    if not isinstance(efs_info, list) or len(efs_info) == 0:
        message = ("Invalid EFS info: Must be a non-empty list")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    for efs in efs_info:
        if not isinstance(efs, list) or len(efs) != 3:
            message = (f"Invalid EFS structure: {efs}")
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
            return False
    return True

def validate_volume_id(volume_id):
    if not volume_id or not re.match(r"vol-[0-9a-fA-F]{8,17}", volume_id):
        message = (f"Invalid volume ID: {volume_id}. Volume IDs must start with 'vol-' followed by 8-17 alphanumeric characters.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    return True

#-----
#POST
#-----

def validate_network_interface_id(eni_id):
    if not eni_id or not re.match(r"eni-[0-9a-fA-F]{8,17}", eni_id):
        message = (f"Invalid network interface ID: {eni_id}. ENI IDs must start with 'eni-' followed by 8-17 alphanumeric characters.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    return True

def validate_subnet_id(subnet_id):
    if not subnet_id or not re.match(r"subnet-[0-9a-fA-F]{8,17}", subnet_id):
        message = (f"Invalid subnet ID: {subnet_id}. Subnet IDs must start with 'subnet-' followed by 8-17 alphanumeric characters.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    return True

def validate_ami_id(ami_id):
    if not ami_id or not re.match(r"ami-[0-9a-fA-F]{8,17}", ami_id):
        message = (f"Invalid AMI ID: {ami_id}. AMI IDs must start with 'ami-' followed by 8-17 alphanumeric characters.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    return True

def validate_instance_type(instance_type):
    if not instance_type:
        message = ("Instance type is required but not provided.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    valid_instance_types = ['t2.micro', 't2.small', 'm5.large', 'r7a.large', 'r7a.xlarge', 'r6a.large', 'r6a.xlarge']
    if instance_type not in valid_instance_types:
        message = (f"Invalid instance type: {instance_type}. Supported types are {valid_instance_types}.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    return True

def validate_security_groups(security_groups):
    if not security_groups or not isinstance(security_groups, list):
        message = ("Security groups should be a list of group IDs.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    for sg in security_groups:
        if not re.match(r"sg-[0-9a-fA-F]{8,17}", sg):
            message = (f"Invalid security group ID: {sg}. Security groups must start with 'sg-' followed by 8-17 alphanumeric characters.")
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
            return False
    return True

def validate_private_ip(private_ip):
    if not private_ip:
        message = ("Private IP address is required but not provided.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    private_ip_regex = r"^(10|172|192)\.(1[6-9]|2[0-9]|3[0-1]|[1-9])\.(\d{1,3})\.(\d{1,3})$"
    if not re.match(private_ip_regex, private_ip):
        message = (f"Invalid private IP: {private_ip}. It must be a valid private IP address.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    return True

def validate_target_group_arn(target_group_arn):
    if not target_group_arn or not re.match(r"arn:aws:elasticloadbalancing:[a-z0-9\-]*:\d+:targetgroup/[a-zA-Z0-9\-]+/\S+", target_group_arn):
        message = (f"Invalid Target Group ARN: {target_group_arn}. Please provide a valid ARN.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return False
    return True



