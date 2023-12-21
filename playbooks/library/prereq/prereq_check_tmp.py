from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckTmp(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckTmp, self).__init__(
            ansible_module,
            "Free space on: {0}".format(ansible_module.params['prereq_values']['tmp']['tmp_dir']),
            "check_tmp")

        self.prereq_values = ansible_module.params['prereq_values']['tmp']
        self.tmp_dir = self.prereq_values['tmp_dir']
        self.tmp_min_size = self.prereq_values['min_size_gb']
        self.tmp_rec_size = self.prereq_values['rec_size_gb']

    def process(self):
        self.check_disk_space_on(self.tmp_dir, self.tmp_min_size, self.tmp_min_size)
