import time

from ansible.module_utils.basic import AnsibleModule
from azure.mgmt.compute import ComputeManagementClient

from ansible.module_utils.mapr_azure import MapRAzure


class MapRAzureStartup(MapRAzure):
    def __init__(self, this_module):
        super(MapRAzureStartup, self).__init__(this_module)

    def run(self):
        try:
            self._validate_credentials()
            credentials = self._get_credentials()
            compute_client = ComputeManagementClient(credentials, self.subscription_id)

            # Get a list of VMs that need to be running
            virtual_machines = compute_client.virtual_machines.list(self.resource_group)
            starting_vms = set()
            for item in virtual_machines:
                if item.tags.get("role") == "MapR Cluster" and item.tags.get("subRole") == "Server Node":
                    # Start the selected VM
                    compute_client.virtual_machines.start(self.resource_group, item.name)
                    starting_vms.add(item.name)

            # Wait until all the VMs are started or we timeout
            success = False
            for i in range(0, 60):
                started_vms = set()
                time.sleep(5)

                for starting_vm in starting_vms:
                    vm = compute_client.virtual_machines.get(self.resource_group, starting_vm, expand='instanceView')

                    for status in vm.instance_view.statuses:
                        # This server is running, add it to the set of started vms
                        if status.code == "PowerState/running":
                            started_vms.add(starting_vm)

                # If the starting and started vm sets are the same size then everything is running, success
                if len(starting_vms) == len(started_vms):
                    success = True
                    break

            if not success:
                self.this_module.fail_json(msg="Could not start vms {0} in resource group {1} after waiting the specified time"
                    .format(str(starting_vms), self.resource_group))
            else:
                self.this_module.exit_json(changed=True,
                    msg="Startup of virtual machines in resource group {0} has completed"
                        .format(self.resource_group, resource_group=self.resource_group))
        except Exception, e:
            self.this_module.fail_json(msg="Could not start virtual machines in resource group {0}. Reason: {1}".
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

    mapr_delete = MapRAzureStartup(this_module)
    mapr_delete.run()


main()
