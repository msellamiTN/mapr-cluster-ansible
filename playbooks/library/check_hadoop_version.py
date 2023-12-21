import json

from ansible.module_utils.basic import AnsibleModule

from ansible.module_utils.mapr_base import MapRBase


class CheckHadoopVersion(MapRBase):
    def __init__(self, module=None):
        self.module = module
        self.timeout = self.module.params['timeout']

    def check_hadoop_version(self):
        mode = "classic"
        changed = False
        maprcli = "sudo -E -n -u {0} {1} maprcli".format(self.module.
            params['mapr_user'], self.get_timeout(self.timeout))
        cmd = "{0} cluster mapreduce get -json".format(maprcli)
        try:
            datastr, code, _ = self.log_run_cmd(cmd)
            self.check_timeout(cmd=cmd, code=code)
            data = json.loads(datastr)
            if data.get(u'status') == u'OK':
                changed = True
                mode = data[u'data'][0][u'default_mode']
        except Exception as e:
            self.log_error("Exception {0} when running cmd {1}".format(e, cmd))
        self.module.exit_json(changed=changed, default_mode=mode, mapr_logs=MapRBase.get_logs())


def main():
    module = AnsibleModule(argument_spec=dict(
        mapr_user=dict(required=True),
        timeout=dict(required=True)
    ))
    m = CheckHadoopVersion(module)
    m.check_hadoop_version()


main()
