import inspect
import json
import os
import shutil
import imp

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.mapr_base import MapRBase
from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck
from ansible.module_utils import six


class MapRPrereq(MapRBase):

    def __init__(self, amodule):
        self.cloud_provider = amodule.params["cloud_provider"]
        self.debug = amodule.params['debug']
        self.devices = json.loads(amodule.params['devices']) if amodule.params['devices'] else None
        self.disks = amodule.params['disks'].split(',') if amodule.params['disks'] else None
        self.distro = amodule.params['distro']
        self.distro_ver = amodule.params['distro_ver']
        self.failures = False
        self.hosts = amodule.params["hosts"]
        self.ignore_errors = amodule.params["ignore_errors"]
        self.is_cloud = amodule.params["is_cloud"]
        self.lvm = json.loads(amodule.params['lvm']) if amodule.params['lvm'] else None
        self.module = amodule
        self.mounts = json.loads(amodule.params['mounts']) if amodule.params['mounts'] else None
        self.payload = {"prereqs": {}, "state": "CHECKING", "disks": None}
        self.prereq_tests = amodule.params["prereq_tests"]
        self.prereq_values = amodule.params["prereq_values"]
        self.warnings = False

        checks = amodule.params["checks"]
        self.checks = map(str.strip, checks.split(',')) if checks else None

    def run_checks(self):
        self._run_checks()
        # TODO: SWF, check_disks should also conform to the self.checks array of checks to run if passed in
        # Fix when moving check_disks to its own file
        # self.payload['prereqs'].update(self.check_disks())
        logs = self.get_logs()

        if not self.ignore_errors and self.failures:
            self.module.fail_json(msg="Node does not meet prerequisites", prereq_payload=self.payload, mapr_logs=logs)
        elif self.failures or self.warnings:
            if self.ignore_errors:
                self.payload['prereqs'] = MapRPrereq.error_to_valid(self.payload['prereqs'])
                self.payload.update(dict(state="INSTALLED", status="Installed"))
            self.module.exit_json(changed=False, prereq_payload=self.payload, warnings="True", mapr_logs=logs)
        else:
            self.module.exit_json(changed=False, prereq_payload=self.payload, mapr_logs=logs)

    @staticmethod
    def error_to_valid(data):
        new_data = dict()
        for key, val in six.iteritems(data):
            if val.get('state') == "ERROR" or val.get('state') == "WARN":
                val['state'] = "VALID"
            new_data[key] = val
        return new_data

    def _run_checks(self):
        if not os.path.exists(self.prereq_tests):
            self.log_error("The directory {0} does not exist".format(self.prereq_tests))
            return

        try:
            files = os.listdir(self.prereq_tests)
            checks = list()

            for afile in files:
                # make sure the file looks to be a python file and is not this file (think stack overflow)
                afile = os.path.join(self.prereq_tests, afile)
                if not afile.endswith(".py") or not os.path.isfile(afile) or afile.find("mapr_prereq.py") >= 0:
                    self.log_debug("Not inspecting file: {0} for prereq classes".format(afile))
                    continue

                module_name = afile[:afile.index(".")]
                file_module = imp.load_source(module_name, os.path.join(self.prereq_tests, afile))
                class_members = inspect.getmembers(file_module, inspect.isclass)
                self.log_debug("class_members for file_module {0} is: {1}".format(str(file_module), str(class_members)))
                for clazz in class_members:
                    # if the class is of the correct subclass add it to the list of tests
                    if not issubclass(clazz[1], MapRPrereqCheck) or clazz[1] == MapRPrereqCheck or clazz[1] in checks:
                        continue

                    if self.checks is None:
                        self.log_debug("Adding class {0} to prereq checks".format(clazz[1]))
                        checks.append(clazz[1])
                    else:
                        instance = clazz[1](self.module)
                        if instance.short_name in self.checks:
                            checks.append(clazz[1])

            self.log_debug("There are {0} tests to run".format(len(checks)))
            for check in checks:
                # run the checks
                instance = check(self.module)
                instance.process()

                rslt = instance.get_results()
                if rslt is not None:
                    self.log_debug("The results from prereq test {0} is: {1}".format(instance.name, str(rslt)))
                    self.payload['prereqs'].update(rslt)
                else:
                    self.log_debug("There is no results from prereq test {0}".format(instance.name))

                if len(instance.additional_payload) > 0:
                    self.log_debug("Additional payload for prereq test {0} is: {1}".format(instance.name, str(instance.additional_payload)))
                    self.payload.update(instance.additional_payload)

                if instance.warnings is True:
                    self.warnings = True
                if instance.failures is True:
                    self.log_debug("Instance Check Failed Test {0}".format(instance.name))
                    self.failures = True
        finally:
            if os.path.exists(self.prereq_tests):
                self.log_debug("Deleting prereq tests from temporary directory")
                shutil.rmtree(self.prereq_tests)


