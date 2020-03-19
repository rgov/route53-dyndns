#!/usr/bin/env python
import argparse
import json
import shlex
import urllib.request

import boto3
import botocore.exceptions
import click


def get_zone_record_set(domain):
    fqdn = domain.rstrip('.') + '.'

    # Find the hosted zone containing this domain
    r53 = boto3.client('route53')
    for zone in r53.list_hosted_zones()['HostedZones']:
        zparts, dparts = zone['Name'].split('.'), fqdn.split('.')
        if zparts == dparts[-len(zparts):]:
            break
    else:
        raise Exception(f'Zone not found for domain {domain}')

    # Find the record set for this domain
    record_sets = r53.list_resource_record_sets(
        HostedZoneId=zone['Id'],
        StartRecordName=fqdn,
        MaxItems='1'
    )
    assert len(record_sets['ResourceRecordSets']) == 1
    assert not record_sets['IsTruncated']
    record_set = record_sets['ResourceRecordSets'][0]

    return (fqdn, zone, record_set)


def get_external_ip():
    out = urllib.request.urlopen('https://icanhazip.com/').read()
    return out.rstrip().decode('ascii')


def get_iam_username(fqdn):
    return f'dyndns@{fqdn}'


@click.group()
def cli():
    pass


@cli.command()
def ip():
    print(get_external_ip())


@cli.command()
@click.argument('domain')
def get(domain):
    _, _, record_set = get_zone_record_set(domain)
    print(record_set['ResourceRecords'][0]['Value'])


@cli.command()
@click.argument('domain')
@click.argument('target')
def set(domain, target):
    _, zone, record_set = get_zone_record_set(domain)

    if target == '-':
        target = get_external_ip()

    # Exit early if the change is unneeded
    if record_set['ResourceRecords'][0]['Value'] == target:
        return

    # Update the record set for new IP address
    r53 = boto3.client('route53')
    r53.change_resource_record_sets(
        HostedZoneId=zone['Id'],
        ChangeBatch={'Changes': [{
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'Name': record_set['Name'],
                'Type': record_set['Type'],
                'TTL': record_set['TTL'],
                'ResourceRecords': [{'Value': target}],
            }
        }]}
    )


@cli.command()
@click.argument('domain')
def grant(domain):
    fqdn, zone, _ = get_zone_record_set(domain)
    zone_id = zone['Id'].split('/')[-1]
    username = get_iam_username(fqdn)

    # Create a user who will be able to modify this hosted zone
    iam = boto3.client('iam')
    iam.create_user(UserName=username)

    # Attach a policy to the user
    policy = {
        'Version': '2012-10-17',
        'Statement': [
            {
                'Sid': 'UpdateRecordSets',
                'Effect': 'Allow',
                'Action': [
                    'route53:ChangeResourceRecordSets',
                    'route53:ListResourceRecordSets',
                ],
                'Resource': f'arn:aws:route53:::hostedzone/{zone_id}',
            },
            {
                'Sid': 'ListHostedZones',
                'Effect': 'Allow',
                'Action': [
                    'route53:ListHostedZones',
                ],
                'Resource': '*',
            }
        ],
    }
    iam.put_user_policy(
        UserName=username,
        PolicyName=username,
        PolicyDocument=json.dumps(policy)
    )

    # Create an access key for the user
    response = iam.create_access_key(UserName=username)
    access_key_id = response['AccessKey']['AccessKeyId']
    secret_access_key = response['AccessKey']['SecretAccessKey']

    # Display values
    print(f'AWS_ACCESS_KEY_ID={shlex.quote(access_key_id)}')
    print(f'AWS_SECRET_ACCESS_KEY={shlex.quote(secret_access_key)}')


@cli.command()
@click.argument('domain')
def revoke(domain):
    fqdn, _, _ = get_zone_record_set(domain)
    username = get_iam_username(fqdn)

    # Delete the hosted zone user
    iam = boto3.client('iam')
    response = iam.list_access_keys(UserName=username)
    for access_key in response['AccessKeyMetadata']:
        iam.delete_access_key(
            UserName=username,
            AccessKeyId=access_key['AccessKeyId']
        )

    iam.delete_user_policy(UserName=username, PolicyName=username)
    iam.delete_user(UserName=username)


if __name__ == '__main__':
    cli()
