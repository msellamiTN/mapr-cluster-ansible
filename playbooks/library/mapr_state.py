from ansible.module_utils.basic import AnsibleModule

from ansible.module_utils.mapr_base import MapRBase


class MapRState(MapRBase):
    def __init__(self, module):
        self.module = module

    def run(self):
        self.module.exit_json(changed=False, state=self.module.params.get('state'))


def main():
    module = AnsibleModule(argument_spec=dict(state=dict(required=True)))
    MapRState(module).run()


main()
