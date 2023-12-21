from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckFIPS(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckFIPS, self).__init__(ansible_module, "FIPS", "check_fips")

        self.is_fips_enabled = self.ansible_module.params['fips']

    def process(self):
        if self.is_fips_enabled:
            self.value = 'Enabled'
        else:
            self.value = 'Disabled'
        self.required = "Ansible need to be able to detect FIPS status on the machine"
        self.log_debug("ansible_fips: {}".format(self.is_fips_enabled))

        self.set_state(MapRPrereqCheck.VALID)
