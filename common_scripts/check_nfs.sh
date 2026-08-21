#!/bin/bash

# Script to check NFS-related details
echo "========================================"
echo "Checking NFS configuration and status..."
echo "========================================"

# Function to check if a service is installed and running
check_service_status() {
    local service_name=$1
    if  rpm -q nfs-utils > /dev/null 2>&1; 
	then
        echo "NFS package (nfs-utils) is installed."
        if  systemctl list-unit-files | grep -qw "$service_name"; 
		then
            echo "The $service_name service is available."
            if  systemctl is-active --quiet "$service_name"; 
			then
                echo "The $service_name service is running."
            else
                echo "The $service_name service is not running."
                #echo "You can start it using: sudo systemctl start $service_name"
            fi
        else
            echo "The $service_name service is not installed."
        fi
    else
        echo "NFS package (nfs-utils) is not installed on this host."
    fi
}

# Check if NFS Server and Client services are installed and running
echo "Checking NFS Server service..."
check_service_status "nfs-server.service"
echo -e "-------------------------\n"
echo "Checking NFS Client service..."
check_service_status "nfs-client.target"
echo -e "-------------------------\n"

# Check NFS exports
echo ""
echo "Checking NFS exports..."
if [ -f /etc/exports ]; then
    echo "Contents of /etc/exports:"
     cat /etc/exports
    echo ""
    echo "Currently active NFS exports:"
    #exportfs -v
else
    echo "/etc/exports file does not exist. No NFS exports configured."
fi

# Check mounted NFS shares
echo -e "-------------------------\n"
echo -e "Checking mounted NFS shares using df command:\n"
MOUNTED_NFS_DF=$(df -hT | grep nfs)
if [ -n "$MOUNTED_NFS_DF" ]; 
then
    echo "$MOUNTED_NFS_DF"
else
    echo "No NFS shares are currently mounted."
fi

# Summary
echo ""
echo "NFS status check completed."
echo -e "-------------------------\n"