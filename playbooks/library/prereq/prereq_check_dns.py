from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck
from ansible.module_utils import six


class PrereqCheckDNS(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckDNS, self).__init__(ansible_module,
                                             "DNS", "check_dns")

        # Get list of hosts to be checked for resolving.
        self.hosts = self.ansible_module.params['hosts']
        self.hostfile = []
        self.debug = MapRPrereqCheck.module_verbose

    @staticmethod
    def isgoodipv4(s):
        pieces = s.split('.')
        if len(pieces) != 4:
            return False
        # Need to account for base too
        try:
            return all(0 <= int(p) < 256 for p in pieces)
        except ValueError:
            return False

    def verify_domainname(self):
        output, rc, _ = self.log_run_cmd("hostname -d")
        self.log_debug("hostname -d returned '{0!s}'".format(output))
        if output == '':
            self.log_error("No FQDN or it is set incorrectly")
            return False
        return True

    def hostname_in_hosts(self, hostname):
        # Checking if hostname present in any line in '/etc/hosts'.
        if not self.hostfile:
            # noinspection PyBroadException
            try:
                self.hostfile = [l.split() for l in [l.rstrip() for l in open("/etc/hosts", 'r')] if not l.startswith('#') and l]
                # Will extract list of list in which each nested list will be in format
                # ['127.0.0.1', 'yournodename.localdomain', 'yournodename'] We do not rely on element order after ip.
                # The only thing you can be sure - first element from list will represent associated IP.
            except Exception:
                self.log_error("Cannot open /etc/hosts. File should be readable.")
            self.log_debug("Extracted list of hosts from hostfile: {0}".format(", ".join(str(item) for item in self.hostfile)))
        for ip_host_value in self.hostfile:
            if hostname in ip_host_value:
                return True
        else:
            return False

    @staticmethod
    def hostname_in_dns(hostname, dnsdata):
        for value in dnsdata:
            if hostname in value:
                return True
        else:
            return False

    def get_ent_names(self, name, service, is_ip):
        outd = []
        nm_ips = ""
        cmd = "getent -s {0} hosts {1}".format(service, name)
        outdata, e_code, _ = self.log_run_cmd(cmd)
        if e_code == 0:
            if len(outdata) > 0:
                nout = outdata.split('\n')
            else:
                nout = outdata

            for l in nout:
                outd.append(l.split())

            for l in range(0, len(outd)):
                if is_ip:
                    for n in range(1, len(outd[l])):
                        if n < len(outd[l][1:]):
                            nm_ips += "{0},".format(outd[l][n])
                        else:
                            nm_ips += "{0}".format(outd[l][n])
                else:
                    if l < (len(outd) - 1):
                        nm_ips += "{0},".format(outd[l][0])
                    else:
                        nm_ips += "{0}".format(outd[l][0])

            self.log_debug("'{0}' resolves to '{1}', using '{2}'".format(name, nm_ips, service))
        else:
            self.log_debug("Can not resolve '{0}', using '{1}'".format(name, service))

        return outd

    def verify_name_resolution(self, l_name, r_data, lookup_db, is_ip, ):
        name_verified = True
        self.log_debug("r_data: {0}".format(r_data))
        for row in r_data:
            ip = row[0]
            if is_ip:
                for n in row[1:]:
                    dd_rows = self.get_ent_names(n, lookup_db, False)
                    for dd_row in dd_rows:
                        if dd_row[0] != ip:
                            self.log_warn("IP lookup for {0} does not mach ip {1}, got {2}".format(n, ip, dd_row[0]))
                            name_verified = False
            else:
                dd_rows = self.get_ent_names(ip, lookup_db, True)
                self.log_debug('dd_rows: {0}'.format(dd_rows))
                for dd_row in dd_rows:
                    if self.hostname_in_hosts(l_name):
                        pass
                        # It`s ok, we found l_name in 'search_host_by_ip'
                        # associated with same ip.
                    if l_name not in dd_row[1:] and not self.isgoodipv4(ip):
                        self.log_warn("Name lookup for {0} does not mach name {1}, got {2}".format(ip, l_name, dd_row[1:]))
                        name_verified = False

        return name_verified

    def process(self):
        # Do not run this test on a cluster probe
        if self.cluster_probe:
            return

        all_host_names = []
        not_found = []
        dns_mismatch = False
        mismatch = []
        self.value = ""
        self.required = ""

        # For some core scripts we require proper FQDN setup. hostname -f should return domain name.
        # In case of no DHCP/DNS - /etc/hosts file changes and proper system configuration required
        # to populate FQDN name on the node
        if not self.verify_domainname():
            self.value = "inconsistent"
            self.required = "inconsistent. Please, refer to your distro documentation to properly set FQDN name. " \
                            "hostname -d returned no domain set. "
            self.set_state(MapRPrereqCheck.ERROR)

        for key in self.env_variables.keys():
            if "_HOST" not in key or not isinstance(self.env_variables[key], str):
                continue
            self.log_debug("key={0}".format(key))

            for h in self.env_variables[key].split(','):
                self.log_debug("h={0}".format(h))

                if len(h) > 0:
                    hname_port = h.split(':')
                    self.log_debug("hnamePort={0}".format(hname_port))

                    all_host_names.append("{0}".format(hname_port[0]))

        # add ourselves
        all_host_names.append("{0}".format(self.getfqdn()))
        # pair down to only unique host names
        all_host_names = list(set(all_host_names) | set(self.hosts))
        self.log_debug("Verifying ip/hostname for '{0}'".format("', '".join(all_host_names)))

        for lookupName in all_host_names:
            is_ip = PrereqCheckDNS.isgoodipv4(lookupName)
            self.log_debug("is_ip for '{0}' is '{1}'".format(lookupName, is_ip))
            hfile_data = self.get_ent_names(lookupName, 'files', is_ip)
            dns_data = self.get_ent_names(lookupName, 'dns', is_ip)
            found_in_hosts = False
            found_in_dns = False
            self.log_debug(("lookupname: {0}, all_host_name: {1}, dns_data: {2}, "
                            "hfile_data: {3}").format(lookupName,
                                                     all_host_names,
                                                     dns_data,
                                                     hfile_data))
            if hfile_data is not None and any(lookupName in h for h in hfile_data):
                found_in_hosts = True
                for row in hfile_data:
                    ip = row[0]
                    self.log_debug("/etc/hosts: ip = {0}, names = {1}".format(ip, row[1:]))
            else:
                self.log_debug("{0} not found in /etc/hosts, hfile_data={1}".format(lookupName, hfile_data))
            if dns_data is not None and any(lookupName in d for d in dns_data):
                found_in_dns = True
                for row in dns_data:
                    ip = row[0]
                    self.log_debug("DNS: ip = {0}, names = {1}".format(ip, row[1:]))
            elif not dns_data and found_in_hosts:
                pass
                # It`s fine.
            elif dns_data and found_in_hosts:
                if not any(lookupName in values for values in dns_data):
                    self.log_warning("'{0}' cannot be resolved via DNS, but present in hosts. "
                                     "To remove warning, please add posibility to resolve '{0}' via DNS.".format(lookupName))
                    self.warnings = True
            else:
                self.log_debug("{0} not found in DNS, nor in '/etc/hosts'.".format(lookupName))

            if not found_in_hosts and not found_in_dns:
                self.warnings = True
                not_found.append(lookupName)
            elif found_in_hosts:
                if not self.verify_name_resolution(lookupName, hfile_data, 'files', is_ip,):
                    self.warnings = True
            elif found_in_dns:
                if not self.verify_name_resolution(lookupName, hfile_data, 'dns', is_ip,):
                    self.warnings = True

            if found_in_hosts and found_in_dns:
                for hosts_row, dns_row in zip(hfile_data, dns_data):
                    if is_ip:
                        # Check to see if the names are the same
                        if hosts_row[1] != dns_row[1]:
                            self.log_warn("Name lookup for ip '{0}' does not match in hosts file '{1}', DNS '{2}'.".format(lookupName, hosts_row[1], dns_row[1]))
                            self.warnings = True
                            mismatch.append(lookupName)
                            dns_mismatch = True
                    else:
                        # Check to see if the ips are the same
                        if hosts_row[0] != dns_row[0]:
                            self.log_warn("Name lookup for ip '{0}' does not match in hosts file '{1}', DNS '{2}'.".format(lookupName, hosts_row[0], dns_row[0]))
                            self.warnings = True
                            mismatch.append(lookupName)
                            dns_mismatch = True

        if len(not_found) > 0:
            self.log_error("The following hostnames cannot be resolved: '{0}'".format("', '".join(not_found)))
            self.value = "inconsistent"
            self.required = ("inconsistent. It needs to be consistent for the MapR cluster to work reliably. "
                             "If this check produces inconsistent result you are likely to have issues "
                             "during install or later. We strongly recommend you fix the DNS setup. "
                             "These hosts cannot be resolved: '{0}'").format(', '.join(not_found))
            self.message = "One or more hostnames failed forward/reverse Dns check"
            self.set_state(MapRPrereqCheck.ERROR)
        elif dns_mismatch:
            self.value = "inconsistent"
            self.required = ("inconsistent. It needs to be consistent for the MapR cluster to work reliably. "
                             "If this check produces inconsistent result you are likely to have issues "
                             "during install or later. We strongly recommend you fix the DNS setup. "
                             "These hosts resolved differently using DNS and hostfile: '{0}'").format(', '.join(mismatch))
            self.set_state(MapRPrereqCheck.WARN)
        else:
            self.value = "consistent"
            self.required = "consistent"
            self.set_state(MapRPrereqCheck.VALID)
