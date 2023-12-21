import os

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckHadoop(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckHadoop, self).__init__(ansible_module, "hadoop", "check_hadoop")
        self.prereq_values = ansible_module.params['prereq_values']['app_names']
        self.app_hadoop = self.prereq_values['hadoop']

    def process(self):
        # Don't run this test on a cloud installation
        if self.is_cloud:
            return

        if os.path.exists("/opt/mapr/installer-lock.file"):
            return

        self.check_exec(self.app_hadoop)
