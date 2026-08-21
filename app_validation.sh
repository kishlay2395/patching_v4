#!/bin/bash

# =============================================================================
# Consolidated Server Availability Check Script
# This script performs comprehensive system health and availability checks
# =============================================================================

echo ""
echo "=============================================================================="
echo "Server Availability Check Started at $(date)"
echo "=============================================================================="

# =============================================================================
# SYSTEM INFORMATION
# =============================================================================
echo ""
echo "----------------------------------------"
echo "Server IP :" $(hostname -I | awk '{print $1}' 2>/dev/null || hostname)
echo "----------------------------------------"
echo "System Information"
echo "------------------"
echo "Hostname: $(hostname)"
echo "Uptime: $(uptime -p 2>/dev/null || uptime)"
echo "Current User: $(whoami)"
echo "Working Directory: $(pwd)"
echo "----------------------------------------"

# =============================================================================
# MEMORY INFORMATION
# =============================================================================
echo ""
echo "----------------------------------------"
echo "Server IP :" $(hostname -I | awk '{print $1}' 2>/dev/null || hostname)
echo "----------------------------------------"
echo "Physical Memory Information"
echo "---------------------------"
# Physical Memory calc
tm=$(free -m | head -2|tail -1| awk '{print $2}')
um=$(free -m | head -2|tail -1| awk '{print $3}')
fm=$(expr $tm - $um)
echo "Total Physical Memory = $tm MB"
echo "Used Physical Memory  = $um MB"
echo "Free Physical Memory  = $fm MB"
echo "----------------------------------------"

# Swap Memory calc
swtm=$(free -m | head -3|tail -1| awk '{print $2}')
swum=$(free -m | head -3|tail -1| awk '{print $3}')
swfm=$(expr $swtm - $swum)
echo "Swap Memory Information"
echo "-----------------------"
echo "Total Swap Memory = $swtm MB"
echo "Used Swap Memory  = $swum MB"
echo "Free Swap Memory  = $swfm MB"
echo "----------------------------------------"

# Load Average
echo "Load Average: $(cat /proc/loadavg)"
echo "----------------------------------------"

# =============================================================================
# DISK USAGE INFORMATION
# =============================================================================
echo ""
echo "Disk Usage Information"
echo "----------------------"
df -h | { read -r line; echo "$line"; sort -k 6,6; }
echo "----------------------------------------"

# =============================================================================
# SERVER REACHABILITY VALIDATION
# =============================================================================
echo ""
HOST_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || hostname)
echo "Application Port Validation for Server IP: $HOST_IP started on $(date)"
echo ""
echo "Server IP: $HOST_IP is reachable."
echo ""
echo "SSH Service (Port 22) Status:"
if nc -z -w5 localhost 22 2>/dev/null; then
    echo "SSH Service (Port 22): REACHABLE"
else
    echo "SSH Service (Port 22): NOT REACHABLE"
fi
echo "----------------------------------------"

# =============================================================================
# JAVA PROCESS INFORMATION (Similar to pcount.sh)
# =============================================================================
echo ""
HOST_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || hostname)
Total_Process_Count=$(ps -aux | grep java | grep -v grep | wc -l)
Daemon_Process_Count=$(ps -aux | grep java | grep -v grep | grep -v Standalone | grep -v 'i-net' | grep -v health | grep -v '/ant/' | wc -l)

echo "Total number of Java process running on this host $HOST_IP is $Total_Process_Count"
echo "Total number of Daemon / Batch (java) application process available is $Daemon_Process_Count"
echo ""
if [ $Daemon_Process_Count -gt 0 ]; then
    echo "Daemon Process id and name details are given below"
    ps -aux --sort comm | grep java | grep -v grep | grep -v Standalone | grep -v 'i-net' | grep -v health | grep -v '/ant/' | while read value; do
        Pid_java_process_name=$(echo $value | awk '{print $2}')
        process_name=$(echo $value | awk '{print $11}')
        echo "Process ID: $Pid_java_process_name, Process Name: $process_name"
    done
