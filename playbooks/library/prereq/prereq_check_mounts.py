import json

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckMounts(MapRPrereqCheck):
    PRESENT = "present."

    def __init__(self, ansible_module):
        super(PrereqCheckMounts, self).__init__(ansible_module, "Mounts", "check_mounts")

        self.mounts = json.loads(ansible_module.params['mounts']) if ansible_module.params['mounts'] else None

    def process(self):
        if self.mounts is None or len(self.mounts) == 0:
            self.required = PrereqCheckMounts.PRESENT + " The fact that the installer found no mounts " + \
                "present, typically indicate that you have a stale NFS mount on /mapr. This node should be " + \
                "rebooted to clear the condition before you continue the install."
            self.value = "stale NFS mount"
            self.set_state(MapRPrereqCheck.ERROR)
        else:
            self.required = ", ".join([d['mount'] for d in self.mounts if 'mount' in d])
            self.value = PrereqCheckMounts.PRESENT
            self.set_state(MapRPrereqCheck.VALID)
