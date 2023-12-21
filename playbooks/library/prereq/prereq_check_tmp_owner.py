from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckTempOwner(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckTempOwner, self).__init__(
            ansible_module,
            "Ownerhip of {0}".format(ansible_module.params['prereq_values']['tmp']['tmp_dir']),
            "check_tmp_owner")

        self.prereq_values = ansible_module.params['prereq_values']['tmp']
        self.tmp_dir = self.prereq_values['tmp_dir']
        self.tmp_uid = self.prereq_values['uid']

    def process(self):
        self.check_owner(self.tmp_dir, self.tmp_uid)
