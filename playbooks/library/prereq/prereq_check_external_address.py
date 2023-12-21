import socket

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck
from ansible.module_utils import six

if six.PY2:
    from urllib2 import Request, urlopen
    from urlparse import urlparse
else:
    from urllib.request import Request, urlopen
    from urllib.parse import urlparse


class PrereqExternalAddress(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqExternalAddress, self).__init__(ansible_module, "External Address", "external_address")
        self.external_address = None
        self.prereq_values = ansible_module.params['prereq_values']['internet']
        self.inter_socket_timeout = self.prereq_values['socket_timeout']
        self.inter_cloud_urls = self.prereq_values['urls_cloud']

    def process(self):
        # Check if we are EC2 or GCE
        timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.inter_socket_timeout)
        try:
            for url in self.inter_cloud_urls:
                try:
                    socket.gethostbyname(urlparse(url)[1])
                    req = Request(url)
                    req.add_header("Metadata-Flavor", "Google")
                    req.add_header("Metadata", "true")
                    resp = urlopen(req)
                    addr = resp.read()
                    if addr and addr.find('<') == -1:
                        self.external_address = addr.strip()
                        break
                except Exception as ex:
                    self.log_warn("Request to url {0} failed due to exception: {1}".format(url, str(ex)))
                    continue
        finally:
            self.additional_payload.update({"external_address": self.external_address})
            socket.setdefaulttimeout(timeout)

    def get_results(self):
        # Override get_results because this is a prereq that doesn't return the standard JSON prereq format
        return None
