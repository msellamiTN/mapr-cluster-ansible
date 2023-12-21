from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckShmOwner(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckShmOwner, self).__init__(ansible_module, "Ownerhip of {0}".format(ansible_module.params['prereq_values']['shm']['shm_dir']), "check_shm_owner")
        self.prereq_values = ansible_module.params['prereq_values']['shm']
        self.shm_dir = self.prereq_values['shm_dir']
        self.shm_uid = self.prereq_values['shm_uid']

    def process(self):
        self.check_owner(self.shm_dir, self.shm_uid)

