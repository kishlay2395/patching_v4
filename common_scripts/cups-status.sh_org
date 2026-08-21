#! /bin/bash
#-------------------------------------------
#Define Colors in the variables. 
DATE_TIME="`date -u +%d-%b-%Y-%H:%M:%S`"
#-------------------------------------------

# Check if an argument is provided
if [ $# -ne 1 ]; then
echo "Usage: $0 <check argument value>"
    exit 1
fi

ServerIP=$1

##Validate the CUPS port in the server.

 CupsPort=631
 CupsPortStatus=$(nmap -Pn $ServerIP | grep -w 631 | grep -w open |awk {'print $2'})
 
 case $CupsPortStatus in
	"open")
		echo "CUPS Service (Port:$CupsPort) is available in Server IP: $ServerIP"
		;;
	*)
		echo "CUPS Service (Port:$CupsPort) is not available in Server IP: $ServerIP"
		;;
esac
