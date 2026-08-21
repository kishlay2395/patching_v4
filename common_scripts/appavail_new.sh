#!/bin/sh

#Define Colors in the variables. 
GREEN='\033[0;32m'
RED='\033[0;31m'
NoColor='\033[0m'

DATE_TIME="`date +%d-%b-%Y-%H:%M:%S`"

ServerIP=${1}

ServerUsername=${2}

ServerPassword=${3}

echo -e "$NoColor\n"

#Executing the command to check the memory details 

MyPath=$( pwd )

##Display the Memory details
sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/mem-calc.sh

##Display the Storage details
sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/df-calc.sh

##Display the Time Zone details
sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/time_zone.sh

##Display the Time Zone details
sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/soft_link_report.sh

##Display the Time Zone details
sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/check_nfs.sh

##Display the Time Zone details
sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/check_cups_new.sh

##Display the Time Zone details
sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/check_ftp_new.sh

##Display the Time Zone details
#sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/check_nfs.sh

##Validate Server reachability. 
#sh $MyPath/ssh-status.sh $ServerIP

##Validate FTP Service reachability. 
#sh $MyPath/ftp-status.sh $ServerIP

##Validate CUPS Service reachability. 
#sh $MyPath/cups-status.sh $ServerIP

##Display the Printer count 
sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/printer-calc.sh $ServerIP

##Display the process id and process name
sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/pcount.sh 

#Commented the below two lines on October 08-2023 and added appcount with grep script to identify 80 port.(By Sabari)
##Display the process id and process name
#sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/appcount.sh

##Display the process id and process name
sshpass -p $ServerPassword ssh -o StrictHostKeyChecking=no $ServerUsername@$ServerIP 'bash -s' < $MyPath/appcount-working-grep1.sh





