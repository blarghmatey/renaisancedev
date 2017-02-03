Title: Discovering MongoDB with Consul
Date: 2017-02-03
Category: Operations
Tags: Operations, Service Discovery

In order to build flexible and maintainable cloud infrastructure we need a way to connect services together with minimal effort. For a long time DNS has been the way to do that, but it also poses a different set of problems. How do you keep the DNS entries up to date? How do you make sure that the instances that are registered in DNS are actually healthy and able to serve traffic?

[Consul]() from Hashicorp is a modern answer to these problems that is being widely adopted by teams of all sizes. It is a service discovery layer for your datacenter, as well as being a distributed key-value store and able to perform cross-datacenter replication and discovery. One of the wonderful things about it is the fact that the service discovery layer can be used via a built-in DNS interface. Services that are registered in Consul can have an associated health-check which will cause a failing instance to be removed from the list of DNS entries for that service. All-in-all it's a pretty great system that is definitely worth considering if you haven't already started using it yourself.

### The Problem

While re-architecting an ailing environment so that it would be easier to maintain and scale I decided to use Consul as the local DNS provider. Everything was going well until I started trying to access a MongoDB replica set through the DNS records that were being retrieved through Consul. For some reason I kept getting errors in my client logs stating that the connection to MongoDB was failing because the instance being connected to wasn't the master.

To try to remedy the failure I added the replica set configuration and the read preference to the connection parameters in the hopes that it would allow the client to properly discover the master node. No matter how I tweaked the parameters and checked and double checked the DNS records I couldn't quite figure out where the problem was. After digging deeper and deeper into the problem I finally realized why I was having the issue.

Because the clients were using a connection of the form `mongodb://mongodb.service.consul:27017/database` they were just doing round-robin DNS lookups of the MongoDB servers. Sometimes they would win the game of roulette and reach a master node but other times they would hit a secondary node instead. Even if you have the read preference set to something like `secondaryPreferred` the client driver still needs to connect to the master first in order to be able to properly enumerate the replica set. Because of the intermittent nature of the failures the way to solve the problem wasn't apparent at first.

### The Solution

Once I fully understood what the failure was, the solution became obvious. Since you can register arbitrary service names in Consul and associate a variety of different health checks, all I had to do was set one up that would only point to the node that was currently the master. In order to make that work I wrote a scripted health check that would run the following script every 10 seconds:

```bash
#!/bin/bash
ISMASTER=$(/usr/bin/mongo --quiet --eval 'db.isMaster().ismaster')
if [ "$ISMASTER" = "true" ]
then
    exit 0
else
    exit 2
fi
```

I then configured the Consul agent on the MongoDB instances with this service definition:

```JSON
{
  "services": [
    {
      "check": {
        "interval": "10s",
        "script": "/consul/scripts/mongo_is_master.sh"
      },
      "name": "mongodb-master",
      "port": 27017,
      "tags": [
        "mongodb",
        "master"
      ]
    }
  ]
}
```

Whichever instance is passing that check will be registered as the `mongodb-master.service.consul` DNS record in Consul. That means that the clients just need to be configured to connect to `mongodb://mongodb-master.service.consul:27017/database?replicaSet=rs0&readPreference=primaryPreferred` and everyone will be happy.

### Conclusion

This was an irritating problem that finally yielded to extended debugging. Hopefully I have been able to save someone else the pain of discovery by writing this post. If that someone is you then leave a comment and let me know. Thanks for reading!
