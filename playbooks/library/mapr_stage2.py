import json
import os
import re

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.mapr_base import MapRBase

pattern = r'\${{{0}}}'
regex = re.compile(r'\${([A-Z_0-9]*)}')


class MapRStage2(MapRBase):

    def __init__(self, module):
        self.module = module
        self.data = json.loads(module.params['data'])
        self.templates_dir = module.params['template_dir']
        self.cmd_log = []
        self.timeout = self.get_timeout(module.params['timeout'])
        self.mapr_home = module.params['mapr_home']
        self.command = module.params['command']
        if self.command == 'upgrade' or self.command == 'rolling_upgrade':
            self.is_upgrade = u'true'
        else:
            self.is_upgrade = u'false'

    def exe(self, cmd, shell=False, executable=None):
        out, rv, _ = self.log_run_cmd(cmd,
                                      self.data["variables"],
                                      shell,
                                      executable)
        return out, rv

    def copy_from_dfs(self, src, dest, optional=False):

        # globs does not work here since the src files are in hdfs
        # see if we have any *

        if '*' in src and not os.path.isdir(dest):
            self.module.fail_json(
                msg="Unable to copy from dfs on stage2 {0} -> {1}, {1} is not a directory".format(src, dest),
                mapr_logs=self.get_logs())
        else:
            # make sure the destination does not exist. copyToLocal doesn't have
            # a -f option.
            emsg = ""
            if os.path.isfile(dest):
                try:
                    os.unlink(dest)
                except OSError as error:
                    emsg += " {0}".format(error)
            elif os.path.isdir(dest):
                # get the name of the files we are trying to copy
                cmd = "{0} hadoop fs -ls /installer/{1}".format(self.timeout, src)
                (out, rv) = self.exe(cmd)
                self.check_timeout(cmd=cmd, code=rv)
                if rv == 0:
                    for line in out.split('\n'):
                        hdfs_ls_output = line.split(" ")
                        # XXX we should just take the last element
                        #     if it has more than 1 or 2 to be more robust
                        if len(hdfs_ls_output) > 12:
                            fname = hdfs_ls_output[12].lstrip('/installer/')
                            dest_fname = os.path.join(dest, fname)
                            if os.path.isfile(dest_fname):
                                try:
                                    os.unlink(dest_fname)
                                except OSError as error:
                                    emsg += " {0}".format(error)
            cmd = "{0} hadoop fs -copyToLocal /installer/{1} {2}".format(self.timeout, src, dest)
            (out, rv) = self.exe(cmd)
            self.check_timeout(cmd=cmd, code=rv)
            if rv != 0 and not optional:
                self.module.fail_json(msg="Unable to copy from dfs on stage2 /installer/{0}->{1}, {2}".format(src, dest, out + emsg),
                                      mapr_logs=self.get_logs())

    def run(self):
        self.data['variables'].update({"TEMPLATES_HOME": self.templates_dir})
        self.data['variables'].update({"MAPR_HOME": self.mapr_home})
        self.data['variables'].update({"IS_UPGRADE": self.is_upgrade})

        services = []
        global_svcs_dict = self.data.get("global_services", {})
        all_svcs_set = set(global_svcs_dict.keys())
        host_svcs_set = set(self.data['services'])
        svcs_intersection = list(all_svcs_set ^ host_svcs_set)

        # Please do not remove
        self.log_info("svcs_intersection: {}".format(svcs_intersection))
        self.log_info("all_svcs_set: {}".format(all_svcs_set))
        self.log_info("host_svcs_set: {}".format(host_svcs_set))

        if len(svcs_intersection) > 0:
            self.log_warn("These services {0} are inconsistent between /hosts and /config".format(svcs_intersection))

        host_svcs_list = sorted([svc for svc in self.data['services'] if svc in all_svcs_set])
        # configure core services first
        for service in host_svcs_list:
            if "core" in self.data["global_services"][service] and self.data["global_services"][service]["core"]:
                services.append(service)
        for service in host_svcs_list:
            if "core" not in self.data["global_services"][service] or not self.data["global_services"][service]["core"]:
                services.append(service)
        for service in services:
            if "stage2_files" in self.data["global_services"][service] and self.data["global_services"][service]["stage2_files"]:
                for f in self.data["global_services"][service]["stage2_files"]:
                    if "dest" in f and "src" in f:
                        for var in regex.findall(f["src"]):
                            if var in self.data["variables"] and self.data["variables"][var]:
                                f["src"] = re.sub(pattern.format(var),
                                    self.data["variables"][var], f["src"])

                        for var in regex.findall(f["dest"]):
                            if var in self.data["variables"] and  self.data["variables"][var]:
                                f["dest"] = re.sub(pattern.format(var),
                                    self.data["variables"][var], f["dest"])

                        try:
                            self.copy_from_dfs(f["src"], f["dest"],
                                f.get("optional", False))
                        except Exception as e:
                            self.module.fail_json(msg="Unable to copy stage2 {0} to {1} {2}".format(f["src"], f["dest"], str(e)),
                                mapr_logs=self.get_logs())

            if "stage2_commands" in self.data["global_services"][service] and self.data["global_services"][service]["stage2_commands"]:
                for c in self.data["global_services"][service]["stage2_commands"]:
                    for var in regex.findall(c):
                        if var in self.data["variables"] and self.data["variables"][var]:
                            c = re.sub(pattern.format(var),
                                self.data["variables"][var], c)

                    try:
                        if c.startswith("bash"):
                            (out, rv) = self.exe(c)
                        else:
                            (out, rv) = self.exe(c, shell=True,
                                executable="/bin/bash")

                        if rv != 0:
                            self.module.fail_json(msg="Unable to execute command: {0}. Returned: {1} {2}".format(c, rv, out),
                                mapr_logs=self.get_logs())
                    except Exception as e:
                        self.module.fail_json(
                            msg="Unable to execute command: {0}".format(str(e)),
                            mapr_logs=self.get_logs())

        self.module.exit_json(changed=True,
                              msg="Successfully completed stage2 procedures",
                              mapr_logs=self.get_logs())


def main():
    module = AnsibleModule(
        argument_spec=dict(
            data=dict(required=True),
            template_dir=dict(required=True),
            timeout=dict(required=True),
            mapr_home=dict(required=True),
            command=dict(required=True),))
    MapRStage2(module).run()


main()
