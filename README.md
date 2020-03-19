# Dynamic DNS for Route 53

This script updates DNS records hosted by [Amazon Route 53][route53].

[route53]: (https://aws.amazon.com/route53/)


## Install

First, configure a virtual environment and install dependencies:

    virtualenv --python=python3 .venv
    . .venv/bin/activate
    pip install -r requirements.txt
    command -v rehash && rehash

[Configure the AWS command line][aws-config] with your credentials and default region. [Other configuration methods][boto3-config], such as environment variables, are available.

[aws-config]: https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html#cli-quick-configuration
[boto3-config]: https://boto3.amazonaws.com/v1/documentation/api/1.9.42/guide/configuration.html


## Configuring Credentials

Do not leave your AWS credentials lying around in `~/.aws` or your shell history file on a server.

The `grant` subcommand creates an IAM user with limited privileges that can be safely deployed instead. *Note that this user has write access to the entire hosted zone.*

    $ python route53-dyndns.py grant ryan.govost.es
    AWS_ACCESS_KEY_ID=AKIATM5TRILULZDQCDP7
    AWS_SECRET_ACCESS_KEY=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

The `revoke` subcommand will delete the IAM user:

    $ python route53-dyndns.py revoke ryan.govost.es


## Updating DNS

This command updates the DNS record for the domain `ryan.govost.es` to the current external IP address:

    $ python route53-dyndns.py set ryan.govost.es -

The external IP address is determined through a public API which may become unavailable or return an incorrect result. If you want to determine the external IP through other means, simply provide it instead of `-`.


## Systemd Service

To regularly update Route 53 from a Linux host with systemd, edit the credentials, paths, and domain name in `dyndns.service`, then:

    sudo cp dyndns.service dyndns.timer /etc/systemd/system/
    sudo systemctl enable dyndns.timer
    sudo systemctl start dyndns.timer
    systemctl list-timers dyndns.timer

The last command should show when the next update will occur.
