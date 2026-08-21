import os
import argparse
from common import utils
from tabulate import tabulate
from validator import *
from precheck import *  
from ec2_upgrade import *
from datetime import datetime

parser = argparse.ArgumentParser()
pid = os.getpid()
os.environ['db_details'] = "prod_reader_db"
db_details = os.environ.get('db_details')
parser.add_argument('-i', '--instance-id', help="Instance ID.")
parser.add_argument('-p', '--pre-run', action='store_true', help="Run pre-run tasks.")
parser.add_argument('-u', '--upgrade-os', action='store_true', help="Upgrade the OS as part of the process.")
args = parser.parse_args()
instance_id = args.instance_id

    
instance_info = []
os_upgrade_info = {}

def pre_run_tasks(db_info):
    profile = db_info[0][0]
    region = db_info[0][1]
    instance_info = get_instance_info(profile, region)
    vpc_id              = instance_info[0][0]
    profile             = instance_info[0][1]
    region              = instance_info[0][2]
    ami_id              = instance_info[0][3]
    key_pair            = instance_info[0][4]
    subnet_id           = instance_info[0][5]
    private_ip          = instance_info[0][6]
    eni_id              = instance_info[0][7]
    security_groups     = instance_info[0][8]
    root_volume_id      = instance_info[0][9]
    data_volume_id      = instance_info[0][10]
    termination_protection = instance_info[0][11]
    public_ip           = instance_info[0][12]
    instance_type       = instance_info[0][13]
    tag_name            = instance_info[0][14]
    tag_cc              = instance_info[0][15]
    tag_wlt             = instance_info[0][16]
    volume_sizes        = instance_info[0][17]
    account_num         = instance_info[0][18]
    instance_architecture = instance_info[0][19]
    availability_zone   = instance_info[0][20]
    data_device_name    = instance_info[0][21]
    tag_backup          = instance_info[0][22]
    volume_type         = instance_info[0][23]
    volume_encrypted    = instance_info[0][24]
    volume_key          = instance_info[0][25]
    lb_info, all_lb_dns_names = get_load_balancers_for_instance(tag_cc, instance_id, profile, region)
    efs_info = get_efs_info(subnet_id, profile, region)
 

    os_upgrade_info = {
        "ec2_instance": {
            "vpc_id": vpc_id,
            "instance_id": instance_id,
            "ami_id": ami_id,
            "key_pair": key_pair,
            "subnet_id": subnet_id,
            "private_ip": private_ip,
            "public_ip": public_ip,
            "eni_id": eni_id,
            "security_groups": security_groups,
            "root_volume_id": root_volume_id,
            "data_volume_id": data_volume_id,
            "termination_protection": termination_protection,
            "instance_type": instance_type,
            "tag_name": tag_name,
            "tag_cc": tag_cc,
            "tag_wlt": tag_wlt,
            "volume_sizes": volume_sizes,
            "account_num": account_num,
            "architecture": instance_architecture,
            "availability_zone": availability_zone,
            "data_device_name": data_device_name,
            "tag_backup": tag_backup,
            "volume_type": volume_type,
            "volume_encrypted": volume_encrypted,
            "volume_key": volume_key
        },
        "load_balancers": lb_info, 
        "efs_info": efs_info,
        "all_lb_dns_names": all_lb_dns_names,
        "load_balancer_tag_names": [],
    }
    
    pre_output(profile, region, os_upgrade_info) 
    return os_upgrade_info, profile, region


def main():
    if instance_id == None:
        print('Invalid instance id exiting script...') 
        return
    start_time = datetime.now()
    message = f"Script start time: {start_time}"
    log_level = "INFO"      ## These are the INFO/ERROR/DEBUG/WARN values
    utils.write_cw_logs(pid, log_level, message)  ## This should be your function that you call instead of logging
        
    db_info = get_db_region_profile(instance_id)
    profile = db_info[0][0]
    region = db_info[0][1]
    
    if args.pre_run:
        print("Running pre-check tasks...")
        os_upgrade_info, profile, region = pre_run_tasks(db_info)
        return os_upgrade_info, profile, region
    elif args.upgrade_os:
        print("Running pre-check and upgrading OS...")
        os_upgrade_info, profile, region = pre_run_tasks(db_info)
        instance_ip = os_upgrade_info["ec2_instance"]["private_ip"]
        instance_name = os_upgrade_info["ec2_instance"]["tag_name"]
        upgrade = input(f'Confirm details:\nInstance Name: {instance_name} \nInstance ID: {instance_id}\nIP: {instance_ip}\nReady to upgrade? (yes/no): ').strip().lower()
        if upgrade == 'yes':
            upgrade_os(profile, region, os_upgrade_info, instance_info)
        else:
            print('Upgrade not confirmed. Terminating program.')
            exit()
        end_time = datetime.now()
        message = f'End script time: {end_time}'
        log_level = "INFO"      ## These are the INFO/ERROR/DEBUG/WARN values
        utils.write_cw_logs(pid, log_level, message)  ## This should be your function that you call instead of logging
        total_seconds = (end_time - start_time).total_seconds()
        minutes = int(total_seconds // 60)
        seconds = round(total_seconds % 60)
        print(f"Total execution time: {minutes} minutes and {seconds} seconds")

if __name__ == "__main__":
    main()

