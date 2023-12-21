import glob
import json
import re
import random
import os
import traceback

from time import sleep
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.mapr_base import MapRBase
from ansible.module_utils import six

pattern = r'\${{{0}}}'
regex = re.compile(r'\${([A-Z_0-9]*)}')


# Regex searching for pattern like ${MAPR_HOME} where MAPR_HOME is variable name.


class MapRConf(MapRBase):
    MFS_RETRIES = 4

    def __init__(self, module):
        self.module = module
        self.data = json.loads(module.params['data'])
        self.template_dir = module.params['template_dir']
        self.timeout = self.get_timeout(module.params['timeout'])
        self.mapr_home = module.params['mapr_home']
        self.is_update = module.params['is_update']
        self.is_upgrade = module.params['is_upgrade']
        # Only True treated as trigger for update.
        # All other values will be passed as empty string.
        TRUE = [True, 'yes', 'y', 'true', 'True']
        if self.is_upgrade not in TRUE:
            self.is_upgrade = "false"
        else:
            self.is_upgrade = "true"
        if self.is_update not in TRUE:
            self.is_update = "false"
        else:
            self.is_update = "true"

    def exe(self, cmd, shell=False, executable=None):
        out, rv, _ = self.log_run_cmd(cmd,
                                      self.data["variables"],
                                      shell,
                                      executable)
        return out, rv

    def perform_substitutions(self, service, subs, dest, comment=None, process_name=None):
        modified = False
        if subs:
            if glob.glob(dest):
                dest = glob.glob(dest)[0]
            for (sub, val) in six.iteritems(subs):
                value = val
                cont = True

                for var in regex.findall(val):
                    if var in self.data["variables"] and self.data["variables"][var]:
                        value = re.sub(pattern.format(var), self.data["variables"][var], value)
                    else:
                        cont = False
                        break

                if not cont:
                    continue

                cmd = "sed -i '\|{0}$|,${{s||{1}|;b}};$q1' {2}".format(sub, value, dest)
                (out, rv) = self.exe(cmd)
                if rv == 0:
                    modified = True
                    continue

                if comment:
                    cmd = "sed -i '\|{0}{1}.*|,${{s||{1}{2}|;b}};$q1' {3}".format(
                        comment, sub, value, dest)
                    (out, rv) = self.exe(cmd)
                    if rv == 0:
                        modified = True
                        continue

                cmd = "sed -i '\|{0}.*|,${{s||{0}{1}|;b}};$q1' {2}".format(sub, value, dest)
                (out, rv) = self.exe(cmd)
                if rv == 0:
                    modified = True
                    continue

        if dest.startswith('/') and os.path.isfile(dest):
            with open(dest) as f:
                data = f.read()

            if data:
                for var in self.data["variables"]:
                    if self.data["variables"][var]:
                        # noinspection PyBroadException
                        try:
                            newdata = re.sub(pattern.format(var), self.data["variables"][var], data)
                            if newdata != data:
                                data = newdata
                                modified = True
                        except:
                            continue

                with open(dest, 'w') as f:
                    f.write(data)

        if modified and process_name:
            return process_name
        return None

    def copy_from_local(self, service, src, dest, optional=False):
        if not os.path.exists(dest):
            if not src.startswith("/"):
                # This is relative to templates directory
                src = os.path.join(self.template_dir, service, src)

            if dest.startswith("/"):
                # This is a local destination
                if dest.endswith("/"):
                    cmd = "mkdir -p {0}".format(dest)
                    self.exe(cmd)

                srcs = glob.glob(src)
                if not srcs:
                    srcs = [src]

                for s in srcs:
                    cmd = "cp {0} {1}".format(s, dest)
                    (out, rv) = self.exe(cmd)
                    if rv != 0 and not optional:
                        self.module.fail_json(
                            msg="Unable to execute command: {0}. Returned: "
                                "{1} {2}".format(cmd, rv, out),
                            mapr_logs=self.get_logs())
            else:
                if dest.endswith("/"):
                    # This is a dfs directory, try to create it
                    cmd = "{0} hadoop fs -mkdir -p /installer/{1}".format(self.timeout, dest)
                    _, retcode = self.exe(cmd)
                    self.check_timeout(cmd=cmd, code=retcode)

                # This is a local path
                if glob.glob(src):
                    srcs = glob.glob(src)
                else:
                    srcs = [src]

                for s in srcs:
                    self.log_info('Putting {0} via hadoop fs -put to {1}'.format(s, dest))
                    cmd = "{0} hadoop fs -put -f {1} /installer/{2}".format(self.timeout, s, dest)
                    self.cmd_retry(cmd, optional)

    def cmd_retry(self, cmd, optional=False, shell=False, executable=None):
        # we may be competing with other nodes and even -f
        # gives errors on collisions
        # hdfs put outputs "put: Invalid source or target" when we have
        # a write collision. It outputs: put: Could not create FileClient
        # when hdfs is down. If we get the Invalid source or target
        # we are assuming we have a collision and ignore it (one of them
        # will succeed)
        failed = False
        rv = -1
        out = ""
        for cnt in range(MapRConf.MFS_RETRIES):
            (out, rv) = self.exe(cmd, shell, executable)
            self.check_timeout(cmd=cmd, code=rv)
            if six.PY3:
                failed = rv != 0 and not optional and b"Invalid source or target" not in out
            else:
                failed = rv != 0 and not optional and "Invalid source or target" not in out
            if not failed:
                return
            sleep(2 + random.randint(0, 1))
        if failed:
            self.module.fail_json(msg="Unable to execute command: {0}. Code: {1} Output: {2}".format(cmd, rv, out),
                                  mapr_logs=self.get_logs())

    def run(self):
        # Update variables that need to be substituted
        self.data["variables"].update({"TEMPLATES_HOME": self.template_dir})
        self.data["variables"].update({"MAPR_HOME": self.mapr_home})
        self.data['variables'].update({"IS_UPDATE": self.is_update})
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

        host_svcs_list = sorted([svc for svc in self.data['services']
                                 if svc in all_svcs_set])
        # configure core services first
        for service in host_svcs_list:
            if "core" in self.data["global_services"][service] and \
                    self.data["global_services"][service]["core"]:
                services.append(service)
        for service in host_svcs_list:
            if "core" not in self.data["global_services"][service] or not \
                    self.data["global_services"][service]["core"]:
                services.append(service)
        for service in services:
            process_name = None
            if "files" in self.data["global_services"][service] and self.data["global_services"][service]["files"]:
                for f in self.data["global_services"][service]["files"]:
                    if "dest" in f and "src" in f:
                        subs = {}
                        if "substitutions" in self.data["global_services"][service] and self.data["global_services"][service]["substitutions"]:
                            subs.update(self.data["global_services"][service]["substitutions"])

                        for var in regex.findall(f["src"]):
                            if var in self.data["variables"] and \
                                    self.data["variables"][var]:
                                f["src"] = re.sub(pattern.format(var),
                                                  self.data["variables"][var], f["src"])
                        for var in regex.findall(f["dest"]):
                            if var in self.data["variables"] and \
                                    self.data["variables"][var]:
                                f["dest"] = re.sub(pattern.format(var), self.data["variables"][var], f["dest"])
                        try:
                            self.copy_from_local(service, f["src"], f["dest"],
                                                 f.get("optional", False))
                        except Exception as e:
                            self.module.fail_json(msg="Unable to copy {0} to {1} {2}, stack: {3}".format(f["src"], f["dest"], str(e), traceback.format_exc()),
                                mapr_logs=self.get_logs())

                        if not f.get("no_substitution", False):
                            process_name_ = self.perform_substitutions(service, subs, f["dest"], f.get("comment", None),

                                self.data["global_services"][service].get("process_name", None))
                            if process_name_ and not f.get("no_restart", False):
                                process_name = process_name_

            if "commands" in self.data["global_services"][service] and self.data["global_services"][service]["commands"]:
                for cmdstr in self.data["global_services"][service]["commands"]:
                    for var in regex.findall(cmdstr):
                        if var in self.data["variables"] and self.data["variables"][var]:
                            cmdstr = re.sub(pattern.format(var),
                                            self.data["variables"][var],
                                            cmdstr)
                    try:
                        if cmdstr.startswith("bash"):
                            shell = False
                            executable = None
                        else:
                            shell = True
                            executable = "/bin/bash"
                        self.cmd_retry(cmdstr, shell=shell,
                                       executable=executable)
                    except Exception as e:
                        self.module.fail_json(msg="Unable to execute command {0}, Exception: {1}".format(cmdstr, str(e)), mapr_logs=self.get_logs())

                        # wait to restart everything until the end
                        # if process_name:
                        #     restartcmd = "maprcli node services -action restart
                        #     -name {0} -nodes {1}".format(process_name, socket.gethostname())
                        #     self.exe(restartcmd, shell=True, executable='/bin/bash')

        self.module.exit_json(changed=True,
                              msg="Successfully completed post install procedures",
                              mapr_logs=self.get_logs())


def main():
    module = AnsibleModule(
        argument_spec=dict(
            data=dict(required=True),
            template_dir=dict(required=True),
            timeout=dict(required=True),
            mapr_home=dict(required=True),
            is_update=dict(required=True),
            is_upgrade=dict(required=True)
        )
    )
    MapRConf(module).run()


main()
