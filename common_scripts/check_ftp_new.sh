#!/bin/bash

# Script to check FTP-related details
echo "========================================"
echo "Checking FTP configuration and status..."
echo "========================================"

# Function to check if a service is installed and running
check_service_status() {
    local service_name=$1
    if systemctl list-unit-files | grep -qw "$service_name"; then
        echo "The $service_name service is installed."
        if systemctl is-active --quiet "$service_name"; then
            echo "The $service_name service is running."
        else
            echo "The $service_name service is not running."
            echo "You can start it using: sudo systemctl start $service_name"
        fi
    else
        echo "The $service_name service is not installed."
    fi
}

# Check if FTP service is installed and running
echo "Checking FTP Server service..."
check_service_status "vsftpd"
echo -e "-------------------------\n"

# Script to check the status of ports 21 (FTP) and 22 (SSH) on the local server
echo "========================================"
echo "Checking local port status..."
echo "========================================"

# Function to check if a port is listening using netstat
check_port_netstat() {
    local port=$1
    local service_name=$2

    if netstat -tuln | grep -q ":$port"; then
        echo "Port $port ($service_name) is open and listening (checked with netstat)."
    else
        echo "Port $port ($service_name) is not open or not listening (checked with netstat)."
    fi
}

# Check port 21 (FTP) using netstat method
echo "Checking FTP port (21)..."
check_port_netstat 21 "FTP"

# Check port 22 (SSH) using netstat method
echo "Checking SSH port (22)..."
check_port_netstat 22 "SSH"

# Summary
echo ""
echo "SSH,FTP status check completed."
echo "========================================"