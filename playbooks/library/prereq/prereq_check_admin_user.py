import pwd

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckAdminUser(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckAdminUser, self).__init__(ansible_module, "Cluster Admin", "check_admin_user")

    def process(self):
        # Don't run this test if create admin is true
        if self.create_admin:
            return

        self.required = "present"
        self.value = self.admin_user

        try:
            pwd.getpwnam(self.admin_user)
            self.set_state(MapRPrereqCheck.VALID)
        except KeyError:
            self.value = "absent"
            self.set_state(MapRPrereqCheck.ERROR)
