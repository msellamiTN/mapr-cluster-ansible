import grp

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckGID(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckGID, self).__init__(ansible_module, "GID", "check_gid")

        self.cluster_admin_gid = ansible_module.params["admin_gid"]
        self.admin_group = ansible_module.params["admin_group"]

    def process(self):
        self.value = ""
        self.required = self.cluster_admin_gid

        try:
            group = grp.getgrgid(self.cluster_admin_gid)
            if group.gr_name == self.admin_group:
                self.value = self.cluster_admin_gid
                self.set_state(MapRPrereqCheck.VALID)
            else:
                self.value = str(group.gr_name)
                self.set_state(MapRPrereqCheck.ERROR)
        except KeyError:
            if self.create_admin:
                self.value = str("-")
                self.set_state(MapRPrereqCheck.VALID)
            else:
                self.value = str("absent")
                self.set_state(MapRPrereqCheck.ERROR)
