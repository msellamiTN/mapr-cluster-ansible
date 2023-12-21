from ansible.module_utils.basic import AnsibleModule

from ansible.module_utils.mapr_base import MapRBase


class MapRClusterInfo(MapRBase):
    def __init__(self, module):
        self.module = module

    def mapr_cluster_info(self):
        clusterid_file = '/opt/mapr/conf/clusterid'
        try:
            with open(clusterid_file) as fd:
                file_lines = fd.readline().splitlines()
            self.log_info("clusterid file {0} contents are {1}".format(clusterid_file,
                str(file_lines)))
            cid = file_lines[0]
        except Exception as e:
            self.log_error("Exception {0} when reading file {1}".format(e, clusterid_file))
            cid = 'error'
        self.module.exit_json(changed=False, cluster_id=cid, mapr_logs=self.get_logs())


def main():
    module = AnsibleModule(argument_spec=dict())
    cluster_info = MapRClusterInfo(module)
    cluster_info.mapr_cluster_info()


main()
