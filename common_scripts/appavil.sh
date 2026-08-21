#!/bin/sh

#Define Colors in the variables. 
GREEN='\033[0;32m'
RED='\033[0;31m'
NoColor='\033[0m'

DATE_TIME="`date +%d-%b-%Y-%H:%M:%S`"

echo -e "$NoColor\n"

#Executing the command to check the system details locally

MyPath=$( pwd )

##Display the Memory details
bash $MyPath/mem-calc.sh

##Display the Storage details
bash $MyPath/df-calc.sh

##Display the Time Zone details
bash $MyPath/time_zone.sh

##Display the Soft Link details
bash $MyPath/soft_link_report.sh

##Display the NFS details
bash $MyPath/check_nfs.sh

##Display the CUPS details
bash $MyPath/check_cups_new.sh

##Display the FTP details
bash $MyPath/check_ftp_new.sh

##Display the Printer count 
bash $MyPath/printer-calc.sh

##Display the process id and process name
bash $MyPath/pcount.sh

##Display the application details with port 80 filtering
bash $MyPath/appcount-working-grep1.sh





