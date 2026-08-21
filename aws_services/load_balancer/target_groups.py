"""
Load Balancer operations for the patching system.

This module contains all load balancer-related functions including:
- Target group management
- Instance registration/deregistration
- Health check monitoring
"""

import boto3
import time
from common.logger import logger

def build_instance_target_group_map(region, profile, instance_ids):
    """Build a mapping of instance IDs to their target group ARNs."""
    import boto3
    session = boto3.Session(profile_name=profile)
    elbv2 = session.client('elbv2', region_name=region)

    instance_tg_map = {}
    try:
        paginator = elbv2.get_paginator('describe_target_groups')
        for page in paginator.paginate():
            for tg in page['TargetGroups']:
                tg_arn = tg['TargetGroupArn']
                try:
                    targets = elbv2.describe_target_health(TargetGroupArn=tg_arn)['TargetHealthDescriptions']
                    for target in targets:
                        instance_id = target['Target']['Id']
                        if instance_id in instance_ids:
                            instance_tg_map.setdefault(instance_id, []).append(tg_arn)
                except Exception as e:
                    logger.warning(f"Could not get target health for TG {tg_arn}: {e}")
    except Exception as e:
        logger.error(f"Error retrieving target groups: {e}")

    logger.info(f"Discovered TG map: {instance_tg_map}")
    return instance_tg_map




