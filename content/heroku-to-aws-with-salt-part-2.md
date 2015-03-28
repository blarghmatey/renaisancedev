Title: From Heroku to AWS With SaltStack (Part 2)
Date: 2015-03-25
Category: Operations
Tags: saltstack, operations, automation, aws, git, github


This is the follow-up post describing how I moved a client off of Heroku and onto AWS using SaltStack. The first post can be found [here](/from-heroku-to-aws-with-saltstack-part-1.html). In this section I will describe how I managed the actual EC2 instances using `salt-cloud` and AWS autoscaling.

#AWS Setup

The first step in getting SaltStack set up to work with any cloud provider is to create a configuration file on the salt master that defines the necessary credentials. For AWS that file looks like this:
```
#!salt
aws_provider:
  minion:
    master: {{ salt_master_domain }}

  ssh_interface: private_ips # Master is hosted in same VPS. Otherwise public_ips
  ssh_username:
    - ubuntu
    - ec2-user
    - root
  keyname: salt_master
  private_key: /etc/salt/keys/salt_master
  delete_sshkeys: True

  id: {{ aws:key }}
  key: {{ aws:secret_key }}


  {% if aws_region -%}
  region: {{ aws_region }}
  {% endif -%}
  provider: ec2
  rename_on_destroy: True
```
The first section allows for setting key/value configuration parameters on the minions that are initialized via salt-cloud. In this case it is telling the minion what IP address or URL to use for communicating with the master. The next segment tells the salt master how to connect to the minion over SSH. Since this deployment is inside an Amazon VPS it is using the private interface to connect. It also tells salt which usernames to attempt to use while connecting. The keyname is what tells AWS which SSH key to use when creating the EC2 instance and the private_key is the file path to where the private SSH key is located on the master node.

Next are the IAM keys that you would like to use for managing your compute nodes. The values for the keys themselves are being passed in as context values from the `file.managed` state. Following that is the configuration for wich AWS region you wish to use.

The `provider` configuration is what tells SaltStack which cloud provider you are targeting. In this instance we are using the AWS EC2 API. Finally, `rename_on_destroy` will cause Salt Cloud to rename the EC2 instance when it is destroyed so that subsequent creation of instances will not result in a name collision.

Now that we have a connection to AWS, we need to define each of the instance types that we are interested in creating. To do that we provide a profile that specifies the various values that EC2 needs to be able to spin up a node.
```
#!yaml
mongodb-server:
  provider: aws_provider
  size: m3.medium
  image: ami-<some_id>
  ssh_interface: private_ips
  ssh_username: ubuntu
  block_device_mappings:
    - DeviceName: /dev/sda1
      Ebs.VolumeSize: 50
  subnetid: subnet-<some_id>

  grains:
    roles:
        - mongodb
        - mongodb-server
    env: prod
```
This creates a new EC2 instance of size `m3.medium` with a 50GB EBS disk mounted at `/dev/sda1` and assigns it to a given subnet of the VPS. It also sets the `roles` and `env` grains to be used for targeting within salt. A similar configuration file needs to be created for each type of instance that you are going to be deploying.

#Building the Environment

