#!/usr/bin/env python
import json
import os
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.mapr_base import MapRBase


class CheckBecomeAccess(MapRBase):

    def __init__(self, module=None):
        self.module = module
        self.timeout = self.module.params['timeout']
        self.ssh_id = self.module.params['ssh_id']
        self.ssh_pw = self.module.params['ssh_pw']
        self.ssh_kf = self.module.params['ssh_kf']
        self.state = "Error"
        self.value = "No privilege elevation ability"
        self.changed = False

    def check_become_access(self):
        if os.getuid() == 0:
            self.log_debug("User is root")
            self.value = "Root user detected"
            self.state = "Valid"
            self.changed = True
#        else:
#            # we will actually never get here as ansible tries to elevate access
#            # in the ssh.py module, and if that fails it errors out there before even
#            # trying to run this 
#            # leaving it here in case ansible change the way it does things
#            timeout_occured = False
#            cmd = "sudo -n true"
#            try:
#                datastr, code, _ = self.log_run_ccmd(cmd)
#                self.check_timeout(cmd=cmd, code=code)
#                data = json.loads(datastr)
#            except Exception as e:
#                self.log_error("Exception {0} when running cmd {1}".format(e, cmd))
#                self.state = "Error"
#                timeout_occured = True
#            if data.get(u'status') == u'OK':
#                self.log_debug("User has sudo access")
#                self.value = "valid sudo detected"
#                self.state = "Valid"
#                self.changed = True
#            elif not timeout_occured:
#                # password needed
#                if self.ssh_pw is none or ssh.ssh_pw == '':
#                    self.log_debug("Sudo require password, but none provided")
#                    self.value = "user '" + self.ssh_id + "' needs a password to use sudo, but none provided"
#                    self.state = "Error"
#                else:
#                    cmd = "echo {0} | sudo -S true".format(ssh_pwd)
#                    try:
#                        datastr, code, _ = self.log_run_ccmd(cmd)
#                        self.check_timeout(cmd=cmd, code=code)
#                        data = json.loads(datastr)
#                    except Exception as e:
#                        self.log_error("Exception {0} when running cmd {1}".format(e, cmd))
#                        self.value = "failed to run sudo"
#                        self.state = "Error"
#                        timeout_occured = True
#                    if data.get(u'status') == u'OK':
#                        self.log_debug("User has sudo access - pw")
#                        self.value = "valid sudo detected"
#                        self.state = "Valid"
#                        self.changed = True
#                    else:
#                        self.log_debug("User doesn not have sudo access - pw")
#                        self.value = "user '" + self.ssh_id + "' does not have sudo access"
#                        self.state = "Error"
        self.module.exit_json(changed=self.changed, value=self.value, state=self.state, mapr_logs=MapRBase.get_logs())


def main():
    module = AnsibleModule(argument_spec=dict(
        ssh_id=dict(required=True),
        ssh_pw=dict(required=False),
        ssh_kf=dict(required=False),
        timeout=dict(required=True)
    ))
    m = CheckBecomeAccess(module)
    m.check_become_access()


main()
