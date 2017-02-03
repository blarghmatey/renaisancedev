Title: SaltStack Pillar Key Surprise
Date: 2016-03-01
Category: Operations
Tags: saltstack

So, at my new job I have the good fortune of being able to use SaltStack to rebuild our ailing infrastructure. As part of this work, I am writing a formula to build a salt master. Naturally, I decided that the top-level key in the pillar data should be `master`. Makes sense, right? Unfortunately it seems that is a special key in the salt namespace and so the data contained under that key was not being properly rendered to the state files. This didn't surface until I was trying to dynamically populate keys and values for the `tls.generate_self_signed_cert` module and none of the values in the pillar were being passed in. After liberal use of `salt-call --local -l debug state.show_highstate` and `salt-call --local -l debug pillar.items` I realized my folly. Changing the top-level key to be `salt_master` instantly fixed my issues and allowed me to proceed unencumbered by such nefarious, silent failures.
