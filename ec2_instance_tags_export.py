import boto3
import csv

def get_all_regions(session):
    ec2 = session.client('ec2')
    return [r['RegionName'] for r in ec2.describe_regions()['Regions']]

def get_instances_with_tags(session, region):
    ec2 = session.client('ec2', region_name=region)
    data = []
    paginator = ec2.get_paginator('describe_instances')
    for page in paginator.paginate():
        for reservation in page['Reservations']:
            for instance in reservation['Instances']:
                private_ip = instance.get('PrivateIpAddress', '')
                name = ''
                tags = []
                if 'Tags' in instance:
                    for tag in instance['Tags']:
                        if tag['Key'] == 'Name':
                            name = tag['Value']
                        else:
                            tags.append(f"{tag['Key']}={tag['Value']}")
                tags_str = '; '.join(tags)
                data.append([private_ip, name, tags_str])
    return data

def main():
    session = boto3.Session()
    regions = get_all_regions(session)
    all_data = []
    for region in regions:
        print(f"Checking region: {region}")
        all_data.extend(get_instances_with_tags(session, region))
    with open('ec2_instances_tags.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Private IP', 'Instance Name', 'Tags'])
        writer.writerows(all_data)
    print("CSV file 'ec2_instances_tags.csv' created.")

if __name__ == '__main__':
    main()
