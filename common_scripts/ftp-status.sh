#! /bin/bash
#-------------------------------------------
#Define Colors in the variables. 
DATE_TIME="`date -u +%d-%b-%Y-%H:%M:%S`"
#-------------------------------------------

#ServerIP="$(hostname -I | awk '{print $1}')"

# Check if an argument is provided
if [ $# -ne 1 ]; then
   echo "Usage: $0 <check argument value>"
    exit 1
fi

ServerIP=$1;

##Validate the FTP port in the server.

FTPPort=21
FTPPortStatus=$( nmap -Pn ${FTPPort} ${ServerIP} | grep -w ${FTPPort} | grep -w open |awk {'print $2'} )

	case $FTPPortStatus in
		"open")
			echo "FTP Service (Port:$FTPPort) is available in Server IP: $ServerIP "
			;;
		*)
			echo "FTP Service (Port:$FTPPort) is not available in Server IP: $ServerIP"
			;;
	esac
