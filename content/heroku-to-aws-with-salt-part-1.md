Title: From Heroku to AWS With SaltStack (Part 1)
Date: 2015-03-24
Category: Operations
Tags: saltstack, operations, automation, aws, git, github

Recently I helped a client move their application from Heroku to AWS while maintaining a similar Git-based workflow. In order to achieve this, I leveraged the power of SaltStack and have been pleased with the results. This is the first in a series of posts explaining the steps that I took to build this system.

For those of you who aren't yet familiar with what SaltStack is, the best way to describe it is as an asynchronous, reactive event bus with different execution layers built on top of it. One such layer is intended for configuration management of your servers, while another is something called the salt reactor, which allows you to define custom reactions to various events.

The first problem tackled was to automate building of the web tier, which involved installing and configuring PHP, Nginx and uWSGI as well as cloning the application code and installing the necessary dependencies. The formulas used for these instances can be found [here](https://github.com/blarghmatey/nginx-formula) and [here](https://github.com/blarghmatey/uwsgi-formula).

Next was setting up a MongoDB replica set with 3 servers and configuring them to speak to each other. One pattern that was incredibly useful for this was to take advantage of the salt `mine` to act as a poor man's DNS. To make this work, add the following to a universally applied `pillar` file.

```YAML

mine_functions:
  network.ip_addrs: [eth0]
  network.get_hostname: []
```

This tells each minion to send the IP address for their `eth0` network interface, as well as their hostname. With this information, it becomes possible to add the following to a base state:

```jinja
{% for id, addr_list in salt['mine.get']('env:{0}'.format(grains['env']), 'network.ip_addrs', expr_form='grain').items() %}
{% if id == grains['id'] %}
self-host-entry:
  host.present:
    - ip: 127.0.0.1
    - names:
        - {{ id }}
{% else %}
{{ id }}-host-entry:
  host.present:
    - ip: {{ addr_list|first() }}
    - names:
        - {{ id }}
{% endif %}
{% endfor %}
```

This stores the hostname and ip address of all of the other minions in a given environment to the `/etc/hosts` file of the minion where the state is executed. This results in easy hostname resolution of the other minions in the deployment without having to manage any DNS infrastructure. Now that host discovery has been taken care of, it becomes trivial to dynamically configure the database connections for the application servers. It also makes it possible to use the following Jinja logic to configure the replica set using only the information available from Salt.

```jinja
{% if 'mongo_primary' in grains['roles'] %}
{% set replset_config = {'_id': salt['pillar.get']('mongodb:replica_set:name', 'repset0'), 'members': []} %}
{% set member_id = 0 %}
{% for id, addrs in salt['mine.get']('roles:mongodb_server', 'network.get_hostname', expr_form='grain').items() %}
{% do replset_config['members'].append({'_id': member_id, 'host': id}) %}
{% set member_id = member_id + 1 %}
{% endfor %}
```

Now that the application and database are configured, we need to manage application deployment using `git`. To do this we take advantage of the SaltStack [reactor](http://docs.saltstack.com/en/latest/topics/reactor/) system. This lets us execute specific actions in response to events that are triggered on the Salt master. In addition to the reactor system, we need to make sure that Salt API is installed and active.

The deployment pipeline is triggered from GitHub webhooks sent to the Salt API, so it is necessary to disable authentication. The configuration that I used is:
```YAML
rest_cherrypy:
  port: 8000
  ssl_crt: /etc/pki/{{ tls_dir }}/certs/{{ common_name }}.crt
  ssl_key: /etc/pki/{{ tls_dir }}/certs/{{ common_name }}.key
  webhook_disable_auth: True
```
This uses pillar data to define the location and name of your SSL certificate and key, as well as disabling HTTP basic auth for the API. By disabling authentication on the API endpoint, it becomes necessary to handle validation of all requests in the reactor function. Fortunately, GitHub sends all of their webhooks with an HMAC signature.

The verification and deployment of code from the webhook is handled by a custom reactor definition:
```py
import hashlib
import hmac


def run():
    '''Verify the signature for a Github webhook and deploy the
    appropriate code'''
    _, signature = data['headers'].get('X-Hub-Signature').split('=')
    body = data['body']
    target = tag.split('/')[-1]
    key = __opts__.get('github', {}).get('webhook-key')
    computed_signature = hmac.new(key, body,
                                  hashlib.sha1).hexdigest()
    # signature_match = hmac.compare_digest(computed_signature, signature)
    if computed_signature == signature:
        return {
            'github_webhook_deploy': {
                'local.state.sls': [
                    {'tgt': 'roles:{0}'.format(target)},
                    {'expr_form': 'grain'},
                    {'arg': ['{0}.deploy'.format(target), 'prod']},
                ]
            }
        }
    else:
        return {}
```
This uses the python DSL for state files which greatly simplifies the representation of the logic involved. The first thing it does is to check that the HMAC signature is valid by computing what it should be based on a secret key that is defined in the master's configuration and the body of the webhook request. If the signatures match, then the function returns a python dictionary consisting of a state definition that is to be executed. In this case, the state file is one that handles the deployment of the application code. The actual deployment is simply cloning the latest code from git to the servers whose grains match the target role which is determined based on the last portion of the URL to which the webhook was sent (`php-web-host`). The cloned source is then symlinked to `current` in the deployment directory, after which the Nginx and uWSGI servers are restarted.

To make this reactor function active, simply add this to the master configuration file:
```YAML
reactor:
  - 'salt/netapi/hook/deploy/*':
      - /srv/lta/reactor/code-deploy.sls
```
This translates to an API endpoint of `https://<salt_master_url>/api/hook/<target_role>`.

Now, it is possible to have a git-based workflow similar to what my client had gotten used to with Heroku, with the additional benefit of being able to define specific actions that will trigger the webhook. This adds greater flexibility without any unnecessary additional complexity.

In the [next post](/from-heroku-to-aws-with-saltstack-part-2.html) I explain how I managed creation and scaling of the EC2 nodes with [salt-cloud](http://docs.saltstack.com/en/latest/topics/cloud/) and the reactor system.
