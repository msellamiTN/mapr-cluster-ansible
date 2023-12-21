import glob
import json
import re
import os

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils import six
from ansible.module_utils.mapr_base import MapRBase

pattern = r'\${{{0}}}'
regex = re.compile(r'\${([A-Z_0-9]*)}')
# Regex searching for pattern like ${MAPR_HOME} where MAPR_HOME is variable name.

# Exit codes for scripts and their meanings
RV_TO_STATE = {-1: "FAILED_TO_EXECUTE", 0: "VERIFIED", 1: "NOT_RUNNING", 2: "RUNNING_NOT_RESPONDING",
               3: "NOT_STARTED", 4: "NOT_IMPLEMENTED"}
# -1 can be returned by out backend in mapr_base.py -> run_cmd()

# Do not check these services
IGNORED_ROLES = ["hbinternal", "hbase"]
# For roles with same folder as main component (like spark and spark-master, etc)
GET_HOME_FROM_PKG = ['spark-thriftserver', 'spark-master', 'spark-historyserver', 'hivemetastore', 'hiveserver2',
                     'timelineserver', 'nodemanager', 'resourcemanager', 'historyserver', 'hbaserest', 'hbasethrift',
                     'hbmaster', 'hbregionserver', 'schema-registry']
# If some of the services are not displayed in verification table - this is the place to patch it!
# Because of mismatch of role name and definition name we have to patch name, so server will receive definition name,
# and not role name for component. This need to be fixed by renaming the role name to match the definition name.
# TODO: fix role name to match definition name in next releases.
ROLENAME_PATCH = {'hbregionserver': 'hbase-regionserver', 'hbaserest': 'hbase-rest', 'hbmaster': 'hbase-master',
                  'livy': 'hue-livy', 'objectstore-client': 'objectstore-gateway', 'ksql': 'kafka-ksql',
                  'schema-registry': 'kafka-schema-registry'}


