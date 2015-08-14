Title: Keeping Secrets With SaltStack
Date: 2015-03-30
Category: Operations
Tags: saltstack, operations, secrets, redis

In configuration management, one of the hardest problems is figuring out how to manage sensitive data. I think we can all agree that storing that data in your source control system is a bad idea, but there is less consensus around what is the _right_ answer. I don't pretend to know what the best solution is to this problem, but I would like to share an approach that worked well for me when using SaltStack.

#Redis as a Pillar Store

The pillar system in salt is incredibly flexible and allows for taking advantage of alternative backends to store and retrieve your data. I decided to take advantage of this by writing a pair of scripts to synchronize sensitive data into a Redis instance running on my salt master. The script that I use on my development machine looks like this:
```python
import redis
import yaml
import argparse


parser = argparse.ArgumentParser(
    description='Utility for synchronizing pillar data in Redis')
parser.add_argument('-H', '--host', dest='host', default='localhost')
parser.add_argument('-p', '--port', dest='port', default=6379)
parser.add_argument('-d', '--db', dest='db', default=0)
parser.add_argument('-P', '--password', dest='password', default=None)
parser.add_argument('-f', '--file', dest='filename', default='pillar.yaml',
                    help='The file that will be used for synchronizing')
parser.add_argument('extra_params', nargs=argparse.REMAINDER,
                    help='Extra parameters to be passed in. key=value format')

args = parser.parse_args()
extra_args = {k: v for k, v in (arg.split('=') for arg in args.extra_params)}
client = redis.Redis(host=args.host, port=args.port, db=args.db,
                     password=args.password, **extra_args)

yaml_data = yaml.load(open(args.filename, 'r'))

try:
    for key, value in yaml_data.items():
        client.set(key, value)
except AttributeError:
    print("There is no YAML data in this file")

redis_data = {}
for key in client.keys():
    rkey = key.decode('utf8')
    rval = client.get(key)
    try:
        redis_data[rkey] = eval(rval)
    except (NameError, SyntaxError):
        redis_data[rkey] = rval.decode('utf8')

with open(args.filename, 'w') as pillar:
    yaml.dump(redis_data, pillar, default_flow_style=False)
```
This allows you to write out your pillar data in the same yaml syntax that you are used to while keeping the contained data out of your source control system.

This is a command line script that allows you to pass connection parameters for your Redis instance and synchronizes the contents of the given database with the specified file. By default the script looks for a file called `pillar.yaml' (overridden by a command line parameter) and parses it using the pyymal library. The data in the file is transformed into a Python dictionary and then uploaded to Redis. The data in the Redis DB is then fetched, converted into YAML and written back out to the pillar file. One advantage to this approach is that it can be easily added to your workflow by adding it as a pre- or post-commit hook.

On the SaltStack side I wrote a complementary script that fetches the data from the specified Redis instance and returns it as a pillar dictionary to be used at execution time.
```python
import redis


def run():
    client = redis.Redis(host='{{ redis_host }}', db={{ redis_db }},
                         password='{{ redis_password }}')
    keys = client.keys()
    data = {}
    for key in keys:
        value = client.get(key)
        try:
            data[key] = eval(value)
        except (NameError, SyntaxError):
            data[key] = value
    return data
```

#Possible Improvements

One change that I have considered making to this system is to use CouchDB as the data storage for the pillar data instead of Redis. The benefit of this change is that it would then provide automatic versioning of the data through the built in document revisions that CouchDB uses for its MVCC (Multi-Version Concurrency Control) system. A potential disadvantage is that installing CouchDB requires bringing in a number of Erlang dependencies.

Another area in which this solution is somewhat lacking is that it doesn't have a good way of targeting the minions that will receive the various bits of stored data.

Any suggestions on how this approach could be improved are welcome in the comments.
