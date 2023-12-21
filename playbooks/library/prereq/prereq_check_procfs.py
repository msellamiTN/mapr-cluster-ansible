from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckProc(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckProc, self).__init__(ansible_module, "Kernel Cfg", "check_values_procfs")
        self.PROC_PATH = ansible_module.params['prereq_values']['os']['procfs']

    def process(self):
        self.required = " not optimal. "
        self.value = "Optimal"
        for prop in self.PROC_PATH:
                path = prop.get("path")
                res = self.read_firstline(path)
                exp = prop.get("exp")
                if res != exp:
                    self.required += "{0!s} should be set to {1!s}, but is set to {2!s}. ".\
                                    format(path, exp, res)
                    self.value = "Sub optimal"
        if self.value == "Sub optimal":
            self.required += " The installer will reset these kernel settings " + \
                "to what is deemed optimal for the MapR software during the install."
            self.set_state(MapRPrereqCheck.WARN)
        else:
            self.required = "optimal."
            self.set_state(MapRPrereqCheck.VALID)
