#! /bin/sh
# command to print the partiion details of the server 

df -h | { read -r line; echo "$line"; sort -k 6,6; }

echo -e"-------------------------------------------------------------------------------"
echo -e "\n Load average is \n"

cat /proc/loadavg
echo -e"-------------------------------------------------------------------------------"