import socket

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck
from ansible.module_utils import six

if six.PY2:
    from urllib2 import urlopen, HTTPError
    from urlparse import urlparse
else:
    from urllib.request import urlopen, HTTPError
    from urllib.parse import urlparse


class PrereqCheckInternet(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckInternet, self).__init__(ansible_module, "Internet", "check_internet")

        self.no_internet = ansible_module.params["no_internet"]
        self.prereq_values = ansible_module.params['prereq_values']['internet']
        self.internet_socket_timeout = self.prereq_values['socket_timeout']
        self.internet_mapr_url = self.prereq_values['mapr_url']

    def process(self):
        # Check if we can access the internet
        self.value = "absent"
        if self.no_internet:
            self.required = "absent"
        else:
            self.required = "present"

        internet_connection = True
        timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.internet_socket_timeout)
        try:
            socket.gethostbyname(urlparse(self.internet_mapr_url)[1])
            urlopen(self.internet_mapr_url)
            internet_state = "present"
        except HTTPError as e:
            # If the error code is 401 or 403, we consider the URL reachable but protected.
            if e.code in [401, 403]:
                internet_state = "present"
            else:
                internet_state = "absent"
                internet_connection = False
        except Exception:
            internet_state = "absent"
            internet_connection = False
        socket.setdefaulttimeout(timeout)

        if self.no_internet:
            self.message = "Internet connection not required"
            self.set_state(MapRPrereqCheck.VALID)
        elif internet_connection:
            self.value = internet_state
            self.set_state(MapRPrereqCheck.VALID)
        else:
            self.value = internet_state
            self.message = "Internet connection not detected"
            self.set_state(MapRPrereqCheck.WARN)
