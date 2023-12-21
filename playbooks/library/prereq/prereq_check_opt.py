import os

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckOpt(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckOpt, self).__init__(ansible_module, "Free space on: {0}".format(ansible_module.params['prereq_values']['disk']['directory']), "check_opt")
        self.prereq_values = ansible_module.params['prereq_values']['disk']
        self.disk_directory = self.prereq_values['directory']
        self.disk_min_size = self.prereq_values['min_size']
        self.disk_recommended_size = self.prereq_values['recommended_size']
        self.disk_recom_cloud_size = self.prereq_values['recommended_cloud_size']
        self.disk_mapr_dir = os.path.join(self.disk_directory, self.prereq_values['install_dir'])

    def process(self):
        if self.is_cloud:
            recommended_size = self.disk_recom_cloud_size
        else:
            recommended_size = self.disk_recommended_size

        if os.path.isdir(self.disk_mapr_dir):
            directory = self.disk_mapr_dir
            self.name = "Free {0}".format(self.disk_mapr_dir)
        else:
            directory = self.disk_directory

        self.check_disk_space_on(directory, recommended_size, self.disk_min_size)
