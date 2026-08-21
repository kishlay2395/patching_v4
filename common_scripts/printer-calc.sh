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
 CupsPortListen=$(netstat -anop | grep -w 631 | grep -w LISTEN | grep -w tcp)
 CupsPortStatus=$(echo $?)
 
 CupsPrinterCount=$(lpstat -v | wc -l)
case $CupsPortStatus in
	"0")
		echo -e "Total Number of printers availabe in this Server IP: $ServerIP $CupsPrinterCount"
		;;
	*)
		echo -e "CUPS Service (Port:$CupsPort) is not available in Server IP: $ServerIP"
		;;
esac
