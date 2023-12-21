from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck
from ansible.module_utils import six


class PrereqCheckLoc(MapRPrereqCheck):

    def __init__(self, ansible_module):
        super(PrereqCheckLoc, self).__init__(ansible_module, "Locale", "check_locale")
        self.locale = ansible_module.params['prereq_values']['os']['locale']

    def process(self):
        self.required = self.locale['need'] + " Install will fail if other locale is " + \
            "configured for root or cluster admin user"
        code = 1
        try:
            out, code, _ = self.log_run_cmd("locale")
        except OSError:
            pass
        if code != 0:
            self.value = "Unknown"
            self.set_state(MapRPrereqCheck.ERROR)
            return
        lang = out.split("LANG=")[-1].split(".")[0]
        if lang == "en_US":
            self.value = "en_US"
            self.set_state(MapRPrereqCheck.VALID)
        else:
            self.value = lang
            self.set_state(MapRPrereqCheck.ERROR)
