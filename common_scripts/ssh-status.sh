#!/bin/sh
#-------------------------------------------
DATE_TIME="`date -u +%d-%b-%Y-%H:%M:%S`"
#-------------------------------------------

# Check if an argument is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <Server IP>"
    exit 1
fi

ServerIP=$1

# Validate Server reachability.
ping -c 1 -W 1 -q "$ServerIP" &>/dev/null
PingStatus=$?

case $PingStatus in
    0)
        echo -e "\n"
        echo -e "Application Port Validation for Server IP: $ServerIP started on $DATE_TIME"
        echo -e ""
        echo -e "Server IP: $ServerIP is reachable."
        ;;
    1)
        echo -e "\n"
        echo -e "Application Port Validation for Server IP: $ServerIP started on $DATE_TIME"
        echo -e ""
        echo -e "Server IP: $ServerIP is NOT reachable. Proceeding with SSH/SFTP port validation..."
        ;;
    2)
        echo -e "Server IP: $ServerIP is not valid."
        exit 1
        ;;
    *)
        echo -e "Unexpected error while checking server reachability."
        exit 1
        ;;
esac

# Validate SSH/SFTP Port
SSHPort=22
SSHPortStatus=$(nmap -p $SSHPort $ServerIP | grep -w "$SSHPort" | grep open | awk '{print $2}')

if [ "$SSHPortStatus" = "open" ]; then
    echo -e "SSH/SFTP Service (Port:$SSHPort) is available on Server IP: $ServerIP"
else
    echo -e "Please check the server IP or SSH/SFTP Service (Port:$SSHPort) is NOT available on Server IP: $ServerIP"
    echo -e "Terminating Application Port Scan."
    exit 1
fi
