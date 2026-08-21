#!/bin/bash

# Usage: ./application-availability.sh <validation_type> <impl_name>
# validation_type: 1=Before, 2=After, 3=Compare
# impl_name: Implementation name identifier
# This script runs locally on the target server

if [ $# -lt 2 ]; then
    echo "Usage: $0 <validation_type> <impl_name>"
    echo "  validation_type: 1=Before Patching, 2=After Patching, 3=Compare Before/After"
    echo "  impl_name: Implementation name identifier"
    echo ""
    echo "Examples:"
    echo "  $0 1 WebApp-Patch"
    echo "  $0 2 WebApp-Patch"
    echo "  $0 3 WebApp-Patch"
    exit 1
fi

OutPath=$(pwd)
MYPath=$(pwd)

MyDate=$(date -u +"%Y-%m-%d")
MyDateTime="$(date -u +"%Y-%m-%d-%H-%M-%S-%3N")"

# Parse command line arguments
ValidationType=$1
ImplName=$2

# Get local server IP for file naming
ServerIP=$(hostname -I | awk '{print $1}')

# Create output directory if not exists
if [ ! -d "${OutPath}/output/${ImplName}-${MyDate}" ]; then
    mkdir -p "${OutPath}/output/${ImplName}-${MyDate}"
fi

case $ValidationType in
    "1")
        echo "Validation output is copied to ${OutPath}/output/${ImplName}-${MyDate}/${ServerIP}-BeforePatching-${MyDateTime}.log"
        cd $MYPath
        bash appavil.sh | tee -ai "${OutPath}/output/${ImplName}-${MyDate}/${ServerIP}-BeforePatching-${MyDateTime}.log"
        ;;
    "2")
        echo "Validation output is copied to ${OutPath}/output/${ImplName}-${MyDate}/${ServerIP}-AfterPatching-${MyDateTime}.log"
        cd $MYPath
        bash appavil.sh | tee -ai "${OutPath}/output/${ImplName}-${MyDate}/${ServerIP}-AfterPatching-${MyDateTime}.log"
        ;;
    "3")
        echo "Validation log is copied to ${OutPath}/output/${ImplName}-${MyDate}/${ImplName}-Validation-details-${MyDateTime}.log"
        cd $MYPath
        bash file_details.sh "${ImplName}-${MyDate}" | tee -ai "${OutPath}/output/${ImplName}-${MyDate}/${ImplName}-Validation-details-${MyDateTime}.log"
        ;;
    *)
        echo "Invalid option. Exiting..."
        exit 1
esac
