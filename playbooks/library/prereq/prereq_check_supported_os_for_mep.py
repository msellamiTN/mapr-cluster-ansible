from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck, MaprVersion


class PrereqCheckSupportedOSForMEP(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckSupportedOSForMEP, self).__init__(
            ansible_module,
            "Supported OS for MEP",
            "check_supported_mep")

        self.core_ver = ansible_module.params["core_ver"]
        self.mep_ver = ansible_module.params["mep_ver"]
        self.distro = ansible_module.params["distro"]
        self.distro_ver = ansible_module.params["distro_ver"]
        self.prereq_values = ansible_module.params['prereq_values']['mep']
        self.os_support_matrix = self.prereq_values['support_matrix']

    def process(self):
        self.log_debug("supported_os_for_mep: core_ver={0}, mep_ver={1}, os_distro={1}, os_distro_ver={3}, os_support_matrix.keys: : {4}".format(self.core_ver, self.mep_ver, self.distro, self.distro_ver, self.os_support_matrix.keys()))
        if self.core_ver not in self.os_support_matrix.keys() or self.mep_ver not in self.os_support_matrix[self.core_ver].keys():
            self.message = "version {0} is supported with same restrictions as HPE Ezmeral Datafabric core".format(self.mep_ver)
            self.required = self.message
            self.value = "{0} {1}".format(self.distro, self.distro_ver)
            self.set_state(MapRPrereqCheck.VALID)
            return
        self.required = ", ".join(self.os_support_matrix[self.core_ver][self.mep_ver].keys()) + \
                        " for MEP {0}, and this node OS is {1} version {2}".format(
                        self.mep_ver, self.distro, self.distro_ver)
        self.value = "{0} {1}".format(self.distro, self.distro_ver)
        self.log_info(self.os_support_matrix[self.core_ver][self.mep_ver])

        if self.distro not in self.os_support_matrix[self.core_ver][self.mep_ver]:
            self.message = "OS not supported({0})".format(self.distro)
            self.set_state(MapRPrereqCheck.ERROR)
            return

        minver = self.os_support_matrix[self.core_ver][self.mep_ver][self.distro]["min"]
        minvers = minver.split(".")
        maxver = self.os_support_matrix[self.core_ver][self.mep_ver][self.distro]["max"]
        maxvers = maxver.split(".")
        curvers = self.distro_ver.split(".")

        if len(minvers) == 0 or len(maxvers) == 0:
            self.message = "Unsupported combination of OS, core and MEP version"
            self.set_state(MapRPrereqCheck.ERROR)
            return

        if len(minvers) > 1:
            minmajv, minminv = minvers[0], minvers[1]
        else:
            minmajv, minminv = minvers[0], "0"
        if len(maxvers) > 1:
            maxmajv, maxminv = maxvers[0], maxvers[1]
        else:
            maxmajv, maxminv = maxvers[0], "0"

        if len(curvers) > 1:
            curmajv, curminv = curvers[0], curvers[1]
        else:
            curmajv, curminv = curvers[0], "0"

        self.log_debug("{0} : {1}".format(self.distro, int(curmajv)))

        if MaprVersion(self.mep_ver) > MaprVersion("7.1.0") \
           and (self.distro == "suse" or self.distro == "SLES") \
           and int(curmajv) < 15:

            self.message = "MEP version {0} requires version 15+ of SLES or suse".format(self.mep_ver)
            self.set_state(MapRPrereqCheck.ERROR)
            return

        reqd_msg = "{0} {1} or higher".format(self.distro, minver)

        try:
            if int(minmajv) < int(curmajv) < int(maxmajv):
                self.set_state(MapRPrereqCheck.VALID)
                return
            if int(curmajv) == int(minmajv) and int(curmajv) != int(maxmajv):
                if int(curminv) >= int(minminv):
                    self.set_state(MapRPrereqCheck.VALID)
                    return
                else:
                    self.set_state(MapRPrereqCheck.ERROR)
                    self.message = "Unsupported minor version"
                    self.required = reqd_msg
                    return
            if int(curmajv) == int(maxmajv) and int(curmajv) != int(minmajv):
                if int(curminv) <= int(maxminv):
                    self.set_state(MapRPrereqCheck.VALID)
                    return
                else:
                    self.set_state(MapRPrereqCheck.WARN)
                    self.message = "Unsupported minor version"
                    self.required = reqd_msg
                    return
            if int(minmajv) == int(curmajv) == int(maxmajv):
                if int(minminv) <= int(curminv) <= int(maxminv):
                    self.set_state(MapRPrereqCheck.VALID)
                    return
                self.message = "Unsupported minor version"
                self.required = reqd_msg
                if int(curminv) > int(maxminv):
                    self.set_state(MapRPrereqCheck.WARN)
                else:
                    self.set_state(MapRPrereqCheck.ERROR)
                return

            self.message = "Unsupported major version"
            self.required = reqd_msg

            if int(curmajv) < int(minmajv):
                self.set_state(MapRPrereqCheck.ERROR)
            else:
                self.set_state(MapRPrereqCheck.WARN)
        except ValueError:
            self.message = "Malformed version identifier"
            self.set_state(MapRPrereqCheck.ERROR)
