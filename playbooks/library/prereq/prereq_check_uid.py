import pwd

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckUID(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckUID, self).__init__(ansible_module, "UID", "check_uid")

        self.cluster_admin_uid = ansible_module.params["admin_uid"]

    def process(self):
        self.value = ""
        self.required = self.cluster_admin_uid

        try:
            usr = pwd.getpwuid(self.cluster_admin_uid)
            if usr.pw_name == self.admin_user:
                self.value = str(self.cluster_admin_uid)
                self.set_state(MapRPrereqCheck.VALID)
            else:
                self.value = str(usr.pw_uid)
                self.set_state(MapRPrereqCheck.ERROR)
        except KeyError:
            if self.create_admin:
                try:
                    usr = pwd.getpwnam(self.admin_user)
                    if usr.pw_uid == self.cluster_admin_uid:
                        self.value = self.cluster_admin_uid
                        self.set_state(MapRPrereqCheck.VALID)
                    else:
                        self.value = str(usr.pw_uid)
                        self.set_state(MapRPrereqCheck.ERROR)
                except KeyError:
                    self.value = "-"
                    self.set_state(MapRPrereqCheck.VALID)
            else:
                self.value = "absent"
                self.set_state(MapRPrereqCheck.ERROR)
