#!/bin/sh

#Memory Calculator
##Physical Memory calc. 
tm=$( free -m | head -2|tail -1| awk {'print $2'} )
#tm=$( expr $tm / 1024 )
um=$( free -m | head -2|tail -1| awk {'print $3'} )
fm=$( expr $tm - $um )
echo "----------------------------------------";
echo "Server IP :" $(hostname -I | awk '{print $1}') #or Host_IP="$(hostname -I | awk '{print $1}')"
echo "----------------------------------------";
echo "Physical Memory Information";
echo "---------------------------";
echo "Total Physical Memory = $tm MB"
echo "Used Physical Memory  = $um MB"
echo "----------------------------------------";
echo "Free Physical Memory  = $fm MB"
echo "----------------------------------------";

##Swap Memory Calc. 
swtm=$( free -m | head -3|tail -1| awk {'print $2'} )
#tm=$( expr $swtm / 1024 )
swum=$( free -m | head -3|tail -1| awk {'print $3'} )
swfm=$( expr $swtm - $swum )
echo "----------------------------------------";
echo "Server IP : $( hostname -I | awk '{print $1}')"; #or Host_IP="$(hostname -I | awk '{print $1}')"
echo "----------------------------------------";
echo "Swap  Memory Information";
echo "------------------------";
echo "Total Swap Memory = $swtm MB"
echo "Used Swap Memory  = $swum MB"
echo "----------------------------------------";
echo "Free Swap Memory  = $swfm MB"
echo "----------------------------------------";
