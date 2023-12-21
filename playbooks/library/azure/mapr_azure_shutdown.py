from ansible.module_utils.basic import AnsibleModule
from azure.mgmt.compute import ComputeManagementClient

from ansible.module_utils.mapr_azure import MapRAzure


class MapRAzureShutdown(MapRAzure):
    def __init__(self, this_module):
        super(MapRAzureShutdown, self).__init__(this_module)

    def run(self):
        try:
            self._validate_credentials()
            credentials = self._get_credentials()
            compute_client = ComputeManagementClient(credentials, self.subscription_id)

            virtual_machines = compute_client.virtual_machines.list(self.resource_group)
            for item in virtual_machines:
                if item.tags.get("role") == "MapR Cluster" and item.tags.get("subRole") == "Server Node":
                    compute_client.virtual_machines.deallocate(self.resource_group, item.name)

            self.this_module.exit_json(changed=True,
                msg="Shutdown(deallocate) of virtual machines in resource group {0} started".
                    format(self.resource_group, resource_group=self.resource_group))
        except Exception, e:
            self.this_module.fail_json(msg="Could not shutdown virtual machines in resource group {0}. Reason: {1}".
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

    mapr_delete = MapRAzureShutdown(this_module)
    mapr_delete.run()


main()
