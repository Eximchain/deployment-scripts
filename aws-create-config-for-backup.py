import argparse
import boto3
import json
import os

OUT_FILE = "backup-servers.json"

# Network ID for main network, gamma, and beta
NETWORK_ID="1"

SUPPORTED_REGIONS = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
                     'eu-central-1', 'eu-west-1', 'eu-west-2',
                     'ap-south-1', 'ap-northeast-1', 'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2',
                     'ca-central-1', 'sa-east-1']

NETWORK_ID_FILTER={'Name': 'tag:NetworkId', 'Values': [NETWORK_ID]}
NODE_FILTER={'Name': 'tag:Role', 'Values': ['Maker', 'Validator', 'Observer']}

def parse_args():
    parser = argparse.ArgumentParser(description='Create config for ssh-to via AWS')
    parser.add_argument('--ssh-user', dest='ssh_user', default='ubuntu', action='store', help='Username that will be used to ssh instances')
    return parser.parse_args()

def get_instance_in_region(region):
    conn = boto3.resource('ec2', region_name=region)
    instances = conn.instances.filter(Filters=[NETWORK_ID_FILTER, NODE_FILTER])
    for instance in instances:
        # Choose arbitrarily
        return instance
    return None

# Converts to input format for ssh-to: ["hostname_or_ip", "human-readable name", "optional comment"]
def convert_to_output_list(region_to_instance, args):
    output = []
    for region,instance in region_to_instance.items():
        name_tag = [tag for tag in instance.tags if tag['Key'] == 'Name']
        name = name_tag[0]['Value']
        hostname = args.ssh_user + '@' + instance.public_dns_name
        entry = [hostname, name, region]
        output.append(entry)
    return output

# Main script body
args = parse_args()

instances = {}
for region in SUPPORTED_REGIONS:
    instance = get_instance_in_region(region)
    if instance:
        instances[region] = instance

output_instances = convert_to_output_list(instances, args)

output = {'backup': output_instances}

with open(OUT_FILE, 'w') as f:
    json.dump(output, f, indent=2)