import os
import argparse
import textwrap
import logging
from logging.handlers import TimedRotatingFileHandler
from common import utils
from tabulate import tabulate
from validator import *

pid = os.getpid()
parser = argparse.ArgumentParser()
os.environ['db_details'] = "prod_reader_db"
db_details = os.environ.get('db_details')
parser.add_argument('-i', '--instance-id', help="Instance ID.", required=False)
parser.add_argument('-p', '--pre-run', action='store_true', help="Run pre-run tasks.")
parser.add_argument('-u', '--upgrade-os', action='store_true', help="Upgrade the OS as part of the process.")
args = parser.parse_args()
instance_id = args.instance_id
instance_info = []


def get_db_region_profile(instance_id):
    error_flag = False
    error_message = ''
    try:
        print(f'Getting Profile and Region for Instance Id: {instance_id}')
        select_sql = f"SELECT ACCOUNT, REGION FROM EC2_INSTANCE_INFO WHERE INSTANCE_ID = '{instance_id}'"
        instance_data = utils.run_select_sql(db_details, select_sql)
        profile = instance_data[0][0]
        region = instance_data[0][1]
    except Exception as e:
        error_flag = True
        error_message = e
        message = f"Error fetching region and profile for instance {instance_id}: {error_message}"
        log_level = "ERROR"      ## These are the INFO/ERROR/DEBUG/WARN values
        utils.write_cw_logs(pid, log_level, message)  ## This should be your function that you call instead of logging
        print(f"Error occurred while fetching region/profile: {e}")
    if error_flag:
        validate_profile(profile)
        validate_region(region)
    return instance_data


