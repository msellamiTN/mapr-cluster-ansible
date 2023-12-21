from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck
from ansible.module_utils import six


class PrereqCheckSVCS(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckSVCS, self).__init__(ansible_module, "Services", "check_svcs")
        self.distro = ansible_module.params["distro"]
        self.distro_ver = ansible_module.params["distro_ver"]
        self.svc_list = list(ansible_module.params['prereq_values']['os']['services'])

    @staticmethod
    def get_status_bool(status):
        return 'turned off' if status is False else 'turned on'

    @staticmethod
    def attr_is_valid(attr, distro, distro_ver):
        ver = attr.get('distro_ver')
        if distro_ver is not None and '.' in distro_ver:
            distro_ver = distro_ver.split('.')[0]
        valid = False
        if attr.get('distro') != distro:
            return False
        if attr.get('cmp') is not None:
            operator = attr.get('cmp')
        else:
            operator = None
            valid = True
        if operator == "<":
            valid = int(distro_ver) < ver
        elif operator == "<=":
            valid = int(distro_ver) <= ver
        elif operator == ">":
            valid = int(distro_ver) > ver
        elif operator == ">=":
            valid = int(distro_ver) >= ver
        return valid

    def get_checkable_svcs(self):
        svcs = {}
        for svc in self.svc_list:
            for attr in svc.get('distros'):
                if not PrereqCheckSVCS.attr_is_valid(attr, self.distro.lower(), self.distro_ver):
                    continue
                svcs.update(svc.get('prop'))
        return svcs

    def get_status(self, svc, exp):
        status = PrereqCheckSVCS.get_status_bool(exp)
        out = ""
        code = 0
        err = None
        try:
            self.log_info("Checking {0} to be {1}".format(svc, exp))
            if self.distro and self.distro == 'Ubuntu' and self.distro_ver == '16.04':
                out, code, err = self.log_run_cmd("service {0} status".format(svc))
            else:
                out, code, err = self.log_run_cmd("systemctl status {0}".format(svc))
        except Exception as e:
            self.log_error(e)
            self.log_info("Exception checking {0}, code: {1}, out: {2}, err: {3}".format(svc, code, out, err))
            pass
        self.log_debug("checking {0}, code: {1}, out: {2}, err: {3}".format(svc, code, out, err))
        exec_status = code == 0
        exec_status_log = PrereqCheckSVCS.get_status_bool(exec_status)
        return out, exec_status, status, exec_status_log

    def process(self):
        self.required = ''

        svcs = self.get_checkable_svcs()
        is_error = False
        self.log_info("Checking services for {0} {1}".format(self.distro, self.distro_ver))
        self.log_info("Services to check: {0}".format(str(svcs)))
        for svc, exp in six.iteritems(svcs):
            self.log_debug("Service: {0}, exp: {1}.".format(svc, exp))
            if type(exp) is list:
                self.log_info("Checking for one of several choices for {0}".format(svc))
                found_one = False
                or_svcs = []
                for or_entry in exp:
                    for s, e in six.iteritems(or_entry):
                        or_svcs.append(s)
                        out, exec_status, status, exec_status_log = self.get_status(s, e)
                        if exec_status == e:
                            self.log_debug("Service status for {0} is OK.".format(s))
                            # This exit if one of the item in the list is true, like:
                            # - distros:
                            #   - {cmp: '>=', distro: centos, distro_ver: 7}
                            #   - {cmp: '>=', distro: redhat, distro_ver: 7}
                            #   - {cmp: '>=', distro: sles, distro_ver: 12}
                            #   - {cmp: '>=', distro: suse, distro_ver: 12}
                            #     prop:
                            #       NTP:
                            #         - {ntpd: true}
                            #         - {chronyd: true}
                            found_one = True
                            break
                    if found_one:
                        break
                if not found_one:
                    is_error = True
                    self.log_warn("Did not find valid service status for {0}, one of these: {1}, it should be {2}.".format(svc, or_svcs, status))
                    self.required += "Did not find valid service status for {0}, one of these: {1}, it should be {2}.".format(svc, or_svcs, status)
            elif type(exp) is bool:
                out, exec_status, status, exec_status_log = self.get_status(svc, exp)
                if exec_status != exp:
                    self.log_warn("Service status for {0} is {1}, it should be {2}.".format(svc, exec_status_log, status))
                    self.required += "Service status for {0} is {1}, it should be {2}. ".format(svc, exec_status_log, status)
                    is_error = True
                else:
                    self.log_debug("Service status for {0} is OK.".format(svc))
            else:
                self.log_debug("Service unknown expression type: exp {0} is {1}.".format(exp, type(exp)))

        if is_error is False:
            self.value = "OK"
            self.required = 'OK. The installer checks that services like firewalld, ntp are configured to be ' \
                            'compatible with MapR software.'
            self.set_state(MapRPrereqCheck.VALID)
        else:
            self.value = "Not OK"
            self.required += " These services were found to be in an incompatible state and will be changed during " \
                             "install. "
            self.set_state(MapRPrereqCheck.WARN)
