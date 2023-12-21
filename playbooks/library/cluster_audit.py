import getpass
import sys
import os

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.mapr_base import MapRBase
from ansible.module_utils import six
from pwd import getpwuid, getpwnam

UBUNTU = "ubuntu"
CENTOS = "centos"
REDHAT = "redhat"
SLES = "sles"
SUSE = "suse"
PROP = "prop"
CMP = "cmp"
GTE = ">="
LT = "<"
DISTRO = "distro"
DISTROS = "distros"
DISTRO_VER = "distro_ver"


class ClusterAudit(MapRBase):
    def __init__(self, module):
        self.module = module
        self.warnings = False
        self.msg = ""
        self.distro = module.params['distro'].lower()

        # noinspection PyBroadException
        try:
            ver = module.params['distro_ver']
            self.distro_ver = float('.'.join(ver.split('.')[:2]))
        except Exception:
            self.distro_ver = 0.0
        self.admin_user = module.params["admin_user"]

    @staticmethod
    def read_firstline(path):
        if os.path.isfile(path) and os.access(path, os.R_OK):
            with open(path) as file_d:
                line = file_d.readline().strip()
            return line

        raise MaprException("Cannot read file: {0}".format(path))

    @staticmethod
    def read_lines(path):
        if os.path.isfile(path) and os.access(path, os.R_OK):
            with open(path) as file_d:
                lines = file_d.readlines()
            return lines

        raise MaprException("Cannot read file: {0}".format(path))

    def run_all(self):
        audits = []
        for audit in audits:
            self.run(audit)
        if self.warnings:
            self.module.exit_json(msg=self.msg, warnings="True",
                mapr_logs=self.get_logs())
        else:
            self.module.exit_json(msg=self.msg, mapr_logs=self.get_logs())

    def run(self, audit):
        try:
            audit()
        except MaprException as exc:
            self.warnings = True
            self.msg += str(exc)
        except Exception as exc:
            self.warnings = True
            self.msg += "Audit failed unexpectedly on line {0} due to " \
                "exception {1}".format(sys.exc_info()[-1].tb_lineno, exc)

    def log_info_warn(self, prop, expected, actual, comp=None, msg=""):
        if comp is None:
            comp = expected == actual
        txt = "{0}, Expected: {1}, Actual: {2}".\
            format(prop, expected, actual)
        if comp is False:
            self.warnings = True
        self.log_info(txt) if comp else self.log_warn(txt)
        if (comp is False) and msg:
            self.log_warn(msg)

    def check_tmp(self):
        actual_perm = oct(os.stat("/tmp").st_mode & int('1777', 8))[-4:]
        self.log_info_warn("/tmp permission", "1777", actual_perm)

    def check_procfs(self):
        proc_vals = [
            {"path": "/proc/sys/vm/swappiness", "exp": "1"},
            {"path": "/proc/sys/net/ipv4/tcp_retries2", "exp": "5"},
            {"path": "/proc/sys/vm/overcommit_memory", "exp": "0"}
        ]

        for prop in proc_vals:
            path = prop.get("path")
            self.log_info_warn(path, prop.get("exp"), ClusterAudit.read_firstline(path))

    def check_basedir(self):
        owner = getpwuid(os.stat("/opt/mapr").st_uid).pw_name
        self.log_info_warn("/opt/mapr owner", "root", owner)

    def check_locale(self):
        out, code, _ = self.run_cmd("locale")
        if code != 0:
            self.warnings = True
            return
        lang = out.split("LANG=")[-1].split(".")[0]
        self.log_info_warn("locale", "en_US", lang, msg="Run locale cmd for more details")

    def check_limits(self):
        def is_valid(prop_val, expr):
            # noinspection PyBroadException
            try:
                valid = prop_val == "unlimited"
                valid = valid or int(prop_val) >= expr
            except Exception:
                valid = False
            return valid

        def_lims = self.get_default_limits()
        out, _, _ = self.run_cmd("grep -e nproc -e nofile /etc/security/limits.d/*.conf"
                            " /etc/security/limits.conf")

        data = filter(lambda line: len(line.strip()) > 0, out.split("\n"))
        data = filter(lambda line: line.find("No such") == -1, data)
        data = map(lambda line: line.split(":")[-1], data)
        data = filter(lambda line: len(line.strip()) > 0, data)
        data = filter(lambda line: line.strip()[0] != '#', data)
        data = map(lambda line: line.split(), data)
        data = filter(lambda line: len(line) >= 4, data)
        exp = 32000

        props = ["nproc", "nofile"]
        users = [getpass.getuser()]
        # noinspection PyBroadException
        try:
            getpwnam(self.admin_user)
            users.append(self.admin_user)
        except Exception:
            self.log_info("{0} limits for cluster admin user: {1} will not be "
                "checked as the user does not exist".format(props,
                self.admin_user))

        for user in users:
            for prop in props:
                try:
                    val = self.get_limit_for_user(user, data, prop)
                except MaprException as exc:
                    val = def_lims.get(prop)
                    if val is None:
                        self.log_warn(exc)
                if val is not None:
                    valid_res = is_valid(val, exp)
                    self.log_info_warn("{0} for user {1}".format(prop, user),
                        "{0} {1}".format(GTE, exp), val, valid_res)

    @staticmethod
    def get_limit_for_user(user, data, prop):
        res = filter(lambda aline: aline[0] == user, data)
        res = [line[3] for line in res if line[2] == prop]
        try:
            res = res[-1]
        except Exception:
            raise MaprException("Property {0} not found for user {1}".format(
                prop, user))
        return res

    @staticmethod
    def get_default_limits():
        res = {}
        lines = ClusterAudit.read_lines("/proc/1/limits")
        key_map = {"open files": "nofile", "processes": "nproc"}
        for key, val in six.iteritems(key_map):
            items = [line for line in lines if line.find(key) != -1]
            if len(items) > 0:
                splt_line = items[-1].split(key)[1].strip()
                res[val] = splt_line.split()[0]
        return res

    def check_thp(self):
        paths = map(lambda item: "/sys/kernel/mm/" + item +
                    "transparent_hugepage/enabled", ["", "redhat_"])
        line = ""
        prop = "Transparent hugepage compaction enabled?"
        for path in paths:
            try:
                line = ClusterAudit.read_firstline(path)
                break
            except MaprException:
                pass
        if not line:
            raise MaprException("{0} not found in these paths"
                                " {1}".format(prop, paths))
        self.log_info_warn(prop, "'never' or '[never] ...'", line,
            line.find("[never]") != -1 or line == "never",
            msg="Check {0} for more details".format(paths))

    def get_checkable_svcs(self):
        svc_list = [
            {PROP: {"ufw": False}, DISTROS: [{DISTRO: UBUNTU}]},
            {PROP: {"apparmor": False}, DISTROS: [{DISTRO: UBUNTU}]},
            {PROP: {"iptables": False}, DISTROS: [
                {DISTRO: CENTOS, DISTRO_VER: 7, CMP: LT},
                {DISTRO: REDHAT, DISTRO_VER: 7, CMP: LT},
                {DISTRO: SLES},
                {DISTRO: SUSE}
            ]},
            {PROP: {"ip6tables": False}, DISTROS: [
                {DISTRO: CENTOS, DISTRO_VER: 7, CMP: LT},
                {DISTRO: REDHAT, DISTRO_VER: 7, CMP: LT},
                {DISTRO: SLES},
                {DISTRO: SUSE}
            ]},
            {PROP: {"firewalld": False}, DISTROS: [
                {DISTRO: CENTOS, DISTRO_VER: 7, CMP: GTE},
            ]},
            {PROP: {"ntp": True}, DISTROS: [
                {DISTRO: SLES, DISTRO_VER: 12, CMP: LT},
                {DISTRO: SUSE, DISTRO_VER: 12, CMP: LT},
                {DISTRO: UBUNTU},
            ]},
            {PROP: {"ntpd": True}, DISTROS: [
                {DISTRO: CENTOS},
                {DISTRO: REDHAT},
                {DISTRO: SLES, DISTRO_VER: 12, CMP: GTE},
                {DISTRO: SUSE, DISTRO_VER: 12, CMP: GTE},
            ]},
        ]
        svcs = {}
        for svc in svc_list:
            for distro_attr in svc.get(DISTROS):
                if not self.attr_is_valid(distro_attr):
                    continue
                svcs.update(svc.get(PROP))
        return svcs

    def attr_is_valid(self, attr):
        if attr.get(DISTRO) != self.distro:
            return False
        op = attr.get(CMP)
        ver = attr.get(DISTRO_VER)
        valid = op is None
        valid = valid or op == LT and self.distro_ver < ver
        valid = valid or op == GTE and self.distro_ver >= ver
        return valid

    def check_active_svcs(self):
        svcs = self.get_checkable_svcs()
        for svc, exp in six.iteritems(svcs):
            self.log_info_warn("Service {0} is running?".format(svc), exp,
                self.is_svc_active(svc),
                msg="Check 'service status {0}' for more details".format(svc))

    def is_svc_active(self, svc):
        enabled = False
        # noinspection PyBroadException
        try:
            out, code, _ = self.run_cmd("service {0} status".format(svc))
            enabled = code == 0
        except Exception:
            pass
        return enabled

    def check_selinux(self):
        enabled = False
        path = "/etc/selinux/config"
        # noinspection PyBroadException
        try:
            lines = self.read_lines("/etc/selinux/config")
            lines = filter(lambda line: len(line.strip()) > 0, lines)
            lines = filter(lambda line: line.strip()[0] != '#', lines)
            lines = map(lambda line: line.find("SELINUX=enforcing") != -1, lines)
            enabled = len(lines) > 0 and lines[-1] is True
        except Exception:
            pass
        self.log_info_warn("SELinux enabled?", False, enabled,
            msg="Check {0} for more details".format(path))

    def check_enc_blkdevs(self):
        enabled = False
        path = "/etc/crypttab"
        # noinspection PyBroadException
        try:
            lines = self.read_lines(path)
            lines = filter(lambda line: len(line.strip()) > 0, lines)
            lines = filter(lambda line: line.strip()[0] != '#', lines)
            enabled = len(lines) > 0
            if enabled:
                self.log_warn("Encrypted block devices:\n{0}".format(lines))
        except Exception:
            pass
        self.log_info_warn("Encrypted block devices present?", False, enabled,
            msg="Check {0} for more details".format(path))


class MaprException(Exception):
    pass


ClusterAudit(AnsibleModule(argument_spec=dict(
    admin_user=dict(type='str'),
    distro=dict(type='str'),
    distro_ver=dict(type='dict')
))).run_all()
