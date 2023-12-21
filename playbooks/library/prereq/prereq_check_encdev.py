from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck, MapRPrereqCheckError
from ansible.module_utils import six

class PrereqCheckEBLKD(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckEBLKD, self).__init__(ansible_module, "Encrypted devices", "check_blkd")
        self.path = ansible_module.params['prereq_values']['file_path']['crypttab']

    def process(self):
        self.required = "not present"

        enabled = False
        try:
            lines = self.read_lines(self.path)
            lines = filter(lambda line: len(line.strip()) > 0, lines)
            lines = filter(lambda line: line.strip()[0] != '#', lines)
            if six.PY3:
                lines = list(lines)
            enabled = len(lines) > 0
        # File can be absent, so just pass errors.
        # TODO: if cluster present and crypttab present = VALID
        except MapRPrereqCheckError:
            pass
        if enabled:
            self.value = "present"
            self.required += " This is just a heads up that electing to use encrypted " + \
                "disks with MapR software does incur a performance cost"
            self.set_state(MapRPrereqCheck.WARN)
        else:
            self.value = "not present"
            self.set_state(MapRPrereqCheck.VALID)
