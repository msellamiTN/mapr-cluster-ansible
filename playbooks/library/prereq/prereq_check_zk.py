import os

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckZooKeeper(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckZooKeeper, self).__init__(ansible_module, "ZooKeeper", "check_zk")
        self.fresh_install = self.ansible_module.params['fresh_install']

    def process(self):
        # Don't run this test on a cloud installation
        if self.is_cloud:
            return

        if os.path.exists("/opt/mapr/installer-lock.file"):
            return

        if self.fresh_install:
            res, code, err = self.log_run_cmd("systemctl is-active -q mapr-zookeeper")
            if code == 0:
                self.value = "mapr-zookeeper found and running on fresh install. This is not allowed"
                self.required("mapr-zookeeper should not exist on fresh install")
                self.set_state(MapRPrereqCheck.ERROR)
                return

        self.value = "Not a fresh installation. Skipped"

        self.set_state(MapRPrereqCheck.VALID)

