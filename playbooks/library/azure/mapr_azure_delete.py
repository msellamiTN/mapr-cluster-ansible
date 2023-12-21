from ansible.module_utils.basic import AnsibleModule
from azure.mgmt.resource import ResourceManagementClient

from ansible.module_utils.mapr_azure import MapRAzure


class MapRAzureDelete(MapRAzure):
    def __init__(self, this_module):
        super(MapRAzureDelete, self).__init__(this_module)

    def run(self):
        try:
            self._validate_credentials()
            credentials = self._get_credentials()
            resource_client = ResourceManagementClient(credentials, self.subscription_id)
            resource_client.resource_groups.delete(self.resource_group)
            self.this_module.exit_json(changed=True,
                msg="Resource group deletion started", resource_group=self.resource_group)
        except Exception, e:
            self.this_module.fail_json(msg="Could not delete resource group {0}. Reason: {1}".
                format(self.resource_group, str(e)))


def main():
    this_module = AnsibleModule(argument_spec=dict(
        subscription_id=dict(required=False),
        auth_type=dict(required=True),
        client_id=dict(required=False),
        secret=dict(required=False, no_log=True),
        tenant=dict(required=False),
        username=dict(required=False),
        password=dict(required=False, no_log=True),
        resource_group=dict(required=True)))

    mapr_delete = MapRAzureDelete(this_module)
    mapr_delete.run()


main()
