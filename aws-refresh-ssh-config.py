import argparse
import boto3
import json
import time

IN_FILE = "initial-servers.json"
OUT_FILE = "temp-servers.json"

# Network ID for main network, gamma, and beta
NETWORK_ID="1"
NETWORK_ID_FILTER = {'Name': 'tag:NetworkId', 'Values': [NETWORK_ID]}
RUNNING_FILTER={'Name': 'instance-state-name', 'Values': ['running']}

def parse_args():
    parser = argparse.ArgumentParser(description='Create config for ssh-to via AWS')
    parser.add_argument('--ssh-user', dest='ssh_user', default='ubuntu', action='store', help='Username that will be used to ssh instances')
    parser.add_argument('--refresh-group', dest='refresh_group', required=True, action='store', help='Group from the input that is being replaced')
    return parser.parse_args()

def check_for_replacement(old_exim_node):
    name_filter = {'Name': 'tag:Name', 'Values': [old_exim_node.name]}
    conn = boto3.resource('ec2', region_name=old_exim_node.region)
    # We distinguish 3 cases based on the contents of 'instances'
    # 1. The old instance is still up and the new one is not up yet
    # 2. The old instance is down but the new one is not up yet
    # 3. The new instance is up
    instances = conn.instances.filter(Filters=[NETWORK_ID_FILTER, RUNNING_FILTER, name_filter])
    # In case 2 this loop has no iterations
    for instance in instances:
        temp_exim_node = EximNode.from_boto_instance(instance)
        # This catches case 1, and case 3 where the old node still exists
        if old_exim_node.instance_id == temp_exim_node.instance_id:
            print(f'Old instance {old_exim_node.instance_id} for {old_exim_node.name} not yet replaced')
            continue
        # If the hostname didn't change with the instance id this is probably a bug
        assert(old_exim_node.hostname != temp_exim_node.hostname)
        return temp_exim_node
    return None

def wait_for_replacements(nodes_to_replace):
    original_to_replacement = {node: None for node in nodes_to_replace}
    num_unreplaced_nodes = len(original_to_replacement)

    while num_unreplaced_nodes > 0:
        for original_node,replacement_node in original_to_replacement.items():
            if replacement_node == None:
                original_to_replacement[original_node] = check_for_replacement(original_node)
        num_unreplaced_nodes = len([node for node in original_to_replacement.values() if node == None])
        print(f'Still waiting for {num_unreplaced_nodes} unreplaced nodes')
        if num_unreplaced_nodes > 0:
            sleep_seconds = 20
            print(f'Sleeping for {sleep_seconds} seconds before polling again')
            time.sleep(sleep_seconds)
    return original_to_replacement.values()


class EximNode:
    def __init__(self, hostname, name, region, instance_id):
        self.hostname = hostname
        self.name = name
        self.region = region
        self.instance_id = instance_id
    
    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return (self.hostname, self.name, self.region, self.instance_id) == (other.hostname, other.name, other.region, other.instance_id)

    def __ne__(self, other):
        return not(self == other)
    
    def __hash__(self):
        return hash((self.hostname, self.name, self.region, self.instance_id))

    @classmethod
    def from_json_list(cls, json_list):
        assert(len(json_list) == 3)
        hostname = json_list[0]
        name = json_list[1]
        comment = json_list[2]
        split_comment = comment.split(':')
        assert(len(split_comment) == 2)
        region = split_comment[0]
        instance_id = split_comment[1]
        return cls(hostname, name, region, instance_id)

    @classmethod
    def from_boto_instance(cls, instance):
        hostname = instance.public_dns_name
        name_tag = [tag for tag in instance.tags if tag['Key'] == 'Name']
        name = name_tag[0]['Value']
        region_tag = [tag for tag in instance.tags if tag['Key'] == 'Region']
        region = region_tag[0]['Value']
        instance_id = instance.instance_id
        return cls(hostname, name, region, instance_id)

    # Serializes to ssh-to input style list
    def to_json_list(self, args):
        ssh_hostname = f'{args.ssh_user}@{self.hostname}'
        comment = f'{self.region}:{self.instance_id}'
        return [ssh_hostname, self.name, comment]

# Main script body
args = parse_args()

with open(IN_FILE, 'r') as f:
    input = json.load(f)

nodes_to_replace = [EximNode.from_json_list(node) for node in input[args.refresh_group]]
replacement_nodes = wait_for_replacements(nodes_to_replace)
replacement_node_json_list = [node.to_json_list(args) for node in replacement_nodes]

output = {args.refresh_group: replacement_node_json_list}

print(f'Dumping server config with replacement instances for group {args.refresh_group} to {OUT_FILE}')
with open(OUT_FILE, 'w') as f:
    json.dump(output, f, indent=2)