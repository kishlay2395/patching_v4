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

sitevalidation()
{
	# Script for link is up or down
	# Arg 1 - Application ip address
	# Arg 2 - Application port number
	status_code=$(curl -sI -w "%{http_code}" $1:$2 | tail -1)
	#echo $status_code
	if [ "$status_code" == "200" ] 
	then
		echo -e " \n"
	    echo "Application URL is $1:$2 up and running with status code $status_code"
		echo -e " \n"
	else
		echo -e " \n"
		echo "Application URL is $1:$2 is down and throwing error $status_code"
		echo -e " \n"
	fi
	break
}


##Assign the argument to the variable Host_IP
Host_IP="$(hostname -I | awk '{print $1}')"

# Using top command to identify the java process 
Total_App_Process_Count=$(ps -aux | grep Standalone | grep -v grep |wc -l)

echo "-------------------------------------------------------------------------------";
echo -e "Total number of App process running on this host" ${Host_IP} 
echo -e "Total number of App java process available is \e[0;32m  ${Total_App_Process_Count} \e[0m"
echo "-------------------------------------------------------------------------------";


if [[ ${Total_App_Process_Count} != '0' ]]
then 
	echo -e "\n \n********************** IP address is \"$Host_IP\"**********************" 
	echo -e "-----------------------------------------------------------------------" 
	
	echo -e "-----------------------------------------------------------------------" 
	echo -e " PID     	Java-Name          Port-No      	 URL        	URL-Status    	App-Path% " 
	echo -e "-----------------------------------------------------------------------" 
	
	#ps -aux | grep -w appadmin | grep java | head -n 1|  while read value
	ps aux --sort comm | grep -w appadmin| grep -w java | grep -w Standalone  |while read value	
		do
			# To print the selected line value 
			# echo $value
			App_Pid_java_process_name=$(echo $value | awk '{print $2}')
			IFS='/' read -ra myAppArray <<< "$value"
			j=0;
			for i in "${!myAppArray[@]}"; 
				do
				# echo "index value is : $i"
				# To print index and value of the array
				# echo "element $i is ${myAppArray[$i]}"
				if [[ "${myAppArray[$i]}" == "bin" ]]
				then
					j=$((i+1))
					#echo "Number of / in the bin path is" $j
					#echo "count value is "$j; 
					App_Java_process_name=$(echo ${myAppArray[$j]} | cut -d " " -f 1)
					
					App_Standalone_path=$(ps -aux | grep ${App_Java_process_name} | rev | cut -d = -f 1 | rev | cut -d " " -f 1 | grep /)
					
					App_Port_Netstat_count=$(netstat -anop 2>/dev/null | grep -w ${App_Pid_java_process_name} | grep -w tcp | grep -w "LISTEN" |awk {'print $4'} |cut -d : -f 2 | wc -l)
					
					App_Port_Netstat_Value=$(netstat -anop 2>/dev/null | grep -w ${App_Pid_java_process_name} | grep -w tcp | grep -w "LISTEN" |awk {'print $4'} |cut -d : -f 2)
					#echo $App_Port_Netstat_Value		
										
					for ((i=1;i<=$App_Port_Netstat_count;i=i+1))
					do	
						temp_value=$(echo ${App_Port_Netstat_Value}|cut -d " " -f $i)
									
							if [[ "${temp_value}" =~ ^[0-9]+$ ]]; then
								prefix="${temp_value:0:2}"  # Get the first two characters of the string
							if [ "$prefix" -eq 80 ]; then
								#return 0  # Port starts with '80'
								export App_Port=${temp_value}								
							else 
								last_digit="${temp_value: -1}"  # Get the last character of the string
								if [ "$last_digit" -eq 0 ]; then
								export App_Port=${temp_value}  # Port ends with '0'
								fi
							fi							
						else
							echo "port number not starts with 80 and didn't end with 0"
						fi										
					done
					#App URL 				
					App_Url="${Host_IP}:${App_Port}"
					
					#Validate http status code
					status_code=$(curl -sI -w "%{http_code}" ${App_Url} | tail -1)
					if [ "$status_code" == "200" ]
					then
						Url_Status="UP"
					else
						Url_Status="Down"
					fi
												
					
					while read -r line; 
					do
						myAppNameArray+=($line)
					done <<< $App_Java_process_name
					
					export myAppJavaNameArray="${myAppNameArray[*]}";
												
					#App_Pid_java_process_name=$(pgrep $App_Java_process_name)
					#echo -e "$App_Pid_java_process_name\t----\t$App_Java_process_name"
					printf "%-10s %-25s %-10s %-24s %-10s %10s" $App_Pid_java_process_name $App_Java_process_name $App_Port $App_Url $Url_Status $App_Standalone_path
					printf "\n"
					break
				fi
			done
			
			#echo $myAppJavaNameArray
			
		done
		echo $myAppJavaNameArray
else
	echo -e "Jboss applications are not running on this server" 
fi
echo "-------------------------------------------------------------------------------";
