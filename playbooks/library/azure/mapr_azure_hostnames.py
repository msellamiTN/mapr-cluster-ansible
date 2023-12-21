from ansible.module_utils.basic import AnsibleModule

from ansible.module_utils.mapr_base import MapRBase


class MapRAzureHostnames(MapRBase):
    def __init__(self, this_module):
        self.this_module = this_module
        self.hostargs = this_module.params.get("hostvars")
        self.for_ips = this_module.params.get("for_ips")

    def run(self):
        hostnames = list()
        fqdn_hostnames = list()
        entry_strings = list()
        hostname_by_ip = dict()
        ignored_ips = list()

        for key in self.hostargs:
            if self.for_ips is not None and len(self.for_ips) > 0 and key not in self.for_ips:
                ignored_ips.append(key)
                continue

            ahost = self.hostargs[key]
            ansible_hostname = ahost["ansible_hostname"]

            private_ip = ahost['ansible_default_ipv4']['address']

            ansible_dns = ahost["ansible_dns"]
            domain_name = ansible_dns['search'][0]
            fqdn_hostname = "{0}.{1}".format(ansible_hostname, domain_name)

            hostnames.append(ansible_hostname)
            fqdn_hostnames.append(fqdn_hostname)
            entry_strings.append("{0} {1} {2}".format(private_ip, fqdn_hostname, ansible_hostname))
            hostname_by_ip[private_ip] = fqdn_hostname

        self.this_module.exit_json(changed=True,
            msg="Hostname information retrieved for {0} nodes".format(len(self.hostargs)),
            hostnames=hostnames,
            fqdn_hostnames=fqdn_hostnames,
            entries=entry_strings,
            hostname_by_ip=hostname_by_ip,
            ignored_ips=ignored_ips)


def main():
    this_module = AnsibleModule(argument_spec=dict(
        hostvars=dict(required=True, type='dict'),
        for_ips=dict(required=False, type='list')))

    mapr_hostnames = MapRAzureHostnames(this_module)
    mapr_hostnames.run()


main()