class MapRVerifyServices(MapRBase):

    def __init__(self, module):
        self.module = module
        self.admin_group = module.params['admin_group']
        self.admin_user = module.params['admin_user']
        self.env_variables = json.loads(module.params['env_variables'])
        self.data = json.loads(module.params['data'])
        self.mapr_home = module.params['home']
        self.timeout = self.get_timeout(module.params['timeout'])
        self.warnings = False
        self.roles = {}
        self.verify_services = {}
        self.result = {'service_verifications': {}}

    def exe(self, cmd, shell=False, executable=None):
        cmd2 = "{0} {1}".format(self.timeout, cmd)  # Use timeout IN-3102
        out, rv, _ = self.log_run_cmd(cmd2,
                                      self.data["variables"],
                                      shell,
                                      executable)
        return out, rv

    def fix_results(self, results):
        self.log_debug("In fix_roles_name")
        roles_dict = results['service_verifications']
        for role in roles_dict:
            self.log_debug("Checking role {}".format(role))
            if role in ROLENAME_PATCH:
                self.log_debug("Match for {}".format(role))
                self.log_debug("service dict before patch: {}".format({role: roles_dict[role]}))
                roles_dict.update({ROLENAME_PATCH[role]: roles_dict.pop(role)})
                self.log_debug("roles_dict after patch: {}".format({ROLENAME_PATCH[role]: roles_dict[ROLENAME_PATCH[role]]}))
        return {'service_verifications': roles_dict}

    def get_role_metadata(self, role_file):
        home = ''
        script = ''
        try:
            if os.path.isfile(role_file) and os.access(role_file, os.R_OK):
                with open(role_file, "r") as f:
                    for line in f:
                        l_stripped = line.rstrip()
                        if 'PKG_HOME' in l_stripped:
                            home = l_stripped.split('PKG_HOME_DIR=')[1].strip('\"')
                            self.log_info("PKG_HOME for {}:{}".format(role_file, home))
                        if 'PKG_CONFIG_COMMAND' in l_stripped:
                            script = l_stripped.split('PKG_CONFIG_COMMAND=')[1].strip('\"')
                            if script == '':
                                script = 'DO_NOT_CONFIGURE'

        except Exception as e:
            self.log_error(e)
            self.log_warn("Failed to process role file for {0}".format(role_file))
        return home, script

    def find_roles(self):
        dest = os.path.join(self.mapr_home, "roles", "*")
        for role in glob.glob(dest):
            meta_home = ''
            meta_script = ''
            role_name = os.path.basename(role)
            if os.path.getsize(role) > 0:
                (meta_home, meta_script) = self.get_role_metadata(role)
            role_dict = dict()
            role_dict[role_name] = {}
            if meta_home != '':
                role_dict[role_name].update({"home": meta_home})
            if meta_script != '':
                role_dict[role_name].update({"script": meta_script})
            self.roles.update(role_dict)

    def find_verify_scripts(self):
        """
        Scripts expected in <service_folder>/bin/verify_service
        Scripts should be in bash format and be executable.
        """
        role_name_to_path = {}
        for role in self.roles:
            self.log_info("role={0}".format(role))
            if role in IGNORED_ROLES:
                continue
            if role in role_name_to_path:
                r = role_name_to_path[role]
            else:
                r = role
            if 'home' in self.roles[r] and self.roles[r]['home'] != '':
                dest = os.path.join(self.roles[r]['home'], "bin", "verify_service")
                # Special case for roles that have same home with other roles
                if r in GET_HOME_FROM_PKG:
                    dest = os.path.join(self.roles[r]['home'], 'bin', 'verify_service' + '-' + r)
            else:
                dest = os.path.join(self.mapr_home, r, r + "-*", "bin", "verify_service")
            self.log_info('dest for {}:{}'.format(r, dest))
            scripts = glob.glob(dest)
            if len(scripts) >= 1:
                self.verify_services[r] = scripts[0]
            if len(scripts) == 0:
                self.verify_services[r] = "NOT_IMPLEMENTED"

    def get_service_status(self):
        self.log_info("roles: {0}".format(self.roles))
        self.log_info("verify_services: {0}".format(self.verify_services))
        for name, script in six.iteritems(self.verify_services):
            if script != 'NOT_IMPLEMENTED':
                (out, rv) = self.exe(script)
            else:
                out = ''
                rv = 4

            if rv is None or rv == -1:
                msg = "Failed to execute verify service script for {0}: " \
                      "{1} {2}".format(name, rv, out)
                svc_state = "UNKNOWN STATE"
                self.warnings = True
            elif rv != 0:
                if rv == 4:
                    msg = "verify service script for {0} is not yet implemented".format(name)
                else:
                    self.warnings = True
                    msg = "verify service script for {0} is failed: {1} {2}".format(name, rv, out)
                if rv not in RV_TO_STATE:
                    svc_state = "UNKNOWN STATE"
                else:
                    svc_state = RV_TO_STATE[rv]
            else:
                msg = "{0} is verified: {1}".format(name, rv)
                svc_state = RV_TO_STATE[rv]
            name_dict = dict()
            name_dict[name] = {"state": svc_state, "message": msg}
            self.result['service_verifications'].update(name_dict)

    def run(self):
        self.find_roles()
        self.find_verify_scripts()
        self.get_service_status()
        self.log_debug("Module results below")
        self.log_debug("Results before patch")
        self.log_debug(self.result)
        self.result = self.fix_results(self.result)
        self.log_debug("Results after patch")
        self.log_debug(self.result)
        logs = self.get_logs()
        if self.warnings:
            self.module.exit_json(changed=False, svcs_ver_payload=self.result, warnings="True", mapr_logs=logs)
        else:
            self.module.exit_json(changed=False, svcs_ver_payload=self.result, mapr_logs=logs)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            admin_group=dict(required=True),
            admin_user=dict(required=True),
            data=dict(required=True),
            env_variables=dict(required=True),
            home=dict(required=True),
            timeout=dict(required=True)))
    MapRVerifyServices(module).run()


main()
