from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckRoot(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckRoot, self).__init__(ansible_module, "Free space on: {0}".format(ansible_module.params['prereq_values']['disk']['root']), "check_root")

        self.prereq_values = ansible_module.params['prereq_values']['disk']
        self.disk_root = self.prereq_values['root']
        self.disk_root_min_size = self.prereq_values['root_min_size']
        self.disk_root_rec_size = self.prereq_values['root_recommended_size']

    def process(self):
        self.check_disk_space_on(self.disk_root, self.disk_root_rec_size, self.disk_root_min_size)
