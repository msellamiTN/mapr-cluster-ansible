from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckTmpPerms(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckTmpPerms, self).__init__(
            ansible_module,
            "Permissions for {0}".format(ansible_module.params['prereq_values']['tmp']['tmp_dir']),
            "check_tmp_perms")

        self.prereq_values = ansible_module.params['prereq_values']['tmp']
        self.tmp_dir = self.prereq_values['tmp_dir']
        self.tmp_prm = self.prereq_values['req_perm']

    def process(self):
        self.check_perms(self.tmp_dir, self.tmp_prm)
