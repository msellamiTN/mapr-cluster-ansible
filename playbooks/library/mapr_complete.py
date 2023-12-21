from ansible.module_utils.basic import AnsibleModule

from ansible.module_utils.mapr_base import MapRBase


class MapRComplete(MapRBase):
    def __init__(self, module):
        self.module = module

    @staticmethod
    def cmd_to_msg(_cmd):
        return "{0}{1} successful".format(_cmd[0].upper(), _cmd[1:])

    def run(self):
        cmd = self.module.params["command"]
        cmd = cmd if cmd in ["check", "uninstall", "upgrade", "rolling_upgrade", "provision"] else "install"
        self.module.exit_json(changed=True, msg=MapRComplete.cmd_to_msg(cmd), command=cmd)


def main():
    module = AnsibleModule(argument_spec=dict(command=dict(default="install")))
    mapr_complete = MapRComplete(module)
    mapr_complete.run()


if __name__ == '__main__':
    main()
