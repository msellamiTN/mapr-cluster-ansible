from ansible.module_utils.basic import AnsibleModule
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import DeploymentMode

from ansible.module_utils.mapr_azure import MapRAzure


class MapRAzureExtend(MapRAzure):
    def __init__(self, this_module):
        super(MapRAzureExtend, self).__init__(this_module)
        self.admin_username = this_module.params.get("admin_username")
        self.admin_password = this_module.params.get("admin_password")
        self.mapr_password = this_module.params.get("mapr_password")
        self.cluster_name = this_module.params.get("cluster_name")
        self.deployment_name = this_module.params.get("deployment_name")
        self.node_count_param = this_module.params.get("node_count_param")
        self.admin_password_param = this_module.params.get("admin_password_param")
        self.mapr_password_param = this_module.params.get("mapr_password_param")
        self.add_count = this_module.params.get("add_count")
        self.resource_client = None
        self.compute_client = None
        self.network_client = None

    @staticmethod
    def _from_original(parameters):
        new_params = dict()

        for old_param in parameters:
            value_dict = dict()

            if 'value' in parameters[old_param]:
                value_dict['value'] = parameters[old_param]['value']
                new_params[old_param] = value_dict

        return new_params

    def run(self):
        fp = open("/tmp/scottdebug.txt", "w")
        try:
            self._validate_credentials()
            credentials = self._get_credentials()
            self.resource_client = ResourceManagementClient(credentials, self.subscription_id)
            self.compute_client = ComputeManagementClient(credentials, self.subscription_id)
            self.network_client = NetworkManagementClient(credentials, self.subscription_id)
            fp.write("Retrieved all clients\n")

            existing_ips, existing_count = self._get_private_ips()
            total_count = existing_count + self.add_count
            fp.write("got count\n")

            deployment = self.resource_client.deployments.get(self.resource_group, self.deployment_name)
            deployment.properties.parameters[self.node_count_param]['value'] = total_count

            if self.admin_password is not None:
                deployment.properties.parameters[self.admin_password_param]['value'] = self.admin_password
                fp.write("Set admin password\n")

            deployment.properties.parameters[self.mapr_password_param]['value'] = self.mapr_password
            fp.write("Set mapr password\n")

            new_deployment_name = self._get_new_deployment_name()
            fp.write("Got deployment name\n")
            template = self.resource_client.deployments.export_template(self.resource_group, self.deployment_name)
            fp.write("Exported template\n")
            deployment_parameters = MapRAzureExtend._from_original(deployment.properties.parameters)

            deployment_properties = {
                'mode': DeploymentMode.incremental,
                'template': template.template,
                'parameters': deployment_parameters
            }

            fp.write("calling create/update\n")
            deployment_async_operation = self.resource_client.deployments.create_or_update(self.resource_group, new_deployment_name,
                                                                                           deployment_properties)
            deployment_async_operation.wait()
            fp.write("done create/update\n")

            all_ips, all_count = self._get_private_ips()
            new_ips = self._get_new_private_ips(existing_ips, all_ips)
            fp.write("Got IPs\n")

            self.this_module.exit_json(changed=True,
                msg="Deployment succeeded", add_count=self.add_count,
                total_count=total_count, existing_ips=existing_ips,
                new_ips=new_ips, new_deployment=new_deployment_name)
        except Exception, e:
            self.this_module.fail_json(msg="Could not deploy {0}. Reason: {1}".
                format(self.deployment_name, str(e)))
        finally:
            fp.close()

    def _get_new_deployment_name(self):
        deployments = self.resource_client.deployments.list_by_resource_group(self.resource_group)
        deployment_names = list()
        for item in deployments:
            deployment_names.append(item.name)

        if self.deployment_name not in deployment_names:
            return self.deployment_name

        count = 1
        while (self.deployment_name + str(count)) in deployment_names:
            count += 1

        return self.deployment_name + str(count)

    def _display_deployments(self):
        deployments = self.resource_client.deployments.list(self.resource_group)
        for item in deployments:
            print "Deployment:", item.name

    def _display_resource_groups(self):
        resource_groups = self.resource_client.resource_groups.list()
        for item in resource_groups:
            print "Resource Group:", item.name

    def _display_cluster_servers(self):
        virtual_machines = self.compute_client.virtual_machines.list(self.resource_group)
        for item in virtual_machines:
            print "Virtual Machine:", item.name

    def _display_nics(self):
        nics = self.network_client.network_interfaces.list(self.resource_group)
        for item in nics:
            print "NICs:", item.ip_configurations[0].private_ip_address

    def _get_private_ips(self):
        ips = list()
        nics = self.network_client.network_interfaces.list(self.resource_group)
        for item in nics:
            if item.tags.get('cluster') == self.cluster_name and item.tags.get('role') == "MapR Cluster":
                ips.append(item.ip_configurations[0].private_ip_address)

        return ips, len(ips)

    @staticmethod
    def _get_new_private_ips(existing_ips, all_ips):
        new_ips = list()

        for ip in all_ips:
            if ip not in existing_ips:
                new_ips.append(ip)

        return new_ips


def main():
    this_module = AnsibleModule(argument_spec=dict(
        subscription_id=dict(required=False),
        auth_type=dict(required=True),
        client_id=dict(required=False),
        secret=dict(required=False, no_log=True),
        tenant=dict(required=False),
        username=dict(required=False),
        password=dict(required=False, no_log=True),
        admin_username=dict(required=False),
        admin_password=dict(required=False, no_log=True),
        mapr_password=dict(required=True, no_log=True),
        resource_group=dict(required=True),
        cluster_name=dict(required=True),
        deployment_name=dict(required=True),
        node_count_param=dict(required=True),
        admin_password_param=dict(required=True),
        mapr_password_param=dict(required=True),
        add_count=dict(required=True, type='int')))

    mapr_complete = MapRAzureExtend(this_module)
    mapr_complete.run()


main()
