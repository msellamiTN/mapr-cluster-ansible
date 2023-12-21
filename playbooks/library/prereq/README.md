#### Adding new prereq
To add a new check just copy the existing prereq check and change these:
* class name. the class name should be unique within this folder
* `super()` call need to use your new class name.
* Change two str in `__init__` call to correctly describe new prereq check. First, str is used in UI, so the user will see it and it should describe this prereq check.
* Remove everything after `def process(self):` and write your own. Use old class as reference `self.set_state()` 
should be executed in all possible scenarios.

#### How to pass value from ansible to the prereq check
Let`s say we need new value from ansible facts to be passed to our prereq check. 
To do so we need to do a few changes in multiple files.

##### check.yml
At the bottom add a new line with the name of the value you want to pass and pass the value as is with Jinja:
```
...
        mysql_host='{{ shared_mysql_host }}'
        mysql_socket='{{ mysql_socket }}'
        fresh_install='{{ is_fresh_install }}'
        fips='{{ ansible_fips }}'
```
The last line is added. The format is <value_name> = '{{ name of the fact in ansible_facts }}'
Example of ansible facts:
```
"ansible_facts": {
        "ansible_all_ipv4_addresses": [
            "192.168.75.241"
        ], 
        "ansible_all_ipv6_addresses": [
            "fe80::cf84:480f:6da5:cde0"
        ], 
        "ansible_apparmor": {
            "status": "disabled"
        }, 
        "ansible_architecture": "x86_64", 
        "ansible_bios_date": "04/01/2014",
...
```
To pass ansible_bios_date we need to add a line to check.yml like this:
```
...
        mysql_host='{{ shared_mysql_host }}'
        mysql_socket='{{ mysql_socket }}'
        fresh_install='{{ is_fresh_install }}'
        fips='{{ ansible_fips }}'
        bios_date='{{ ansible_bios_date }}'
```
#### mapr_prereq.py
Almost the same need to be done in mapr_prereq.py. But we also need to correctly specify the type of value we pass.
Let`s take an ansible_bios_date as an example.
```
...
                           mysql_host=dict(type='str'),
                           mysql_socket=dict(type='str'),
                           fresh_install=dict(default=False, type='bool'),
                           fips=dict(default=False, type='bool'),
                           bios_date=dict(default='', type='str'),
                           ))
```
AnsibleModule expects all values to be passed as dictionaries with type and default inside the dictionary.
It will pick up the value from check.yml on execution.
#### prereq check
Inside the prereq check we can get the value like this:
```
from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckFIPS(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckFIPS, self).__init__(ansible_module, "FIPS", "check_fips")

        self.is_fips_enabled = self.ansible_module.params['fips']
        self.bios_date = self.ansible_module.params['bios_date']
...
```

Basically, we need to get the value from ansible in check.yml, pass it to mapr_prereq.py, code mapr_prereq.py to use it.
Since all prereqs are inherited from mapr_prereq.py - we can use those values in the prereq code.
