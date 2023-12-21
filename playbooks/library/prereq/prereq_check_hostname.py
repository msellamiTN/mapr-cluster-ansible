from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck
from ansible.module_utils import six


class PrereqCheckHostname(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckHostname, self).__init__(ansible_module, "Hostname", "check_hostname")

        self.fqdn = ansible_module.params['fqdn']

    def process(self):
        outdata, _, _ = self.log_run_cmd("getent hosts {0}".format(self.getfqdn()))

        self.required = self.fqdn
        v_to_check = "amazonaws.com"

        if v_to_check in outdata:
            self.value = "Amazon EC2 external address"
            # TODO: In the original test self.failures was not set to True. Why???
            self.set_state(MapRPrereqCheck.ERROR)
        elif self.fqdn in outdata:
            self.value = self.fqdn
            self.set_state(MapRPrereqCheck.VALID)
        else:
            self.value = outdata
            self.message = "Cannot resolve hostname {0}. Add it to /etc/hosts and/or DNS." \
                " This host needs to be able to resolve names for all other hosts in" \
                " cluster as well".format(self.fqdn)
            self.set_state(MapRPrereqCheck.ERROR)