class MaprVer(MapRBase):
    def __init__(self, ver_str):
        self.ver_str = ver_str
        # noinspection PyBroadException
        try:
            self.ver = map(int, ver_str.split("."))
        except Exception:
            self.log_error("Mapr version string must be of the form x.y.z: {0}".format(ver_str))

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __gt__(self, other):
        return self.__cmp__(other) > 0

    def __le__(self, other):
        return self.__cmp__(other) <= 0

    def __ge__(self, other):
        return self.__cmp__(other) >= 0

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __ne__(self, other):
        return self.__cmp__(other) != 0

    def __cmp__(self, other):
        min_len = min(len(self.ver), len(other.ver))
        for idx in range(min_len):
            if self.ver[idx] < other.ver[idx]:
                return -1
            elif self.ver[idx] > other.ver[idx]:
                return 1
        if len(self.ver) > min_len:
            return -1
        if len(other.ver) > min_len:
            return 1
        return 0

    def __str__(self):
        return self.ver_str

    @staticmethod
    def is_valid(ver_str):
        res = True
        for var in ver_str.split("."):
            res = res and var.isdigit()
        return res


def main():
    amodule = AnsibleModule(
        argument_spec=dict(admin_gid=dict(default=5000, type='int'),
                           admin_group=dict(default='mapr', type='str'),
                           admin_uid=dict(default=5000, type='int'),
                           admin_user=dict(default='mapr', type='str'),
                           checks=dict(),
                           cloud_provider=dict(type='str'),
                           cluster_probe=dict(default=False, type='bool'),
                           core_ver=dict(type='str'),
                           cpu=dict(default='x86_64', type='str'),
                           create_admin=dict(default=False, type='bool'),
                           data=dict(),
                           db_admin_password=dict(required=False, type='str'),
                           db_admin_password_set=dict(required=True, type='bool'),
                           db_admin_user=dict(type='str'),
                           debug=dict(default=False, type='bool'),
                           devices=dict(),
                           disk_space=dict(type='int', default=1),
                           disks=dict(type='str'),
                           distro=dict(type='str'),
                           distro_ver=dict(type='str'),
                           env_variables=dict(),
                           fips=dict(default=False, type='bool'),
                           fqdn=dict(type='str'),
                           fresh_install=dict(default=False, type='bool'),
                           home=dict(type='str'),
                           hosts=(dict(required=True, type='list')),
                           ignore_errors=dict(default=False, type='bool'),
                           interfaces=dict(type='list'),
                           is_cloud=dict(default=False, type='bool'),
                           lvm=dict(),
                           mapr_subnet=dict(default='', type='str'),
                           mep_ver=dict(type='str'),
                           mounts=dict(),
                           mysql_host=dict(type='str'),
                           mysql_socket=dict(type='str'),
                           name=dict(default='prereq', aliases=['prereq'], type='str'),
                           no_internet=dict(default=False, type='bool'),
                           nodename=dict(type='str'),
                           prereq_tests=dict(required=False),
                           prereq_values=dict(required=True, type='dict'),
                           ram=dict(type='int'),
                           security=dict(default=False, type='bool'),
                           swap=dict(type='int'),
                           use_external_mysql=dict(default=False, type='bool'),
                           use_shared_mysql=dict(default=False, type='bool'),
                           ))

    prereq = MapRPrereq(amodule)
    prereq.run_checks()


if __name__ == '__main__':
    main()
