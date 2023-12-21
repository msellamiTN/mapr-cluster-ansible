import json
import os

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck


class PrereqCheckDisks(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckDisks, self).__init__(ansible_module, "Disks", "check_disks")

        self.disks = ansible_module.params['disks'].split(',') if ansible_module.params['disks'] else None
        self.devices = json.loads(ansible_module.params['devices']) if ansible_module.params['devices'] else None
        self.mounts = json.loads(ansible_module.params['mounts']) if ansible_module.params['mounts'] else None
        self.lvm = json.loads(ansible_module.params['lvm']) if ansible_module.params['lvm'] else None
        self.prereq_values = ansible_module.params['prereq_values']['disk']
        self.machine_ram = self.ansible_module.params['ram'] / 1024  # Calculating GBs.
        self.disk_min_size_to_check = self.machine_ram
        self.root_device = None

    def find_real_root(self):
        real_root, _, _ = self.log_run_cmd("findmnt -n -o SOURCE /")
        self.log_debug("Real root is {}".format(real_root))
        self.root_device = real_root.split('/')[2]

    @staticmethod
    def disk_size_str(size):
        words = size.split(' ')
        if len(words) < 2:
            words[1] = '?'
        return "{0:.1f} {1}".format(float(words[0]), words[1])

    def get_mountpoint(self, name, broken_fdisk):
        if name == self.root_device:
            return '/'

        mounts = []
        for mount in self.mounts:
            if mount["device"].endswith(name):
                mounts.append(mount["mount"])
                self.log_debug("{} mounted at {}".format(name, mount["mount"]))
            # # hack for broken Ubuntu 14 with nvme in cloud
            # if 'nvme' in name and broken_fdisk and mount["device"].endswith(name + 'p1'):
            #     mounts.append(mount["mount"])
        if len(mounts) == 1:
            return mounts[0]
        elif len(mounts) > 1:
            # for filesystems like zfs, btrfs the same disk will be listed as device
            # for many mount points - the shortest name is likely the best representation for
            # the root - for example '/'
            return min(mounts, key=len)

        return None

    def get_swapdisk(self, name, broken_fdisk, fdisk_output):
        os_release_file = open('/etc/os-release')
        os_release_info = os_release_file.readlines()
        id_line = [match for match in os_release_info if match.startswith("ID=")]
        if id_line is not None and len(id_line) > 0 and ('sles' in id_line[0] or 'suse' in id_line[0]):
            is_suse_release = True
        else:
            is_suse_release = False

        if self.debug:
            self.log_info("get_swapdisks: is_os_release={0}, id_line={1}".format(is_suse_release, id_line))

        # don't check for swap device in fdisk output if it is broken or on
        # non suse systems. The other distros populate the holders info correctly
        if broken_fdisk or (not is_suse_release):
            return None

        swap_matches = [match for match in fdisk_output.split('\n') if "swap" in match]

        if self.debug:
            self.log_info("get_swapdisks: matches={0}".format(swap_matches))

        for swap_dev_line in swap_matches:
            s_dev = swap_dev_line.split(" ")[0]
            if s_dev is not None and os.path.basename(s_dev) == name:
                if self.debug:
                    self.log_info("get_swapdisks: found swap dev={0}".format(s_dev))
                return s_dev
        return None

    def is_disk_available(self, name, broken_fdisk, fdisk_output):
        self.log_debug("Checking if {} is available".format(name))
        mount_point = self.get_mountpoint(name, broken_fdisk)
        if mount_point is not None:
            self.log_debug("{} can not be used".format(name))
            return False, mount_point
        swap_disk = self.get_swapdisk(name, broken_fdisk, fdisk_output)
        if swap_disk is not None:
            return False, 'used_as_swap'
        self.log_debug("{} can be used".format(name))
        return True, None

    def select_disk(self, disk_name, disk_size, available, mount_point, select_by_default, disk_detail, found_list):
        disk_aliases = []
        if self.debug:
            self.log_info("select_disk: name={0}, avail={1}, mount={2}, sbd={3}".format(disk_name, available, mount_point, select_by_default))

        selected = available
        if not select_by_default and available:
            selected = False

            if len(disk_aliases) > 0:
                if self.debug:
                    self.log_info("select_disk: disk_aliases={0}".format(disk_aliases))
                for disk_da in disk_aliases:
                    if any(disk_name == os.path.basename(alias) for alias in disk_da):
                        selected = True
                        if self.debug:
                            self.log_info("select_disk: alias found for {0}".format(disk_name))
                        break
                    if not selected:
                        if any(os.path.basename(disk_name) == os.path.basename(alias) for alias in disk_da):
                            selected = True
                            if self.debug:
                                self.log_info("select_disk: alias found for {0}".format(os.path.basename(disk_name)))
                        else:
                            if self.debug:
                                self.log_info("select_disk: no alias found")
            else:
                if self.debug:
                    self.log_info("select_disk: looking for {0} in {1}".format(disk_name, self.disks))
                # does absolute path match?
                if any(disk_name == name for name in self.disks):
                    selected = True
                    if self.debug:
                        self.log_info("select_disk: found absolute match for {0}".format(disk_name))
                if not selected:
                    for path_prefix in ('/dev', '/dev/mapper', 'mapper'):
                        if self.debug:
                            self.log_info("select_disk: trying for rel match for {0} - removing {1}".format(disk_name, path_prefix))
                        if any(os.path.relpath(disk_name, path_prefix) == os.path.relpath(name, path_prefix) for name in self.disks):
                            selected = True
                            if self.debug:
                                self.log_info("select_disk: trying for rel match for {0} - removing {1}".format(disk_name, path_prefix))
                            break
                if not selected:
                    if self.debug:
                        self.log_info("select_disk: trying for base match for {0}".format(disk_name))
                    if any(os.path.basename(disk_name) == os.path.basename(name) for name in self.disks):
                        selected = True
                        if self.debug:
                            self.log_info("select_disk: found base match for {0}".format(disk_name))

        unavailable_msg = mount_point
        if not available and mount_point:
            if 'used_as_swap' in mount_point:
                unavailable_msg = "Disk used for swap"
            elif 'used_as_thin_pool' in mount_point:
                unavailable_msg = "Disk used as thin pool"
            else:
                unavailable_msg = "Disk mounted at {0}".format(mount_point)
        elif any(name in disk_size for name in ('MB', 'KB')) or \
                ('GB' in disk_size and float(disk_size.split(' ')[0]) < self.disk_min_size_to_check):
            selected = False
            available = False
            unavailable_msg = "Disk size less than {0} GB".format(self.disk_min_size_to_check)

        found_output = "/dev/{0}".format(disk_name)

        found_list.update({found_output: {"selected": selected, "size": self.disk_size_str(disk_size)}})
        found_list[found_output].update(disk_detail)

        if not available:
            found_list[found_output].update({"unavailable": unavailable_msg})

        return selected

    def get_lvm_size(self, disk_name):
        name_parts = disk_name.rsplit('-', 1)
        if len(name_parts) > 0:
            lv_name = name_parts[-1]
            vg_name = name_parts[0].replace('--', '-')
        else:
            lv_name = disk_name
            vg_name = disk_name

        dsize = None
        if self.lvm is not None and 'lvs' in self.lvm and self.lvm["lvs"] and \
                len(self.lvm["lvs"]) > 0 and lv_name in self.lvm["lvs"]:
            if self.debug:
                self.log_info('get_lvm_size: lv_name={0}, vg_name={1}, vg={2}'.format(lv_name, vg_name, self.lvm['lvs'][lv_name]['vg']))
            if vg_name == self.lvm['lvs'][lv_name]['vg']:
                dsize = self.lvm['lvs'][lv_name]['size_g']
                return '{0} GB'.format(dsize)
        return dsize

    def process(self):
        self.find_real_root()
        disks_found = {}
        a_disk_is_available = False
        broken_fdisk = False

        # Get disks as known by fdisk
        fdisk_output, _, _ = self.log_run_cmd("fdisk -l")

        if self.debug:
            self.log_info('process: fdisk_output={0}'.format(fdisk_output))

        # check for broken Ubuntu 14 and nvme disks
        if fdisk_output is None or (fdisk_output is not None and len(fdisk_output) == 0):
            broken_fdisk = True

        # if no disk names provided, choose available disks
        select_by_default = True if self.disks is None else False

        # Process all disks and partitions
        for dev, dev_val in self.devices.items():
            # if fdisk does not know about it, skip it (skips cdrom, fd)
            if fdisk_output is not None and len(fdisk_output) > 0 and dev not in fdisk_output:
                continue

            disk_size = None
            mount_point = None
            disk_details = {"supportDiscard": dev_val['support_discard'],
                            "sectorSize": dev_val['sectorsize'],
                            "rotational": dev_val['rotational']}
            if self.debug:
                self.log_debug("For disk {0} found: {1}".format(dev, dev_val))

            if self.debug:
                self.log_info("check_disk: dev={0}, dev_val={1}".format(dev, dev_val))

            if "holders" in dev_val and self.devices[dev]["holders"] and len(self.devices[dev]["holders"]) > 0:
                if self.debug:
                    self.log_info('check_disk: Checking holders for dev={0}, dev_val={1}'.format(dev, dev_val))
                for h in dev_val["holders"]:
                    available, mount_point = self.is_disk_available(h, broken_fdisk, fdisk_output)
                    disk_name = "mapper/{0}".format(h)
                    disk_size = dev_val["size"]  # How to find size of individual if there
                    # are more than 1?
                    if self.debug:
                        self.log_info('check_disk: Found luks dev={0}, size={1}, '
                                      'avail={2}, mnt={3}'.format(disk_name, dev_val["size"], available, mount_point))
                    if self.select_disk(disk_name, disk_size, available, mount_point, select_by_default, disk_details, disks_found):
                        a_disk_is_available = True
            elif "partitions" in dev_val and self.devices[dev]["partitions"] and len(self.devices[dev]["partitions"]) > 0:
                disks_found.update({"/dev/{0}".format(dev): {"selected": False,
                                                             "size": self.disk_size_str(dev_val["size"]),
                                                             "unavailable": "disk has partitions"}})
                disks_found["/dev/{0}".format(dev)].update(disk_details)
                for part, part_val in dev_val["partitions"].items():
                    if self.debug:
                        self.log_info('check_disk: Checking partition={0}, part_val={1}'.format(part, part_val))
                    if part_val["holders"] and len(part_val["holders"]) > 0:
                        for h in part_val["holders"]:
                            if 'swap' in h:
                                available = False
                                mount_point = None
                            else:
                                available, mount_point = self.is_disk_available(h, broken_fdisk, fdisk_output)
                                disk_name = h
                                disk_size = self.get_lvm_size(disk_name)
                                if disk_size is None:
                                    disk_size = part_val["size"]
                                    available = False  # This is typically a thin volume meta container
                                    mount_point = 'used_as_thin_pool'
                                if self.debug:
                                    self.log_info('check_disk: Found part dev={0}, '
                                                  'size={1}, avail={2}, mnt={3}'.format(disk_name, disk_size, available,
 mount_point))
                                if self.select_disk(disk_name, disk_size, available, mount_point, select_by_default, disk_details, disks_found):
                                    a_disk_is_available = True
                    else:
                        available, mount_point = self.is_disk_available(part, broken_fdisk, fdisk_output)
                        disk_name = part
                        disk_size = part_val["size"]
                        if self.debug:
                            self.log_info('check_disk: Found part dev={0}, size={1}, '
                                          'avail={2}, mnt={3}'.format(disk_name, disk_size, available, mount_point))
                        if self.select_disk(disk_name, disk_size, available, mount_point, select_by_default, disk_details, disks_found):
                            a_disk_is_available = True
            else:
                available, mount_point = self.is_disk_available(dev, broken_fdisk, fdisk_output)
                disk_name = dev
                disk_size = dev_val["size"]
                if self.debug:
                    self.log_info('check_disk: Found raw dev={0}, size={1}, avail={2}, '
                                  'mnt={3}'.format(disk_name, dev_val["size"], available, mount_point))
                if self.select_disk(disk_name, disk_size, available, mount_point, select_by_default, disk_details, disks_found):
                    a_disk_is_available = True

        disk_list = disks_found.keys()
        if self.debug:
            self.log_debug("DISK_LIST: {0}".format(disk_list))
            self.log_debug("DISK_FOUND: {0}".format(disks_found))
        self.additional_payload.update({"disks": disks_found})

        # Why do we send back available disks as required?
        self.value = ", ".join([] if self.disks is None else self.disks)
        self.required = ", ".join(disk_list)
        self.set_state(MapRPrereqCheck.VALID)
        if not select_by_default:
            unknown_disks = list(set(sorted(self.disks)) - set(sorted(disk_list)))
            self.log_info('unknown_disks: {0}, disk_list: {1}, self.disks: {2}'.format(unknown_disks, disk_list, self.disks))
            if unknown_disks:
                self.required = ", ".join(self.disks)
                self.set_state(MapRPrereqCheck.WARN)
                # Test if none of the disks matched.
                no_matched_disks = list(set(sorted(self.disks)) - set(sorted(unknown_disks)))
                if no_matched_disks is None or not no_matched_disks:
                    self.set_state(MapRPrereqCheck.ERROR)
                else:
                    self.log_debug("NO_MATCHED_DISKS: {0}".format(no_matched_disks))
                    a_disk_is_selected = False
                    for disk in no_matched_disks:
                        if 'selected' in disks_found[disk] and disks_found[disk]["selected"]:
                            self.log_debug("no_matched_disks: {0} - selected".format(disk))
                            a_disk_is_selected = True

                    self.value = ", ".join(no_matched_disks)
                    if not a_disk_is_selected:
                        self.value = []
                        self.required = "Specified disks not found - {0}".format(no_matched_disks)
                        self.set_state(MapRPrereqCheck.ERROR)
            else:
                a_disk_is_selected = False
                for disk in disks_found:
                    if 'selected' in disks_found[disk] and disks_found[disk]["selected"]:
                        a_disk_is_selected = True
                if not a_disk_is_selected:
                    disk_msg = ""
                    for disk in self.disks:
                        if len(disk_msg) > 0:
                            disk_msg += ", "
                        if 'unavailable' in disks_found[disk]:
                            disk_msg += "{0} not selected because {1}".format(disk, disks_found[disk]["unavailable"])
                        else:
                            disk_msg += "{0} not selected because of constraint".format(disk)
                    self.required = "At least one disk is required - {0}".format(disk_msg)
                    self.set_state(MapRPrereqCheck.ERROR)
        elif not a_disk_is_available:
            self.required = "At least one disk is required"
            self.set_state(MapRPrereqCheck.ERROR)

