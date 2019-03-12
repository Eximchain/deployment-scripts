import argparse
import boto3
import json
import os

OUT_FILE_INITIAL = "initial-servers.json"
OUT_FILE_FINAL = "final-servers.json"

# Network ID for main network, gamma, and beta
NETWORK_ID="1"

SUPPORTED_REGIONS = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
                     'eu-central-1', 'eu-west-1', 'eu-west-2',
                     'ap-south-1', 'ap-northeast-1', 'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2',
                     'ca-central-1', 'sa-east-1']

NETWORK_ID_FILTER={'Name': 'tag:NetworkId', 'Values': [NETWORK_ID]}
RUNNING_FILTER={'Name': 'instance-state-name', 'Values': ['running']}

VAULT_ROLE_FILTER={'Name': 'tag:Role', 'Values': ['Vault']}
CONSUL_ROLE_FILTER={'Name': 'tag:Role', 'Values': ['Consul']}
MAKER_ROLE_FILTER={'Name': 'tag:Role', 'Values': ['Maker']}
VALIDATOR_ROLE_FILTER={'Name': 'tag:Role', 'Values': ['Validator']}
OBSERVER_ROLE_FILTER={'Name': 'tag:Role', 'Values': ['Observer']}
BOOTNODE_ROLE_FILTER={'Name': 'tag:Role', 'Values': ['Bootnode']}

def parse_args():
    parser = argparse.ArgumentParser(description='Create config for ssh-to via AWS')
    parser.add_argument('--ssh-user', dest='ssh_user', default='ubuntu', action='store', help='Username that will be used to ssh instances')
    parser.add_argument('--final', dest='final', default=False, action='store_true', help='Output to final-servers.json instead')
    return parser.parse_args()

def get_instances_by_region():
    instances_by_region = {}
    for region in SUPPORTED_REGIONS:
        ec2 = boto3.resource('ec2', region_name=region)
        instances = ec2.instances.filter(Filters=[NETWORK_ID_FILTER, RUNNING_FILTER])
        instances_by_region[region] = instances
    return instances_by_region

def filter_vault_instances(instances_by_region):
    return {region: instances.filter(Filters=[VAULT_ROLE_FILTER]) for region,instances in instances_by_region.items()}

def filter_consul_instances(instances_by_region):
    return {region: instances.filter(Filters=[CONSUL_ROLE_FILTER]) for region,instances in instances_by_region.items()}

def filter_maker_instances(instances_by_region):
    return {region: instances.filter(Filters=[MAKER_ROLE_FILTER]) for region,instances in instances_by_region.items()}

def filter_validator_instances(instances_by_region):
    return {region: instances.filter(Filters=[VALIDATOR_ROLE_FILTER]) for region,instances in instances_by_region.items()}

def filter_observer_instances(instances_by_region):
    return {region: instances.filter(Filters=[OBSERVER_ROLE_FILTER]) for region,instances in instances_by_region.items()}

def filter_bootnode_instances(instances_by_region):
    return {region: instances.filter(Filters=[BOOTNODE_ROLE_FILTER]) for region,instances in instances_by_region.items()}

# Converts to input format for ssh-to: ["hostname_or_ip", "human-readable name", "optional comment"]
def convert_to_output_lists(instances_by_region):
    output_list_a = []
    output_list_b = []
    for region,instances in instances_by_region.items():
        for instance in instances:
            name_tag = [tag for tag in instance.tags if tag['Key'] == 'Name']
            name = name_tag[0]['Value']
            host = args.ssh_user + "@" + instance.public_dns_name
            comment = f'{region}:{instance.instance_id}'
            entry = [host, name, comment]

            if len(output_list_a) > len (output_list_b):
                output_list_b.append(entry)
            else:
                output_list_a.append(entry)
    return output_list_a, output_list_b

# Main script body
args = parse_args()

out_file = OUT_FILE_FINAL if args.final else OUT_FILE_INITIAL
if os.path.isfile(out_file):
    raise RuntimeError(f'Output file {out_file} already exists. Aborting to prevent accidental overwrite.')

all_instances_by_region = get_instances_by_region()

vault_instances_by_region = filter_vault_instances(all_instances_by_region)
consul_instances_by_region = filter_consul_instances(all_instances_by_region)
maker_instances_by_region = filter_maker_instances(all_instances_by_region)
validator_instances_by_region = filter_validator_instances(all_instances_by_region)
observer_instances_by_region = filter_observer_instances(all_instances_by_region)
bootnode_instances_by_region = filter_bootnode_instances(all_instances_by_region)

vault_output_list_a, vault_output_list_b = convert_to_output_lists(vault_instances_by_region)
consul_output_list_a, consul_output_list_b = convert_to_output_lists(consul_instances_by_region)
maker_output_list_a, maker_output_list_b = convert_to_output_lists(maker_instances_by_region)
validator_output_list_a, validator_output_list_b = convert_to_output_lists(validator_instances_by_region)
observer_output_list_a, observer_output_list_b = convert_to_output_lists(observer_instances_by_region)
bootnode_output_list_a, bootnode_output_list_b = convert_to_output_lists(bootnode_instances_by_region)

output = {
    'vault-a': vault_output_list_a, 'vault-b': vault_output_list_b,
    'consul-a': consul_output_list_a, 'consul-b': consul_output_list_b,
    'maker-a': maker_output_list_a, 'maker-b': maker_output_list_b,
    'validator-a': validator_output_list_a, 'validator-b': validator_output_list_b,
    'observer-a': observer_output_list_a, 'observer-b': observer_output_list_b,
    'bootnode-a': bootnode_output_list_a, 'bootnode-b': bootnode_output_list_b
}

if args.final:
    output['all-quorum'] = maker_output_list_a + maker_output_list_b + \
                           validator_output_list_a + validator_output_list_b + \
                           observer_output_list_a + observer_output_list_b
    output['all-servers'] = vault_output_list_a + vault_output_list_b + \
                            consul_output_list_a + consul_output_list_b + \
                            bootnode_output_list_a + bootnode_output_list_b + output['all-quorum']

with open(out_file, 'w') as f:
    json.dump(output, f, indent=2)