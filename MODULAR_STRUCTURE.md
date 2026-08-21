# Modular Architecture Documentation

## Overview
This project has been refactored into a modular architecture with AWS service-specific packages to improve maintainability, testing, and code organization.

## Directory Structure

```
patching_v4/
├── aws_services/
│   ├── __init__.py
│   ├── ssm/
│   │   ├── __init__.py
│   │   └── commands.py          # SSM-related operations
│   ├── ec2/
│   │   ├── __init__.py
│   │   └── instances.py         # EC2 instance management
│   ├── load_balancer/
│   │   ├── __init__.py
│   │   └── target_groups.py     # ALB target group operations
│   └── s3/
│       ├── __init__.py
│       └── uploads.py           # S3 operations
├── common/
│   ├── __init__.py
│   ├── notifications.py        # Email notifications
│   └── utils.py                 # Database utilities
├── functions.py                 # Backward compatibility layer
├── patching_main.py            # Main orchestration workflow
└── appavil.sh                  # Standalone script file
```

## Module Responsibilities

### aws_services.ssm.commands
- **Purpose**: Centralized SSM operations and command execution
- **Key Functions**:
  - `run_appavil_via_ssm()` - Execute appavil script via SSM
  - `send_patch_command()` - Send patching commands to instances
  - `scan_instances()` - Perform security scans
  - `run_kernel_check_via_ssm()` - Check kernel versions
- **Dependencies**: boto3, common.logger, common.utils

### aws_services.ec2.instances
- **Purpose**: EC2 instance lifecycle management
- **Key Functions**:
  - `stop_wait_start_instances()` - Complete stop/start workflow
  - `get_instance_state()` - Check instance status
  - `wait_for_instance_state()` - Wait for state transitions
- **Dependencies**: boto3, aws_services.ssm.commands

### aws_services.load_balancer.target_groups
- **Purpose**: ALB target group management
- **Key Functions**:
  - `build_instance_target_group_map()` - Map instances to target groups
  - `register_instance_to_target_group()` - Register instances
  - `check_instance_health_in_target_group()` - Health monitoring
- **Dependencies**: boto3

### aws_services.s3.uploads
- **Purpose**: S3 storage operations
- **Key Functions**:
  - `upload_log_to_s3()` - Upload log files to S3
- **Dependencies**: boto3, common.logger

### common.notifications
- **Purpose**: Communication and notification services
- **Key Functions**:
  - `send_email_notification()` - Send email alerts
- **Dependencies**: smtplib, email

## Backward Compatibility

The `functions.py` file serves as a compatibility layer that imports all functions from the new modules, ensuring existing code continues to work without modification.

## Key Improvements

1. **Separation of Concerns**: Each AWS service has its own module
2. **Improved Testability**: Isolated functions can be tested independently
3. **Better Maintainability**: Clear responsibility boundaries
4. **Reduced Coupling**: Modules have minimal interdependencies
5. **EST Timezone Consistency**: All database operations use US/Eastern timezone
6. **Eliminated S3 Dependencies**: Scripts are embedded directly in SSM commands

## Usage Examples

### Direct Import (Recommended for new code)
```python
from aws_services.ssm.commands import run_appavil_via_ssm
from aws_services.ec2.instances import stop_wait_start_instances
from aws_services.load_balancer.target_groups import build_instance_target_group_map
```

### Backward Compatible Import (Existing code)
```python
from functions import *
# All functions available as before
```

## Migration Notes

- All functions maintain their original signatures
- Database operations consistently use EST timezone
- S3 script distribution has been replaced with embedded content
- SSH hostname resolution issues have been resolved
- Comprehensive logging has been added throughout
