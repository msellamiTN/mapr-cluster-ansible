import os

from os.path import expanduser
from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckHome(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckHome, self).__init__(ansible_module, "Home Dir", "check_home")

        self.security = ansible_module.params["security"]

    def process(self):
        self.required = "present"
        homedir = expanduser("~{0}".format(self.admin_user))

        if not self.create_admin:
            if os.path.exists(homedir):
                self.value = homedir
                self.set_state(MapRPrereqCheck.VALID)
            elif not self.security:
                self.value = "optional"
                self.set_state(MapRPrereqCheck.VALID)
            else:
                self.value = "absent"
                self.set_state(MapRPrereqCheck.ERROR)
        else:
            self.value = homedir
            self.set_state(MapRPrereqCheck.VALID)
