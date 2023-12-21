import json

from ansible.module_utils import six
from ansible.module_utils.basic import AnsibleModule

from ansible.module_utils.mapr_base import MapRBase


class MapRNodeTopology(MapRBase):
    def __init__(self, module):
        self.module = module
        self.data = json.loads(module.params['data'])
        self.mapr_user = module.params['mapr_user']
        self.timeout = self.get_timeout(module.params['timeout'])
        self.nodes = []

    def run(self):
        maprcli = "sudo -E -n -u {0} {1} maprcli".format(self.mapr_user,
            self.timeout)
        cmd = "{0} node list -json".format(maprcli)
        res, code, _ = self.log_run_cmd(cmd)
        cmd_fail_msg = "Unable to execute maprcli node list"
        if code != 0:
            self.check_timeout(cmd=cmd, code=code)
            self.module.fail_json(msg=cmd_fail_msg, mapr_logs=self.get_logs())
        try:
            data = json.loads(res)
            id_ = None
            if data.get(u'status') != u'OK':
                self.module.fail_json(msg=cmd_fail_msg, mapr_logs=self.get_logs())
            for node in data[u'data']:
                # Check if this is an ip that we match on
                if isinstance(node['ip'], six.string_types):
                    node['ip'] = [node['ip']]
                for ip in node['ip']:
                    if ip == self.data['hostname']:
                        id_ = node['id']
                        break
                if id_ is None and node['hostname'] == self.data['hostname']:
                    id_ = node['id']
                if id_:
                    break
            rackname = self.data.get(u'rack')
            self.log_info("node id: {0} hostname: {1} rackname {2}".format(id_,
                self.data.get('hostname'), rackname))

            changed = False
            if id_ and rackname:
                rack = self.data[u'rack']
                rack = '/data{0}'.format(rack) if rack.startswith('/') else \
                    '/data/{0}'.format(rack)
                cmd = "{0} node move -serverids {1} -topology {2}".format(
                    maprcli, id_, rack)
                res, code, _ = self.log_run_cmd(cmd)
                self.check_timeout(cmd=cmd, code=code)
                changed = code == 0
            self.module.exit_json(changed=changed,
                msg="Successfully set node topology", mapr_logs=self.get_logs())
        except Exception as e:
            self.module.fail_json(msg="Unable to parse json: "
                "{0}, raw data {1}".format(e, res), mapr_logs=self.get_logs())


def main():
    module = AnsibleModule(argument_spec=dict(
        data=dict(required=True),
        mapr_user=dict(required=True),
        timeout=dict(required=True)
    ))
    MapRNodeTopology(module).run()


main()
