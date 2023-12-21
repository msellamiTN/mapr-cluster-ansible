from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckInterface(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckInterface, self).__init__(ansible_module, "Interface", "check_interface")
        self.interfaces = ansible_module.params['interfaces']

    def process(self):
        self.required = "compatible - one network interface found"
        numIfaces=0
        ifaces=[]
        self.log_debug("interfaces : {0}".format(self.interfaces))
        if self.interfaces is not None:
            for iface in self.interfaces:
                self.log_debug("iface : {0}".format(iface))
                if 'lo' == iface:
                    continue
                else:
                    realIfaceIdx=numIfaces
                ifaces.append(iface)
                numIfaces += 1
        else:
            self.message = "not determined - ansible returned no interface data"
            self.set_state(MapRPrereqCheck.WARN)
            return
        
        if numIfaces > 1:
            self.value = str(ifaces)
            if len(self.mapr_subnet) > 0:
                self.required = "compatible - network interfaces found"
                self.set_state(MapRPrereqCheck.VALID)
            else:
                self.required = "incompatible - multiple network interfaces found, cluster may not" + \
                            " come up unless MAPR_SUBNET is specified"
                self.message = "Detected more than one network interface, did you set MAPR_SUBNET?"
                self.set_state(MapRPrereqCheck.WARN)
        else:
            self.value = ifaces[realIfaceIdx]
            self.set_state(MapRPrereqCheck.VALID)