Now that SaltStack knows how to connect to AWS and build a node we can start telling it how to configure things like auto-scaling, security groups and load-balancing. For the following, you can refer to the collection of formulas found [here](https://github.com/blarghmatey/aws-formula).

The first thing that is needed is to set up the security groups that will be used for the different server types that we are going to deploy. The [formula](https://github.com/blarghmatey/aws-formula/blob/master/aws/security_groups.sls) is driven entirely by pillar data. One thing that I like about this pattern is that it allows for a more data driven infrastructure. An example pillar file might look like this:
```
#!yaml
  security_groups:
    - name: webhost
      description: Web server security group
      vpc_id: vpc-1234567
      rules:
        - ip_protocol: tcp
          from_port: 80
          to_port: 80
          cidr_ip:
            - 0.0.0.0/0
        - ip_protocol: tcp
          from_port: 443
          to_port: 443
          cidr_ip:
            - 0.0.0.0/0
        - ip_protocol: tcp
          from_port: 22
          to_port: 22
          cidr_ip: default
    - name: mongodb
      description: MongoDB Security Group
      vpc_id: vpc-1234567
      rules:
        - ip_protocol: tcp
          from_port: 27017
          to_port: 27017
          cidr_ip: webhost
        - ip_protocol: tcp
          from_port: 22
          to_port: 22
          cidr_ip: default
```
Fortunately SaltStack allows for passing the name attribute of an as-yet undefined security group as the `cidr_ip` of another group, greatly simplifying creation of multiple groups at one time. With this pillar data it is simple to see that we are creating two security groups and that both of them are allowing SSH connections from the `default` security group.

Now that we have defined the network restrictions for our application and database tiers, it is necessary to build the load-balancer that will proxy the traffic for the application servers. Again, the [ELB formula](https://github.com/blarghmatey/aws-formula/blob/master/aws/elb.sls) is entirely data driven.
```
#!yaml
  elb:
    name: MY-ELB
    listeners:
      - elb_port: 443
        instance_port: 443
        certificate: 'arn:aws:iam::<your_account_number>:server-certificate/<your_certificate_name>'
        elb_protocol: HTTPS
        instance_protocol: HTTPS
      - elb_port: 80
        instance_port: 80
        elb_protocol: HTTP
        instance_protocol: HTTP
    subnets:
      - subnet-<vpc_subnet1>
      - subnet-<vpc_subnet2>
      - subnet-<vpc_subnet3>
    health_check:
      target: 'HTTPS:443/check.html'
    attributes:
      cross_zone_load_balancing:
        enabled: True
    security_groups:
      - default
      - webhost
```
This is creating an elastic load balancer listening on ports 80 and 443 and proxying those requests to servers across each of the subnets contained in the target VPC.

Now that the ELB has been created, we can create the autoscale group for the application tier. To make this work, we need to define two sections of pillar data. First the settings for the autoscale group itself.
```
#!sls
  autoscale:
    groups:
      - name: app-hosts
        desired_capacity: 2
        max_size: 10
        min_size: 2
        default_cooldown: 1500
        vpc_zone_identifiers:
          - subnet-<vpc_subnet1>
          - subnet-<vpc_subnet2>
          - subnet-<vpc_subnet3>
        load_balancers:
          - MY-ELB
        launch_config_name: webhost
        launch_config:
          - image_id: ami-1234567
          - key_name: salt_master
          - instance_type: t2.small
          - security_groups:
              - webhost
              - default
          - region: us-east-1
        scaling_policies:
          - name: webhost_scale_up
            adjustment_type: ChangeInCapacity
            as_name: app-hosts
            scaling_adjustment: 1
          - name: webhost_scale_down
            adjustment_type: ChangeInCapacity
            as_name: app-hosts
            scaling_adjustment: -1
```
This will scale up and down by one node at a time when the associated cloudwatch alarms are triggered. Instances that are added to the autoscale group will also be registered with the ELB instance that we created previously. The settings for the cloudwatch alarms that will trigger the autoscaling are shown here:
```
#!sls
  cloudwatch:
    alarms:
      - name: webhost_cpu_scale_up
        attributes:
          metric: CPUUtilization
          namespace: 'AWS/EC2'
          statistic: Average
          comparison: ">="
          threshold: 70.0
          period: 60
          evaluation_periods: 5
          description: 'Web hosts scale up alarm'
          alarm_actions:
            - arn:aws:sns:us-east-1:<account_id>:alert_salt_web_scale_up:<UUID for sns event>
            - scaling_policy:app-hosts:webhost_scale_up
          insufficient_data_actions: []
          ok_actions: []
          dimensions:
            AutoScalingGroupName:
              - app-hosts
      - name: php_cpu_scale_down
        attributes:
          metric: CPUUtilization
          namespace: 'AWS/EC2'
          statistic: Average
          comparison: "<="
          threshold: 40.0
          period: 60
          evaluation_periods: 5
          description: 'PHP hosts scale down alarm'
          alarm_actions:
            - arn:aws:sns:us-east-1:<account_id>:alert_salt_php_scale_down:<UUID for sns event>
            - scaling_policy:app-hosts:webhost_scale_down
          insufficient_data_actions: []
          ok_actions: []
          dimensions:
            AutoScalingGroupName:
              - app-hosts
```
This will trigger building of a new node when the average CPU usage of the group surpasses 70% for 5 minutes, and then remove it once the usage drops back below 40% for 5 minutes. This set up does require a manual component for creating the SNS notifications that send a request to the Salt API. The SNS request triggers an event in the reactor system which we will use to register the minions that are created from the autoscaling.

This reactor function registers the minions with the salt master. It is adapted from the reactor formula found [here](https://github.com/saltstack-formulas/ec2-autoscale-reactor).
```
#!python
#!py

import pprint
import os
import time
import json
import requests
import binascii
import M2Crypto
import salt.utils.smtp as smtp
import salt.config as config


def run():
    '''
    Run the reactor
    '''
    sns = data['post']

    if 'SubscribeURL' in sns:
        # This is just a subscription notification
        msg_kwargs = {
            'smtp.subject': 'EC2 Autoscale Subscription (via Salt Reactor)',
            'smtp.content': '{0}\r\n'.format(pprint.pformat(sns)),
        }
        smtp.send(msg_kwargs, __opts__)
        return {}

    url_check = sns['SigningCertURL'].replace('https://', '')
    url_comps = url_check.split('/')
    if not url_comps[0].endswith('.amazonaws.com'):
        # The expected URL does not seem to come from Amazon, do not try to
        # process it
        msg_kwargs = {
            'smtp.subject': 'EC2 Autoscale SigningCertURL Error (via Salt Reactor)',
            'smtp.content': (
                'There was an error with the EC2 SigningCertURL. '
                '\r\n{1} \r\n{2} \r\n'
                'Content received was:\r\n\r\n{0}\r\n').format(
                    pprint.pformat(sns), url_check, url_comps[0]
                ),
        }
        smtp.send(msg_kwargs, __opts__)
        return {}

    if 'Subject' not in sns:
        sns['Subject'] = ''

    pem_request = requests.request('GET', sns['SigningCertURL'])
    pem = pem_request.text

    str_to_sign = (
        'Message\n{Message}\n'
        'MessageId\n{MessageId}\n'
        'Subject\n{Subject}\n'
        'Timestamp\n{Timestamp}\n'
        'TopicArn\n{TopicArn}\n'
        'Type\n{Type}\n'
    ).format(**sns)

    cert = M2Crypto.X509.load_cert_string(str(pem))
    pubkey = cert.get_pubkey()
    pubkey.reset_context(md='sha1')
    pubkey.verify_init()
    pubkey.verify_update(str_to_sign.encode())

    decoded = binascii.a2b_base64(sns['Signature'])
    result = pubkey.verify_final(decoded)

    if result != 1:
        msg_kwargs = {
            'smtp.subject': 'EC2 Autoscale Signature Error (via Salt Reactor)',
            'smtp.content': (
                'There was an error with the EC2 Signature. '
                'Content received was:\r\n\r\n{0}\r\n').format(
                    pprint.pformat(sns)
                ),
        }
        smtp.send(msg_kwargs, __opts__)
        return {}

    message = json.loads(sns['Message'])
    instance_id = str(message['EC2InstanceId'])

    if 'launch' in sns['Subject'].lower():
        vm_ = __opts__.get('ec2.autoscale', {}).get(str(tag.split('/')[-2]))
        vm_['reactor'] = True
        vm_['instances'] = instance_id
        vm_['instance_id'] = instance_id
        vm_list = []
        for key, value in vm_.iteritems():
            if not key.startswith('__'):
                vm_list.append({key: value})
        # Fire off an event to wait for the machine
        ret = {
            'ec2_autoscale_launch': {
                'runner.cloud.create': vm_list
            }
        }
    elif 'termination' in sns['Subject'].lower():
        ret = {
            'ec2_autoscale_termination': {
                'wheel.key.delete': [
                    {'match': instance_id},
                ]
            }
        }

    return ret
```
This will accept requests from the AWS SNS service to the salt API, verify the message validity and then dispatch an action request to either register a new minion or remove it depending on the subject of the message. Because SNS requires verification of new URL endpoints it is necessary to configure the SMTP system in salt as defined [here](http://docs.saltstack.com/en/latest/ref/modules/all/salt.modules.smtp.html#module-salt.modules.smtp). By adding these lines to the reactor configuration in the master, we will register the endpoints that SNS will use when sending the autoscale messages.
```
#!yaml
reactor:
  - 'salt/netapi/hook/autoscale/web/up':
      - /srv/lta/reactor/ec2-autoscale.sls
  - 'salt/netapi/hook/autoscale/web/down':
      - /srv/lta/reactor/ec2-autoscale.sls
```

The specifications for the cloud instance are set in the master configuration as shown here.
```
#!yaml
ec2.autoscale:
  web:
    provider: aws_provider
    ssh_interface: private_ips
    ssh_username: ubuntu
    minion:
      startup_states: highstate
    grains:
      env: prod
      roles: web-host
```
This will preseed the salt master with a key for the new minion and register a trigger in the salt cloud system to wait for the new minion to come online. Once the master is able to connect to the minion, it will execute the bootstrap routine, setting the minion grains and telling it to run a highstate once the minion daemon starts up. Because the reactor script is calling `tag.split('/')[-2]` when looking up which ec2.autoscale configuration to use, we can easily have multiple autoscale configurations that are triggered dependent on the URL that the request is received on. For instance, by changing the configuration in the reactor file to `'salt/netapi/hook/autoscale/database/up'`, the definition of the instance would be
```
#!yaml
ec2.autoscale:
  database:
    ...
```

There are any number of other things that you may want to do with AWS and SaltStack does a good job of making them easy to automate. With a few changes in pillar data, we can now rapidly and repeatably build out an autoscaled and load balanced application tier inside a VPC.
