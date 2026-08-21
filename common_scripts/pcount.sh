#! /bin/sh -xv
#-------------------------------------------
#Define Colors in the variables. 
GREEN='\033[0;32m'
RED='\033[0;31m'
NoColor='\033[0m'

DATE_TIME="`date +%d-%b-%Y-%H:%M:%S`"
#-------------------------------------------

# Check if an argument is provided
# if [ $# -ne 1 ]; then
#    echo "Usage: $0 <check argument value>"
#    exit 1
#fi

##Assign the argument to the variable Host_IP
Host_IP="$(hostname -I | awk '{print $1}')"

# Using top command to identify the java process 
Total_Process_Count=$(ps -aux | grep java | grep -v grep | wc -l )
Daemon_Process_Count=$(ps -aux | grep java | grep -v grep |grep -v Standalone | grep -v 'i-net' |grep -v health | grep -v '\/ant\/' | wc -l )

echo -e "Total number of Java process running on this host ${Host_IP} is ${Total_Process_Count}"

echo -e "Total number of Batch application process available is"  ${Daemon_Process_Count}

echo -e "\n"
echo -e "Daemon Process id and name details are given below "


#ps -aux | grep -w appadmin | grep java | head -n 1|  while read value
#ps aux --sort comm | grep -w appadmin | grep java |  while read value

ps -aux --sort comm | grep java | grep -v grep |grep -v Standalone | grep -v 'i-net' |grep -v health | grep -v '\/ant\/' | while read value

do
	# To print the selected line value 
	# echo $value

Pid_java_process_name=$(echo $value | awk '{print $2}')

IFS='/' read -ra myArray <<< "$value"
j=0;
for i in "${!myArray[@]}"; 
	do
		# echo "index value is : $i"
		# To print index and value of the array
		# echo "element $i is ${myArray[$i]}"
   	 	if [[ "${myArray[$i]}" == "bin" ]]
  		then
			j=$((i+1))
			#echo "Number of / in the bin path is" $j
			#echo "count value is "$j; 
			export Java_process_name=$(echo ${myArray[$j]} | cut -d " " -f 1)
			#Pid_java_process_name=$(pgrep $Java_process_name)
			#echo -e "$Pid_java_process_name\t----\t$Java_process_name"
			printf "%-10s %-30s" $Pid_java_process_name $Java_process_name
			printf "\n"
			break
  		fi
	done
done




