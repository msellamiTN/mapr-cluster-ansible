import json
import socket
import math
import os
import stat

from ansible.module_utils import pymysql
# So, some info about line above:
# ansible create module_utils environment for Python each time you ask for a module
# on end machine. And each time it tries to find out which modules from module_utils are needed.
# So if you would not import your module at your entry point (in case of prereq - the entry point is this file) -
# you will not be able to import it in other modules this script calls.
# Ansible cannot parse our inherited modules that we include with inspect, we each time we add 3rd-party python module
# we need to include that python module in THIS file to bundle it with module_utils.

from ansible.module_utils import six
from ansible.module_utils.mapr_base import MapRBase
from distutils.version import LooseVersion


class MapRPrereqCheckError(Exception):
    pass


# TODO Can we add the logs to the JSON returned to the GUI? Or add additional information to WARN or ERROR response?

class MapRPrereqCheck(MapRBase):
    module_verbose = False

    ERROR = "ERROR"
    WARN = "WARN"
    VALID = "VALID"
    STATES = [ERROR, WARN, VALID]

    MB = "MB"
    VALUES = [MB]

    def __init__(self, ansible_module, name, short_name):
        if ansible_module is None:
            raise MapRPrereqCheckError("Missing 'ansible_module' argument")
        if name is None:
            raise MapRPrereqCheckError("Missing 'name' argument")

        self._state = None
        self._check_run = False

        self.ansible_module = ansible_module
        self.name = name
        self.short_name = short_name
        self.message = None
        self.action = None
        self.required = None
        self.value = None
        self.failures = False
        self.warnings = False
        self.additional_payload = dict()
        self.distro = ansible_module.params['distro']
        self.distro_ver = ansible_module.params['distro_ver']
        self.is_cloud = ansible_module.params.get("is_cloud", False)
        self.cloud_provider = ansible_module.params.get("cloud_provider")
        self.cluster_probe = ansible_module.params.get("cluster_probe")
        self.create_admin = ansible_module.params.get("create_admin")
        self.admin_user = ansible_module.params.get("admin_user")
        self.mapr_subnet = ansible_module.params.get("mapr_subnet")
        self.env_variables = None
        if ansible_module.params.get('env_variables') is not None:
            self.env_variables = json.loads(ansible_module.params.get('env_variables'))
        self.data = None
        if ansible_module.params.get('data') is not None:
            self.data = json.loads(ansible_module.params.get('data', dict()))
        self.debug = ansible_module.params.get("debug")
        if self.debug:
            self.module_verbose = True

    @staticmethod
    def getfqdn(name=''):
        """Get fully qualified domain name from name.

        An empty argument is interpreted as meaning the local host.

        First the hostname returned by gethostbyaddr() is checked, then
        possibly existing aliases. In case no FQDN is available, hostname
        from gethostname() is returned.
        """
        name = name.strip()
        if not name or name == '0.0.0.0':
            name = socket.gethostname()
        try:
            hostname, aliases, ipaddrs = socket.gethostbyaddr(name)
        except socket.error:
            pass
        else:
            aliases.insert(0, hostname)
            for name in aliases:
                if '.' in name:
                    break
            else:
                name = hostname

        return name

    @staticmethod
    def get_limit_for_user(user, data, prop):
        res = filter(lambda aline: aline[0] == user, data)
        res = [line[3] for line in res if line[2] == prop]
        try:
            res = res[-1]
        except Exception:
            raise MapRPrereqCheckError("Property {0} not found for user"
                                       "{1}".format(prop, user))
        return res

    @staticmethod
    def read_firstline(path):
        if os.path.isfile(path) and os.access(path, os.R_OK):
            with open(path) as file_d:
                line = file_d.readline().strip()
            return line

        raise MapRPrereqCheckError("Cannot read file: {0!s}".format(path))

    @staticmethod
    def read_lines(path):
        if os.path.isfile(path) and os.access(path, os.R_OK):
            with open(path) as file_d:
                lines = file_d.readlines()
            return lines

        raise MapRPrereqCheckError("Cannot read file: {0!s}".format(path))

    @staticmethod
    def to_gb(value, value_in=MB):
        if value_in not in MapRPrereqCheck.VALUES:
            raise MapRPrereqCheckError("{0} is not valid; Must be one of the following: {1}".format(type(value_in), MapRPrereqCheck.VALUES))

        if value_in == MapRPrereqCheck.MB:
            return math.ceil((int(value) / 1024.0))

    def _validate(self):
        if self._state is None:
            self._validate_error("state missing for check {0}".format(self.name))
        if self.required is None:
            self._validate_error("required missing for check {0}".format(self.name))
        if self.value is None:
            self._validate_error("value missing for check {0}".format(self.name))

    def _validate_error(self, error_message):
        self.log_error(error_message)
        self.set_state(MapRPrereqCheck.ERROR)
        if not self.message:
            self.message = "Missing message"
        if not self.value:
            self.value = "Missing value"
        self.log_error("check {0}, state: {1}, message: {2}, value: {3}".format(self.name, self._state, self.message, self.value))

    def check_owner(self, fname, uid):
        self.value = "uid 0"
        self.required = "uid {0}".format(uid)
        self.set_state(MapRPrereqCheck.VALID)

        if os.path.exists(fname):
            statinfo = os.stat(fname)
            if statinfo.st_uid != uid:
                self.value = "uid {0}".format(statinfo.st_uid)
                self.required = "uid {0}".format(uid)
                self.set_state(MapRPrereqCheck.ERROR)

            return

        self.message = "File missing"
        self.set_state(MapRPrereqCheck.ERROR)

    def check_perms(self, fname, perm):
        self.value = "01777"
        self.required = "{0}".format(oct(perm))
        self.set_state(MapRPrereqCheck.VALID)

        if os.path.exists(fname):
            statinfo = os.stat(fname)
            if oct(stat.S_IMODE(statinfo.st_mode)) != oct(perm):
                self.value = "{0}".format(oct(stat.S_IMODE(statinfo.st_mode)))
                self.required = "{0}".format(oct(perm))
                self.set_state(MapRPrereqCheck.ERROR)

            return

        self.message = "File missing"
        self.set_state(MapRPrereqCheck.ERROR)

    def check_disk_space_on(self, directory, ok_size_gb, min_size_gb):
        res, code, err = self.log_run_cmd("df -P {0}".format(directory))
        if code !=0:
            self.required = "Failed to get diskspace for mount point {0}, return code {1}, stderr {2}".format(directory,code,err)
            self.set_state(MapRPrereqCheck.ERROR)
            return
        device, size, used, available, percent, mountpoint = res.split("\n")[1].split()
        available_in_gb = float(format(int(available) / (1000 * 1000.0), '.1f'))

        self.value = "{0} GB".format(available_in_gb)
        self.required = "{0} GB".format(ok_size_gb)
        if available_in_gb > ok_size_gb:
            self.set_state(MapRPrereqCheck.VALID)
        elif available_in_gb > min_size_gb or min_size_gb == 0:
            self.required = "{0} GB. You only have {1} GB available. " \
                            "Please make sure required disk space is available before continuing " \
                            "the install.".format(ok_size_gb, available_in_gb)
            self.set_state(MapRPrereqCheck.WARN)
        else:
            self.required = "{0} GB. You only have {1} GB available, which is less " \
                            "than the ablsolute minimum of {2} GB. " \
                            "Please make sure required disk space is available before continuing " \
                            "the install.".format(ok_size_gb, available_in_gb, min_size_gb)
            self.set_state(MapRPrereqCheck.ERROR)

    def set_state(self, state):
        if state not in MapRPrereqCheck.STATES:
            raise MapRPrereqCheckError("{0} is not a valid state; Must be one of the following: {1}"
                                       .format(type(state), MapRPrereqCheck.STATES))

        self.failures = False
        self.warnings = False

        if state == MapRPrereqCheck.ERROR:
            self.failures = True
        elif state == MapRPrereqCheck.WARN:
            self.warnings = True

        self._state = state
        self._check_run = True

    def check_exec(self, program):
        self.value = "absent"
        self.required = "absent. It should be absent during fresh install."
        present_msg = "present. If it is present for a fresh install, " \
                      "it means you are trying to install a node that is already installed, and we " \
                      "will not allow you to overwrite the node. Check to make sure the node is " \
                      "really the one you intended to install, and if it is and has this binary " \
                      "install, uninstall required packages before retrying."

        def is_exe(filename):
            return os.path.isfile(filename) and os.access(filename, os.X_OK)

        found = False
        fpath, fname = os.path.split(program)
        if fpath:
            if is_exe(program):
                found = True
        else:
            for path in os.environ['PATH'].split(os.pathsep):
                path = path.strip('"')
                exe_file = os.path.join(path, program)
                if is_exe(exe_file):
                    found = True

        if found:
            if self.data is not None and "services" in self.data:
                if self.data["services"] and "installed" in self.data and self.data["installed"] is True:
                    self.value = "allowed"
                    self.required = "allowed. It's presence is allowed for incremental or upgrade installs."
                    self.set_state(MapRPrereqCheck.VALID)
                    return

                if os.path.isdir("/opt/mapr/roles") and not os.path.exists("/opt/mapr/hostid"):
                    self.value = "unconfigured"
                    self.required = "unconfigured. It's presence is allowed for nodes that are not configured."
                    self.set_state(MapRPrereqCheck.VALID)
                    return

                self.value = "present"
                self.required = present_msg
                self.set_state(MapRPrereqCheck.ERROR)
                return

            if self.cluster_probe:
                self.value = "allowed"
                self.required = "allowed. It's presence is allowed for incremental or upgrade installs or probe."
                self.set_state(MapRPrereqCheck.VALID)
                return

            if os.path.exists("/opt/mapr"):
                self.value = "present"
                self.required = "present. This is unexpected, since you have no mapr services on this node, " \
                                "but we found /opt/mapr to exist. You may want to double check that this " \
                                "node is indeed the correct target node before continuing on with the install."
                self.set_state(MapRPrereqCheck.WARN)
                return

            self.value = "present"
            self.required = present_msg
            self.set_state(MapRPrereqCheck.ERROR)
            return

        self.set_state(MapRPrereqCheck.VALID)

    def get_results(self):
        if not self._check_run:
            # If set_state() was not called then the test will be ignored in the output
            return None

        self._validate()

        name_dict = dict()
        results_dict = dict()

        results_dict["state"] = self._state
        results_dict["required"] = self.required
        results_dict["value"] = self.value
        if self.message is not None:
            results_dict["message"] = self.message
        if self.action is not None:
            results_dict["action"] = self.action

        name_dict[self.name] = results_dict
        return name_dict

    def process(self):
        raise NotImplementedError("The process method cannot be called on the abstract class and must be implemented")

    def __str__(self):
        return "Name: {0}; State: {1}; Required: {2}; Value: {3}; Message: {4}".format(self.name, self._state, self.required, self.value, self.message)


class MaprVersion(MapRBase):
    def __init__(self, ver_str):
        self.ver = ver_str

    def __eq__(self, other):
        return LooseVersion(self.ver) == LooseVersion(other.ver)

    def __ne__(self, other):
        return LooseVersion(self.ver) != LooseVersion(other.ver)

    def __lt__(self, other):
        return LooseVersion(self.ver) < LooseVersion(other.ver)

    def __le__(self, other):
        return LooseVersion(self.ver) <= LooseVersion(other.ver)

    def __gt__(self, other):
        return LooseVersion(self.ver) > LooseVersion(other.ver)

    def __ge__(self, other):
        return LooseVersion(self.ver) >= LooseVersion(other.ver)

    def __str__(self):
        return self.ver

    @staticmethod
    def is_valid(ver_str):
        res = True
        for var in ver_str.split("."):
            res = res and var.isdigit()
        return res
