from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckSwap(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckSwap, self).__init__(ansible_module, "SWAP", "check_swap")

        self.machine_ram = self.ansible_module.params['ram']
        self.machine_swap = self.ansible_module.params['swap']
        self.prereq_values = ansible_module.params['prereq_values']['disk']
        self.disk_swap_recommended_swap = self.prereq_values['swap_required']

    def process(self):
        ram_in_gb = MapRPrereqCheck.to_gb(self.machine_ram)
        swap_in_gb = MapRPrereqCheck.to_gb(self.machine_swap)
        required_by_ram = 0.1 * ram_in_gb

        self.value = "{0} GB".format(swap_in_gb)

        if swap_in_gb < required_by_ram and swap_in_gb < self.disk_swap_recommended_swap:
            self.required = "at least {0} GB, optimal at least {1}".format(self.disk_swap_recommended_swap, required_by_ram)
            self.set_state(MapRPrereqCheck.WARN)
        else:
            self.required = "{0} GB".format(required_by_ram)
            self.set_state(MapRPrereqCheck.VALID)
