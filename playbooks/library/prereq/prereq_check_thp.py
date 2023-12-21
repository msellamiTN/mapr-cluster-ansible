from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck, MapRPrereqCheckError


class PrereqCheckTHP(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckTHP, self).__init__(ansible_module, "Transparent Huge Pages", "check_thp")
        self.paths = ansible_module.params['prereq_values']['os']['thp']

    def process(self):
        self.required = "turned off. Having THP enabled degrades performance."
        line = ""
        checks = []
        for path in self.paths:
            try:
                line = self.read_firstline(path)
                break
            except MapRPrereqCheckError:
                pass

        if not line:
            self.required = "state is indetermined. Unable to determine the setting of THP. " + \
                "Having THP enabled degrades performance."
            self.value = "Unknown"
            self.set_state(MapRPrereqCheck.WARN)

        keyswords = ['[never]', 'never']  # If THP turned off.
        # Check that keywords in line
        checks = map(lambda key: key in line, keyswords)
        if True in checks:
            self.value = "Off"
            self.set_state(MapRPrereqCheck.VALID)
        else:  # If THP on.
            self.message = "THP turned on."
            self.value = "On"
            self.set_state(MapRPrereqCheck.WARN)
