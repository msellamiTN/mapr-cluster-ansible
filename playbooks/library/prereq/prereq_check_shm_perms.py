from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckShmPerms(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckShmPerms, self).__init__(ansible_module, "Permissions for {0}".format(ansible_module.params['prereq_values']['shm']['shm_dir']), "check_shm_perms")
        self.prereq_values = ansible_module.params['prereq_values']['shm']
        self.shm_perm = self.prereq_values['shm_perm']
        self.shm_dir = self.prereq_values['shm_dir']

    def process(self):
        self.check_perms(self.shm_dir, self.shm_perm)
