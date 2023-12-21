import os
from shutil import Error
import shutil
from ansible.module_utils.basic import AnsibleModule

from ansible.module_utils.mapr_base import MapRBase


class MapROffload(MapRBase):
    def __init__(self, module):
        self.module = module
        self.from_dir = module.params["from_dir"]
        self.to_dir = module.params["to_dir"]
        self.symlinks = module.params["symlinks"]

    def run(self):
        if not os.path.exists(self.from_dir):
            self.module.fail_json(
                msg="from_dir directory does not exist", from_dir=self.from_dir)
        if os.path.exists(self.to_dir):
            self.module.fail_json(
                msg="to_dir directory already exists", to_dir=self.to_dir)

        try:
            shutil.copytree(self.from_dir, self.to_dir, self.symlinks)
        except Error, e:
            self.module.fail_json(
                msg="Could not copy {0}, {1}".format(self.from_dir, str(e)))

        try:
            shutil.rmtree(self.from_dir)
        except Exception as e:
            self.module.fail_json(
                msg="Could not remove {0}, {1}".format(self.from_dir, str(e)))

        try:
            os.symlink(self.to_dir, self.from_dir)
        except Exception as e:
            self.module.fail_json(
                msg="Could not create symlink from {0} to {1}, {2}".
                    format(self.from_dir, self.to_dir, str(e)))

        self.module.exit_json(changed=True,
            msg="Successfully offloaded {0} to {1}".format(self.from_dir,
                self.to_dir),
            from_dir=self.from_dir,
            to_dir=self.to_dir)


def main():
    module = AnsibleModule(argument_spec=dict(
        from_dir=dict(required=True),
        to_dir=dict(required=True),
        symlinks=dict(required=False, default=False, type='bool')))

    mapr_complete = MapROffload(module)
    mapr_complete.run()


main()
