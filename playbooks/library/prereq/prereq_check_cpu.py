from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckCPU(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckCPU, self).__init__(ansible_module, "CPU", "check_cpu")

        self.machine_cpu = self.ansible_module.params['cpu']
        self.cpu_prereq_values = ansible_module.params['prereq_values']['cpu']

    def process(self):
        self.value = self.machine_cpu
        self.required = "One from: {0}".format(self.cpu_prereq_values['architecture'])
        self.log_debug(self.machine_cpu)
        self.log_debug(self.required)

        if self.machine_cpu not in self.cpu_prereq_values['architecture']:
            self.set_state(MapRPrereqCheck.ERROR)
            return

        self.set_state(MapRPrereqCheck.VALID)