def get_instance_info(profile, region):
    error_flag = False
    volume_ids = []
    try:
        print(f"Fetching instance information for instance id: {instance_id} profile: {profile}, region: {region}")
        message = (f"Fetching instance information for instance id: {instance_id} profile: {profile}, region: {region}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        ec2_cmd = f"aws ec2 describe-instances --instance-ids {instance_id} --profile {profile} --region {region}"
        ec2_output = utils.execute_shell_command(ec2_cmd)[0]
    except Exception as e:
        error_flag = True
        if error_flag:
            validate_instance_id(instance_id)
        message = (f"Error describing instance {instance_id} in {profile}, {region}: {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        print(f"Error occurred while describing instance: {e}")
        return []
    try:
        message = (f"Checking termination protection status for instance {instance_id} in {profile}, {region}")
        log_level = "INFO"
        utils.write_cw_logs(pid, log_level, message)
        termination_cmd = f"aws ec2 describe-instance-attribute --instance-id {instance_id} --attribute disableApiTermination --profile {profile} --region {region}"
        termination_output = utils.execute_shell_command(termination_cmd)[0]
        termination_protection = termination_output.get("DisableApiTermination", {}).get("Value")
    except Exception as e:
        error_flag = True
        message = (f"Error fetching termination protection for instance {instance_id}: {e}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        print(f"Error occurred while fetching termination protection: {e}")
        termination_protection = 'False'
    for reservation in ec2_output.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            try:
                instance_type = instance.get("InstanceType")
                account_num = reservation.get("OwnerId")
                vpc_id = instance.get("VpcId")
                ami_id = instance.get("ImageId")
                key_name = instance.get("KeyName", "N/A")
                subnet_id = instance.get("SubnetId")
                private_ip = instance.get("PrivateIpAddress")
                public_ip = instance.get("PublicIpAddress", "N/A")
                eni_id = instance.get("NetworkInterfaces")[0].get("NetworkInterfaceId")
                security_groups = [sg.get("GroupId") for sg in instance.get("SecurityGroups")]
                availability_zone = instance['Placement'].get('AvailabilityZone')
                instance_architecture = instance.get('Architecture')
                tags = instance.get("Tags", [])
                tag_name = tag_cc = tag_wlt = "N/A"
                for tag in tags:
                    if tag["Key"] == "Name":
                        tag_name = tag["Value"]
                    elif tag["Key"] == "CostCenter":
                        tag_cc = tag["Value"]
                    elif tag["Key"] == "WorkloadType":
                        tag_wlt = tag["Value"]
                    elif tag["Key"] == "AwsBackup":
                        tag_backup = tag["Value"]
                root_device_names = ["/dev/xvda", "/dev/sda1", "/dev/nvme0n1"]
                root_volume = None
                data_volume = None
                data_device_name = None
                for block_device in instance.get("BlockDeviceMappings", []):
                    device_name = block_device.get("DeviceName", "")
                    if device_name in root_device_names:
                        root_volume = block_device.get("Ebs", {}).get("VolumeId")
                    else:
                        data_device_name = device_name
                        data_volume = block_device.get("Ebs", {}).get("VolumeId")
                volume_ids.append([root_volume])
                volume_sizes, volume_types, volume_encrypted, volume_key = get_volume_size(volume_ids, profile, region)
                instance_info.append([vpc_id, profile, region, ami_id, key_name, subnet_id,
                                      private_ip, eni_id, security_groups, root_volume,
                                      data_volume, termination_protection, public_ip,
                                      instance_type, tag_name, tag_cc, tag_wlt, volume_sizes,
                                      account_num, instance_architecture, availability_zone, data_device_name, tag_backup, volume_types, volume_encrypted, volume_key])
            except Exception as e:
                error_flag = True
                message = (f"Error processing instance data: {e}")
                log_level = "ERROR"
                utils.write_cw_logs(pid, log_level, message)
                print(f"Error occurred while processing instance data: {e}")
    if error_flag:
        validate_instance_info(instance_id)
        message = ("Some errors occurred while fetching instance information.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
    return instance_info


def get_volume_size(volume_ids, profile, region):
    volume_sizes = []
    error_flag = False
    for volume in volume_ids:
        try:
            message = (f"Fetching details for volume IDs {volume} in profile: {profile}, region: {region}") 
            log_level = "INFO"
            utils.write_cw_logs(pid, log_level, message)
            volumes = " ".join(volume)
            volume_cmd = f"aws ec2 describe-volumes --volume-ids {volumes} --profile {profile} --region {region}"
            volume_output = utils.execute_shell_command(volume_cmd)[0]
            for vol in volume_output.get("Volumes", []):
                volume_sizes.append(vol.get("Size"))
                volume_types = vol.get("VolumeType")
                volume_encrypted = vol.get("Encrypted")
                volume_key = vol.get("KmsKeyId")
        except Exception as e:
            error_flag = True
            message = (f"Error fetching volume details for {volume}: {e}")
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
            print(f"Error occurred while fetching volume details: {e}")
    if error_flag:
        validate_volume_id(volume_ids)
        message = ("Some errors occurred while fetching volume details.")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
    return volume_sizes, volume_types, volume_encrypted, volume_key


def get_efs_info(subnet_id, profile, region): 
    efs_info = []
    error_flag = False
    try:
        print(f'Getting EFS details')
        efs_cmd = f"aws efs describe-file-systems --profile {profile} --region {region} --query FileSystems[].FileSystemId --output json"
        efs_list, _ = utils.execute_shell_command(efs_cmd)  
    except Exception as e:
        error_flag = True
        print(f"Error occurred while describing EFS details: {e} in {profile} and {region}")
        message = (f"Error occurred while describing EFS details: {e} in {profile} and {region}")
        log_level = "ERROR"
        utils.write_cw_logs(pid, log_level, message)
        return []
    for efs in efs_list:
        try:
            mount_cmd = f"aws efs describe-mount-targets --file-system-id {efs} --profile {profile} --region {region} --output json"
            mount_output, _ = utils.execute_shell_command(mount_cmd)
            mount_targets = mount_output.get("MountTargets", []) if isinstance(mount_output, dict) else []
            tags_cmd = f"aws efs describe-tags --file-system-id {efs} --profile {profile} --region {region} --output json"
            tags_output, _ = utils.execute_shell_command(tags_cmd)
            tags = tags_output.get("Tags", []) if isinstance(tags_output, dict) else []
            efs_name = next((tag["Value"] for tag in tags if tag["Key"] == "Name"), None)
            for mount in mount_targets:
                if mount.get("SubnetId") == subnet_id:
                    efs_info.append([efs_name, efs, subnet_id])
        except Exception as e:
            error_flag = True
            if error_flag:
                validate_efs_info(efs_info)
            print(f"Error occurred while processing EFS details: {e}")
            message = (f"Error occurred while fetching EFS mounted targets: {e} in {profile} and {region}")
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
    return efs_info


def get_route53_records(profile, region, unique_lb_dns, instance_ip):
    records_found_total = []
    message = ('Getting hosted zones')
    log_level = "INFO"
    utils.write_cw_logs(pid, log_level, message)
    for lb_dns_name in unique_lb_dns:
        if lb_dns_name:
            lb_dns_name = lb_dns_name.rstrip('.').lower()
        profile = "default"
        records_found = []
        try:
            hosted_zones_cmd = f"aws route53 list-hosted-zones --profile {profile} --region {region}"
            hosted_zones_output = utils.execute_shell_command(hosted_zones_cmd)[0]
            hosted_zones = hosted_zones_output.get('HostedZones', [])
            for zone in hosted_zones:
                zone_id = zone['Id'].split('/')[-1]
                list_records_cmd = f"aws route53 list-resource-record-sets --hosted-zone-id {zone_id} --profile {profile} --region {region}"
                record_sets_output = utils.execute_shell_command(list_records_cmd)[0]
                record_sets = record_sets_output.get('ResourceRecordSets', [])
                for record in record_sets:
                    record_name = record['Name'].rstrip('.').lower()
                    alias_target = record.get('AliasTarget', {}).get('DNSName', '').rstrip('.').lower()
                    resource_records = [res['Value'].rstrip('.').lower() for res in record.get('ResourceRecords', [])]
                    normalized_lb_dns_name = lb_dns_name.replace("dualstack.", "").replace("internal-", "")
                    normalized_alias_target = alias_target.replace("dualstack.", "").replace("internal-", "")
                    normalized_resource_records = [rr.replace("dualstack.", "").replace("internal-", "") for rr in resource_records]
                    if alias_target:
                        if normalized_lb_dns_name in normalized_alias_target:
                            records_found.append({"Name": record_name, "Record": alias_target})
                    if resource_records:
                        for record_value in normalized_resource_records:
                            if normalized_lb_dns_name in record_value or record_value == instance_ip:
                                records_found.append({"Name": record_name, "Record": record_value})
            if not records_found:
                message = ('No record found')
                log_level = "INFO"
                utils.write_cw_logs(pid, log_level, message)
                records_found.append({"Name": "No Record Found", "Record": lb_dns_name})
        except Exception as e:
            message = (f'Error getting route 53 records: {e}')
            log_level = "ERROR"
            utils.write_cw_logs(pid, log_level, message)
            print(f'Error getting the Route53 records: {e}')
        records_found_total.append(records_found)
    flat_list = [item for sublist in records_found_total for item in sublist]
    return flat_list

def get_load_balancers_for_instance(cost_center, instance_id, profile, region):
    lb_info = {"application": [], "classic": []}
    all_lb_dns_names = set()
    try:
        all_lb_tg_info_query = f"""
            SELECT li.lb_name, li.lb_arn, li.dns_name, li.hosted_zone_id, li.lb_type, 
                   ltgi.target_group_name, ltgi.target_group_arn, li.cost_center, li.workload_type
            FROM lb_info li
            JOIN lb_target_group_info ltgi ON li.lb_arn = ltgi.lb_arn
            WHERE li.cost_center = '{cost_center}'
            ORDER BY li.lb_name;
        """
        all_lb_tg_info = utils.run_select_sql(db_details, all_lb_tg_info_query)

        for all_info in all_lb_tg_info:
            lb_name, lb_arn, dns_name, hosted_zone_id, lb_type, target_name, tg_arn, _, _ = all_info
            dns_name = dns_name if dns_name else 'N/A'

            try:
                target_health_cmd = (
                    f"aws elbv2 describe-target-health "
                    f"--target-group-arn {tg_arn} "
                    f"--profile {profile} --region {region} "
                    f"--output json"
                )
                result = utils.execute_shell_command(target_health_cmd)
                data = result[0] if isinstance(result, (list, tuple)) else result
                target_descriptions = data.get("TargetHealthDescriptions", [])
                for t in target_descriptions:
                    target_id = t.get("Target", {}).get("Id")
                    if target_id == instance_id:
                        lb_info["application"].append({
                            "name": lb_name,
                            "dns_name": dns_name,
                            "target_group": target_name,
                            "type": lb_type,
                            "target_group_arn": tg_arn
                        })
                        if dns_name not in all_lb_dns_names:
                            all_lb_dns_names.add(dns_name)
                        break
            except Exception as e:
                message = f"Error checking target group {tg_arn}: {e}"
                utils.write_cw_logs(pid, "ERROR", message)
    except Exception as e:
        message = f"Database error: {e}"
        utils.write_cw_logs(pid, "ERROR", message)
    try:
        clb_cmd = (
            f"aws elb describe-load-balancers "
            f"--profile {profile} --region {region} "
            f"--query LoadBalancerDescriptions[?Instances[?InstanceId=='{instance_id}']]."
            f"{{LoadBalancerName:LoadBalancerName,DNSName:DNSName}} "
            f"--output json"
        )
        classic_load_balancers = utils.execute_shell_command(clb_cmd)[0]
        if classic_load_balancers and isinstance(classic_load_balancers, list):
            for lb in classic_load_balancers:
                classic_lb_name = lb.get('LoadBalancerName')
                dns = lb.get('DNSName')
                if dns and dns not in all_lb_dns_names:
                    all_lb_dns_names.add(dns)
                    lb_info["classic"].append({
                        "name": classic_lb_name,
                        "dns_name": dns,
                        "type": "classic"
                    })
    except Exception as e:
        message = f"Error fetching classic load balancers: {e}"
        utils.write_cw_logs(pid, "ERROR", message)
    return lb_info, list(all_lb_dns_names)


def pre_output(profile, region, os_upgrade_info):
    try:
        instance_details = os_upgrade_info["ec2_instance"]
        instance_ip = instance_details["private_ip"]
        efs_info = os_upgrade_info["efs_info"]
        load_balancer_info = os_upgrade_info["load_balancers"]
        all_lb_dns_names = os_upgrade_info["all_lb_dns_names"]
        classic_names = {lb["dns_name"]: lb["name"] for lb in load_balancer_info.get("classic", []) if lb.get("dns_name")}
        alb_names = {lb["dns_name"]: lb["name"] for lb in load_balancer_info.get("application", []) if lb.get("dns_name")}
        alb_target_groups = {}
        for lb in load_balancer_info.get("application", []):
            dns = lb.get("dns_name")
            tg = lb.get("target_group")
            if dns:
                alb_target_groups.setdefault(dns, []).append(tg if tg else "No target groups")
        unique_lb_dns = list(dict.fromkeys(all_lb_dns_names))
        records_dict = {}
        for lb_dns in unique_lb_dns:
            records_dict[lb_dns] = get_route53_records(profile, region, [lb_dns], instance_ip)
        records_collected = {}
        for lb_dns in unique_lb_dns:
            lb_name = classic_names.get(lb_dns) or alb_names.get(lb_dns) or "Unknown"
            target_groups = alb_target_groups.get(lb_dns, ["No target groups"])
            target_groups_str = ", ".join(target_groups)
            filtered_records = records_dict.get(lb_dns, [])
            merged_dns_names = ", ".join({record["Name"] for record in filtered_records}) if filtered_records else "No Record Found"
            records_collected[lb_dns] = {
                "lb_dns_name": lb_dns,
                "lb_name": lb_name,
                "target_groups": target_groups_str,
                "dns_name": merged_dns_names
            }

        if records_collected:
            table_data = []
            for rec in records_collected.values():
                lb_disp = textwrap.fill(rec["lb_name"], width=40)
                lb_dns_disp = textwrap.fill(rec["lb_dns_name"], width=40)
                tg_disp = textwrap.fill(rec["target_groups"], width=40)
                dns_disp = textwrap.fill(rec["dns_name"], width=40)
                table_data.append([lb_disp, lb_dns_disp, tg_disp, dns_disp])
            table_output = tabulate(table_data, tablefmt="pretty", headers=["Load Balancer Name", "LB DNS", "Target Groups", "Route53 Record(s)"])
            table_lines = table_output.split("\n")
            table_width = len(table_lines[1])
            title = "Load Balancers".center(table_width - 2)
            print("-" * table_width)
            print(f"|{title}|")
            print("-" * table_width)
            print(table_output)
            print("\n")
        else:
            print("No Route53 records found")

        if instance_details:
            table_data = [
                ["Instance ID", instance_details["instance_id"]],
                ["AMI ID", instance_details["ami_id"]],
                ["Key Pair", instance_details["key_pair"]],
                ["VPC ID", instance_details["vpc_id"]],
                ["Subnet ID", instance_details["subnet_id"]],
                ["Private IP", instance_details["private_ip"]],
                ["Public IP", instance_details["public_ip"]],
                ["ENI ID", instance_details["eni_id"]],
                ["Security Groups", ", ".join(instance_details["security_groups"])],
                ["Root Volume ID", instance_details["root_volume_id"]],
                ["Data Volume ID", instance_details["data_volume_id"]],
                ["Termination Protection", instance_details["termination_protection"]],
                ["Instance Type", instance_details["instance_type"]],
                ["Instance Name", instance_details["tag_name"]],
                ["CostCenter", instance_details["tag_cc"]],
                ["WorkloadType", instance_details["tag_wlt"]],
                ["Volume Sizes", instance_details["volume_sizes"]],
                ["Account Number", instance_details["account_num"]],
                ["Architecture", instance_details["architecture"]],
                ["Availability Zone", instance_details["availability_zone"]],
                ["Data Device Name", instance_details["data_device_name"]],
                ["KMS Key ID", instance_details["volume_key"]]
            ]
            table_output = tabulate(table_data, tablefmt="pretty", headers=[])
            table_lines = table_output.split("\n")
            table_width = len(table_lines[1])
            title = "EC2 Instance Details".center(table_width - 2)
            print("-" * table_width)
            print(f"|{title}|")
            print("-" * table_width)
            print(table_output)
            print("\n")
        else:
            print("No instance records found")

        if efs_info:
            table_data = [[r[0], r[1], r[2]] for r in efs_info]
            table_output = tabulate(table_data, tablefmt="pretty", headers=["EFS Name", "EFS ID", "Subnet ID"])
            table_lines = table_output.split("\n")
            table_width = len(table_lines[0])
            title = "EFS Information".center(table_width - 2)
            print("-" * table_width)
            print(f"|{title}|")
            print("-" * table_width)
            print(table_output)
            print("\n")
        else:
            print("No EFS records found")

    except Exception as e:
        print(f"Error during pre-run: {e}")

