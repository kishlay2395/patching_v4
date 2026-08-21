#!/bin/bash

#systemctl: This is the command-line tool used to interact with the systemd system and service manager. 
#It allows you to manage services, check their status, and perform other system management tasks.

#is-active: This option checks whether the specified service is currently active (running). It returns an exit status that indicates the state of the service.

#--quiet: This option suppresses output. When used, the command will not print any output to the terminal; it will only return an exit status. 
#This is useful in scripts where you only care about whether the service is running or not, without needing to see the output.

# Function to check and print CUPS service status
check_cups_status() {
    echo "Checking CUPS service status..."
    if  systemctl is-active --quiet cups; then
        echo "CUPS service is running."
    else
        echo "CUPS service is not running."
    fi
}

# Function to check printer configuration
check_printer_configuration() {
    echo "Checking printer configuration..."
    if [ -f /etc/cups/printers.conf ]; then
        echo "Identifying printer drivers..."
        DRIVER_INFO=$( grep -i "MakeModel" /etc/cups/printers.conf)
        if [ -n "$DRIVER_INFO" ]; then
            echo "Printer Drivers Found:"
            echo "$DRIVER_INFO"
        else
            echo "No printer drivers found in /etc/cups/printers.conf."
        fi
    else
        echo "CUPS configuration file /etc/cups/printers.conf does not exist."
    fi
}

# Function to check configured printers
check_configured_printers() {
    echo "Checking configured printers..."
    PRINTER_COUNT=$( lpstat -p 2>/dev/null | wc -l)
    if [ "$PRINTER_COUNT" -gt 0 ]; then
        echo "Number of printers configured: $PRINTER_COUNT"
        # Uncomment this if you need printer details
        # lpstat -p 
    else
        echo "No printers are configured."
    fi
}

# Main script starts here
echo "========================================"
echo "Checking CUPS Information ..."
echo "========================================"

echo "Checking CUPS installation..."

# Check if CUPS is installed via RPM
if  rpm -q cups > /dev/null 2>&1; then
    echo "CUPS is installed."
    CUPS_VERSION=$( rpm -qi cups | awk '/^Version/ {print $NF}')
    echo "CUPS Version: $CUPS_VERSION"

    check_cups_status
    check_printer_configuration
    check_configured_printers

# Check if CUPS is running but not installed via RPM (alternative installations)
elif  pgrep cupsd > /dev/null; then
    echo "CUPS is installed."

    if  command -v cups-config &> /dev/null; then
        echo "cups-config command is available"
        CUPS_VERSION=$( cups-config --version)
        echo "CUPS Version: $CUPS_VERSION"

        check_cups_status
        check_printer_configuration
        check_configured_printers
    else
        echo "cups-config command is unavailable"
    fi
else
    echo "CUPS is not installed on this host."
fi

echo -e "-------------------------\n"
