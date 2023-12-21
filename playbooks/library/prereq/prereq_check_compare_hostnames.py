from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCompareHostnames(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCompareHostnames, self).__init__(ansible_module, "Shortname", "compare_hostnames")

        self.fqdn = ansible_module.params['fqdn']
        self.nodename = ansible_module.params['nodename']

    def process(self):
        # Do not run this test on a cluster probe
        if self.cluster_probe:
            return

        self.value = "{0}".format(self.nodename)
        self.required = "{0}".format(self.fqdn)
        hostnames_valid = self.fqdn.lower().find(self.nodename.lower()) != -1

        if hostnames_valid:
            self.message = ""
            self.set_state(MapRPrereqCheck.VALID)
        else:
            self.message = "Short Hostname must be part of FQDN."
            self.set_state(MapRPrereqCheck.WARN)