else
    echo "No Java daemon processes running"
fi
echo "----------------------------------------"

# =============================================================================
# APPLICATION PROCESS INFORMATION (Similar to appcount-working-grep.sh)
# =============================================================================
echo ""
HOST_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || hostname)
Total_App_Process_Count=$(ps -aux | grep -w Standalone | grep -v grep | wc -l)

echo "-------------------------------------------------------------------------------"
echo "Total number of App process running on this host $HOST_IP"
echo "Total number of App java process available is $Total_App_Process_Count"
echo "-------------------------------------------------------------------------------"

if [ $Total_App_Process_Count -ne 0 ]; then
    echo "App Process details:"
    ps -aux | grep -w Standalone | grep -v grep | while read value; do
        Pid=$(echo $value | awk '{print $2}')
        process_name=$(echo $value | awk '{print $11}')
        echo "Process ID: $Pid, Process Name: $process_name"
    done
else
    echo "No Standalone application processes running"
fi
echo "----------------------------------------"

# =============================================================================
# FTP SERVICE VALIDATION
# =============================================================================
echo ""
HOST_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || hostname)
echo "FTP Service Validation for Server IP: $HOST_IP"
echo ""
if nc -z -w5 localhost 21 2>/dev/null; then
    echo "FTP Service (Port 21): REACHABLE"
else
    echo "FTP Service (Port 21): NOT REACHABLE"
fi

# Check for FTP processes
ftp_processes=$(ps aux | grep -E "(vsftpd|proftpd|ftpd)" | grep -v grep)
if [ ! -z "$ftp_processes" ]; then
    echo "FTP Processes running:"
    echo "$ftp_processes" | awk '{print "Process ID: " $2 ", Process Name: " $11}'
else
    echo "No FTP processes detected"
fi
echo "----------------------------------------"

# =============================================================================
# CUPS SERVICE VALIDATION
# =============================================================================
echo ""
HOST_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || hostname)
echo "CUPS Service Validation for Server IP: $HOST_IP"
echo ""
if nc -z -w5 localhost 631 2>/dev/null; then
    echo "CUPS Service (Port 631): REACHABLE"
else
    echo "CUPS Service (Port 631): NOT REACHABLE"
fi

echo ""
echo "Printer Configuration:"
if command -v lpstat >/dev/null 2>&1; then
    printer_count=$(lpstat -p 2>/dev/null | wc -l)
    echo "Total Printers Configured: $printer_count"
    if [ $printer_count -gt 0 ]; then
        echo "Printer Details:"
        lpstat -p 2>/dev/null || echo "Cannot retrieve printer details"
    fi
else
    echo "CUPS commands not available"
fi
echo "----------------------------------------"

# =============================================================================
# WEB APPLICATION PORT VALIDATION
# =============================================================================
echo ""
HOST_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || hostname)
echo "Web Application Port Validation for Server IP: $HOST_IP"
echo ""
echo "Port 80 Status:"
if nc -z -w5 localhost 80 2>/dev/null; then
    echo "Port 80: LISTENING"
    # Check what's running on port 80
    port80_process=$(netstat -tlnp 2>/dev/null | grep ":80 " | awk '{print $7}' | cut -d'/' -f2)
    if [ ! -z "$port80_process" ]; then
        echo "Process on Port 80: $port80_process"
    fi
else
    echo "Port 80: NOT LISTENING"
fi

echo ""
echo "Common Web Ports Status:"
for port in 80 443 8080 8443; do
    process_info=$(netstat -tlnp 2>/dev/null | grep ":$port ")
    if [ ! -z "$process_info" ]; then
        process_name=$(echo $process_info | awk '{print $7}' | cut -d'/' -f2)
        echo "Port $port: $process_name"
    else
        echo "Port $port: No process listening"
    fi
done
echo "----------------------------------------"

# =============================================================================
# REPORT COMPLETION
# =============================================================================
echo ""
echo "=============================================================================="
echo "Server Availability Check Completed at $(date)"
echo "=============================================================================="
echo ""
