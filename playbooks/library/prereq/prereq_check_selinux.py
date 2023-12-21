from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck, MapRPrereqCheckError


class PrereqCheckSELinux(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckSELinux, self).__init__(ansible_module, "SELinux", "check_selinux")
        self.path = ansible_module.params['prereq_values']['file_path']['selinux']

    def process(self):
        self.required = "turned off. Install will disable it if it is enabled."
        checks = []

        try:
            lines = self.read_lines(self.path)
            # Check if there is line at all.
            lines = filter(lambda line: len(line.strip()) > 0, lines)
            # Remove commented lines
            lines = filter(lambda line: line.strip()[0] != '#', lines)
            # Check every line for 'SELINUX=enforcing'
            checks = map(lambda line: 'SELINUX=enforcing' in line, lines)
        except MapRPrereqCheckError:
            pass

        if True in checks:
            self.message = "SELinux turned on."
            self.value = "On"
            self.set_state(MapRPrereqCheck.WARN)
        else:
            self.set_state(MapRPrereqCheck.VALID)
            self.value = "Off"
