import glob
import os
import re

from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck, MaprVersion
from ansible.module_utils import six


class PrereqCheckJDK(MapRPrereqCheck):
    def __init__(self, ansible_module):
        super(PrereqCheckJDK, self).__init__(ansible_module, "JDK", "check_jdk")

        self.core_ver = ansible_module.params['core_ver']
        self.prereq_values = ansible_module.params['prereq_values']['jdk']
        self.jdk_missing_msg = self.prereq_values['jdk_missing_message']
        self.jdk_path = self.prereq_values['path']
        self.log_info(("If JAVA_HOME not set, will search in following path: "
                       "{0}").format(self.jdk_path))
        if MaprVersion(self.core_ver) >= MaprVersion("6.2.0"):
            self.min_jdk = 11.0
            self.min_major_jdk = 11
            self.min_minor_jdk = 0
        elif MaprVersion(self.core_ver) >= MaprVersion("6.0.0"):
            self.min_jdk = 1.8
            self.min_major_jdk = 1
            self.min_minor_jdk = 8
        else:
            self.min_jdk = 1.7
            self.min_major_jdk = 1
            self.min_minor_jdk = 7
        self.max_jdk = ansible_module.params['prereq_values']['jdk']['max_jdk']
        self.max_maj_jdk = int(self.max_jdk.split('.')[0])
        self.max_minor_jdk = int(self.max_jdk.split('.')[1])
        self.to_check = ansible_module.params['prereq_values']['jdk']['binaries_to_check']
        if MaprVersion(self.core_ver) >= MaprVersion("6.2.0"):
            self.warn_message = "java or javac not found. OpenJDK 1.11 will be installed by default."
        else:
            self.warn_message = "java or javac not found. OpenJDK 1.8 will be installed by default."

    @staticmethod
    def regexes_match(regex_list, line):
        for regex in regex_list:
            if regex.match(line):
                return True

        return False

    @staticmethod
    def text_in_string(lines, target):
        for line in lines:
            if line in target:
                return True

        return False

    def set_java_version(self, java_version):
        # When version starts not from 1 - it likely to be new version format.
        # ex. 'java 9.0.4' for Oracle JDK 9
        # We can pass here java_version or javac_version and we transform var
        # to type int.
        # From major version 9, Oracle changed version style and now we have no
        # '1' as first version number, ex. 9.0.4 - new version style.
        # Until OpenJDK will not move to new version style we will set major
        # to 1 for backward compatibility in code.

        if java_version is None:
            message = self.warn_message
            warn = True
            value = message
            return None, None, value, warn, message

        for item in java_version:
            if not item:  # If we can`t determine version
                message = self.warn_message
                warn = True
                value = message
                return None, None, value, warn, message
        for idx, elem in enumerate(java_version):
            try:
                java_version[idx] = int(elem)
            except TypeError:  # If we can`t convert version to int.
                self.log_error(("Can not convert each member of list {0} to int,"
                                " var name: {1}".format(java_version,
                                                       java_version.__name__)))
                message = self.warn_message
                warn = True
                value = message
                return None, None, value, warn, message
        # Find real major and minor JDK version.
        minor = java_version[1]
        major = java_version[0]
        return major, minor, None, None, None

    def get_jdk_search_paths(self,):
        java_home = os.getenv("JAVA_HOME")

        java_home_str = False
        if java_home:
            java_home_str = isinstance(java_home, str)

        if java_home and java_home_str:
            base_paths = [java_home]
        else:
            base_paths = self.jdk_path

        paths = map(lambda x: "{0}/bin".format(x), base_paths)
        # TODO remove python2-like behaviour for map
        if six.PY3:
            paths = list(paths)
        paths += os.environ.get('PATH', "").split(":")
        return paths

    def check_java_cmd_version(self, loc, java_cmd):
        self.log_debug("Checking {0} version for: {1}".format(java_cmd, loc))
        # Added new argument 'treat_err_as_info' - is True: log_level
        # will be INFO.
        # We don`t want to confuse people with ERROR in logs
        # if output go to stderr and we expect it to be in stderr.
        out, rv, stderr = self.log_run_cmd("{0} -version".format(loc),
                                           treat_err_as_info=True)
        self.log_debug("rv: '{0}', out: '{1}', stderr: '{2}'".format(rv, out,
                                                                         stderr))
        res = None  # Will trigger WARN in set_java_version
        if not out:
            out = stderr
        if rv != -1:
            if java_cmd == 'java':
                # java -version reports a 3 line output
                # openjdk version "11.0.8" 2020-07-14
                # OpenJDK Runtime Environment (build 11.0.8+10-post-Ubuntu-0ubuntu118.04.1)
                # OpenJDK 64-Bit Server VM (build 11.0.8+10-post-Ubuntu-0ubuntu118.04.1, mixed mode, sharing)
                # just grab the version between the quotes
                res = out.split('"')[1]
            else:
                res = out.split()

            if 'internal' in out or 'internal' in stderr:
                # Fix for '9-internal' as version on Ubuntu.
                if java_cmd == 'java':
                    res = ['1', str(res.split('-')[0])]
                else:
                    res = ['1', str(res[1].split('-')[0])]
            else:
                if java_cmd == 'java':
                    res = res.split(".")[:-1]
                else:
                    res = res[-1].split(".")[:-1]
        self.log_debug("check_java_cmd_version: cmd: {0}, "
                       "res: '{1}'".format(java_cmd, res))
        return res

    def is_java_version_installed(self, found_versions, version):
        if len(found_versions) == 0:
            return False
        else:
            for jdk in found_versions:
                self.log_debug("is_java_version_installed: checking jdk: "
                               "{0}, version: '{1}'".format(jdk, version))
                if len(jdk['java_binary']) == len(version) == 2 and \
                   int(jdk['java_binary'][0]) == version[0] and \
                   int(jdk['java_binary'][1]) == version[1]:
                    self.log_debug("is_java_version_installed: "
                                   "found jdk: {0}, version: '{1}'".format(jdk, version))
                    return True
        return False

    def process(self):
        self.required = "{0}.x".format(self.min_jdk)
        # Something can be done with version in future.
        # Now just collecting them.
        found_versions = []

        for possible_location in self.get_jdk_search_paths():
            javac_loc = os.path.join(possible_location, "javac")
            java_loc = os.path.join(possible_location, "java")
            list_javac_binary = glob.glob(javac_loc)
            for i, java_location in enumerate(glob.glob(java_loc)):
                # Assuming java and javac are in one folder.
                if i < len(list_javac_binary):
                    javac_location = list_javac_binary[i]
                    self.log_debug(("java location: {0}, "
                                    "javac_location: {1}").format(java_location,
                                                                  javac_location))
                    if not any((os.path.exists(java_location),
                               os.path.exists(javac_location))):
                        continue
                        # Return to loop start if there is no such location

                    java_version = self.check_java_cmd_version(java_location, "java")
                    javac_version = self.check_java_cmd_version(javac_location, "javac")
                    if java_version is None or javac_version is None:
                        self.log_error("Failed to get version from java({0}) "
                                       "and/or javac({1})".format(java_location,
                                                                 javac_location))
                        continue
                    if java_version != javac_version:
                        self.log_error(("Version of '{0}' do not match version "
                                        "of '{1}'").format(java_location,
                                                          javac_location))

                    found_versions.append({'java_binary': java_version,
                                           'javac_binary': javac_version})
                else:
                    self.log_debug(("java location returned "
                                    "more entries than javac"))

        # Checking java version that set to default:
        java_version = self.check_java_cmd_version('java', "java")
        if java_version is None:
            self.log_error("The detected Java version could not be found")
        else:
            self.log_info("Detected Java version: {0}".format(str(java_version)))

        javac_version = self.check_java_cmd_version('javac', "javac")
        if javac_version is None:
            self.log_error("The detected JavaC version could not be found")
        else:
            self.log_info("Detected JavaC version: {0}".format(str(javac_version)))

        # If we can`t determine version from calling java or javac - just spawn
        # an error and do not go further.

        if len(found_versions) > 0:
            self.log_info("Found following java jdks installed : {0}".format(str(found_versions)))

        major, minor, value, warn, message = self.set_java_version(java_version)
        if major is None or minor is None:
            self.value = value if value is not None else "Unknown Java"
            if warn is True:
                self.set_state(MapRPrereqCheck.WARN)
            else:
                self.set_state(MapRPrereqCheck.ERROR)
            self.message = message
            return

        jc_major, jc_minor, jc_value, jc_warn, jc_message = self.set_java_version(javac_version)
        if jc_major is None or jc_minor is None:
            self.value = value if value is not None else "Unknown JavaC"
            if jc_warn is True:
                self.set_state(MapRPrereqCheck.WARN)
            else:
                self.set_state(MapRPrereqCheck.ERROR)
            self.message = jc_message
            return

        self.log_debug(("Default java version: {0}, "
                        "default javac_version: {1}").format(java_version,
                                                             javac_version))
        if java_version != javac_version:
            if self.distro == "Ubuntu":
                # If default java version has different version to
                # javac version - likely error in configuring alternatives.
                self.log_error(("Default javac and java binaries have different"
                                " versions. Likely mismatch in alternatives "
                                "configuration. Please fix configuration with"
                                " alternatives or update-alternatives."))
            else:
                # When default java binary has different version to
                # javac version on SUSE or Cent - likely error during
                # uninstalling/configuring.
                self.log_error(("Default javac and java binaries have "
                                "different versions."))
            self.value = ("javac and java versions do not match. "
                          "Fix alternatives configuration!")
            self.set_state(MapRPrereqCheck.ERROR)
            return

        elif major != self.min_major_jdk:
            if self.is_java_version_installed(found_versions, [self.min_major_jdk, self.min_minor_jdk]):
                self.log_info(("Default java version point to unsupported "
                               "version. Default java version is: "
                               "'{0}.{1}'. Installer found valid java "
                               "already installed.").format(*java_version))
                self.value = (("Default java version point to unsupported "
                               "version. Default java version is: "
                               "'{0}.{1}'. Required version is "
                               "'{2!s}'. It is already installed and will "
                               "be used.").format(java_version[0],
                                                  java_version[1],
                                                  self.min_jdk))
                self.set_state(MapRPrereqCheck.VALID)
            else:
                self.log_warn(("Default java version point to unsupported "
                               "version. Default java version is: "
                               "'{0}.{1}'. Installer will automatically "
                               "install maximum supported "
                               "version.").format(*java_version))
                self.value = (("Default java version point to unsupported "
                               "version. Default java version is: "
                               "'{0}.{1}'. Required version is "
                               "'{2!s}'. It will be installed "
                               "automatically.").format(java_version[0],
                                                        java_version[1],
                                                        self.min_jdk))
                self.set_state(MapRPrereqCheck.WARN)
            return
        elif minor != self.min_minor_jdk:
            if self.is_java_version_installed(found_versions, [self.min_major_jdk, self.min_minor_jdk]):
                # Java 8 OK. Java 9 and above should trigger warning.
                if minor > self.max_minor_jdk:
                    self.log_warn(("Default java version point to unsupported "
                                   "version. Default java version is: "
                                   "'{0}.{1}'. Installer found valid java "
                                   "installed and will be using that "
                                   "version.").format(*java_version))
                    if self.max_jdk == self.min_jdk:
                        self.value = (("Default java version is '{1!s}.{2!s}'"
                                       " It is above needed. Required version is "
                                       "'{0!s}'. Installer found valid java "
                                       "installed and will be using that "
                                       "version.").format(self.max_jdk,
                                                                major, minor))
                    else:
                        self.value = (("Default java version is '{2!s}.{3!s}'"
                                       " It is above needed. Required version from "
                                       "'{0!s}' to '{1!s}' Java {1!s} is "
                                       "installed and will be using that "
                                       "version.").format(self.min_jdk,
                                                                self.max_jdk,
                                                                major, minor))
                    self.set_state(MapRPrereqCheck.VALID)
                    return
                elif minor < self.min_minor_jdk:
                    self.log_warn(("Default java version point to unsupported "
                                   "version(maj={0},min={1}, min_maj={2}, "
                                   "min_min={3}). Default java version is: "
                                   "'{4}.{5}', found valid version already "
                                   "installed").format(major, minor,
                                                       self.min_major_jdk,
                                                       self.min_minor_jdk,
                                                       *java_version))
                    self.value = (("Default java version is '{0!s}.{1!s}' It is "
                                   "below needed. Required version from '{2!s}' "
                                   "to '{3!s}'. Found valid version already "
                                   "installed").format(major, minor, self.min_jdk,
                                                     self.max_jdk))
                    self.set_state(MapRPrereqCheck.VALID)
            else:

                # Java 8 OK. Java 9 and above should trigger warning.
                if minor > self.max_minor_jdk:
                    self.log_warn(("Default java version point to unsupported "
                                   "version. Default java version is: "
                                   "'{0}.{1}'. Installer will automatically "
                                   "install maximum supported "
                                   "version.").format(*java_version))
                    if self.max_jdk == self.min_jdk:
                        self.value = (("Default java version is '{1!s}.{2!s}'"
                                       " It is above needed. Required version is "
                                       "'{0!s}'. It will be installed "
                                       "automatically.").format(self.max_jdk,
                                                                major, minor))
                    else:
                        self.value = (("Default java version is '{2!s}.{3!s}'"
                                       " It is above needed. Required version from "
                                       "'{0!s}' to '{1!s}' Java {1!s} will "
                                       "be installed "
                                       "automatically.").format(self.min_jdk,
                                                                self.max_jdk,
                                                                major, minor))
                    self.set_state(MapRPrereqCheck.WARN)
                    return
                elif minor < self.min_minor_jdk:
                    # Ubuntu 16.04 specific check in below if
                    if MaprVersion(self.core_ver) >= MaprVersion("6.0.0") and \
                       self.distro == "Ubuntu" and float(self.distro_ver) < 16.04:
                        if minor <= 8:
                            # Ubuntu below 16.04 require JDK 8 that
                            # is missing in repos.
                            self.value = "{0}.{1}".format(major, minor)
                            self.message = self.jdk_missing_msg.format('8')
                            self.set_state(MapRPrereqCheck.ERROR)
                            return
                    # Other distros have OpenJDK 8 in repos.
                    self.log_warn(("Default java version point to unsupported "
                                   "version(maj={0},min={1}, min_maj={2}, min_min={3}). Default java version is: "
                                   "'{4}.{5}'").format(major, minor, self.min_major_jdk, self.min_minor_jdk,*java_version))
                    self.value = (("Default java version is '{0!s}.{1!s}' It is "
                                   "below needed. Required version from '{2!s}' "
                                   "to '{3!s}' It will get upgraded during "
                                   "install").format(major, minor, self.min_jdk,
                                                     self.max_jdk))
                    self.set_state(MapRPrereqCheck.WARN)

        failed_check = []
        known_java_found = False
        # rpm company
        if self.distro == "CentOS" or self.distro == "SLES" or \
           self.distro == "Rocky" or self.distro == "OracleLinux" or\
           self.distro == "RedHat":
            pattern_openjdk = re.compile(".*java-{0}.{1}.[0-9]-openjdk-.*".format(*java_version))
            pattern_openjdk11 = re.compile(".*java-{0}-openjdk-{0}.*".format(java_version[0]))
            pattern_openjdk_centos6 = re.compile(".*jre-{0}.{1}.[0-9]-openjdk.*".format(*java_version))
            pattern_oracle = re.compile(".*/latest/jre/bin/java.*")
            # rpm unpack oracle jdk to '/usr/java/latest/jre/'
            pattern_oracle_1 = re.compile(".*java/jdk{0}.{1}.[0-9].*".format(*java_version))
            pattern_oracle_2 = re.compile(".*java/jdk\-{0}.{1}.[0-9].*".format(*java_version))
            self.log_debug(("Searching for pattern '{0}' or '{1}' or '{2}' or '{3}' or '{4}' in "
                            "alternatives").format(pattern_openjdk.pattern,
                                                   pattern_openjdk_centos6.pattern,
                                                   pattern_openjdk11.pattern,
                                                   pattern_oracle.pattern,
                                                   pattern_oracle_1.pattern,
                                                   pattern_oracle_2.pattern))
            regexes = [pattern_openjdk, pattern_openjdk11, pattern_openjdk_centos6, pattern_oracle, pattern_oracle_1, pattern_oracle_2]
            alternatives, err_code, alt_err = self.log_run_cmd("alternatives --display java")
            if err_code != 0:
                self.log_debug('Failed to get alternatives: stderr = {0}, err_code = {1}'.format(alt_err, err_code))

            # it looks like communicate returns one single string, vs before we returned an array of strings
            #if len(alternatives) > 1 and len(alternatives[0]) == 1 and len(alternatives[1]) == 1:
            if len(alternatives) > 1:
                list_ = alternatives.splitlines()
            else:
                list_ = alternatives[0].splitlines()
            self.log_debug(list_)
            start_idx = None
            max_idx = None
            for line in list_:
                self.log_debug("idx: {0}, max: {1}".format(start_idx, max_idx))
                if start_idx and start_idx > max_idx:
                    break
                self.log_debug("Checking line '{0}', idx: {1}".format(line, list_.index(line)))
                if self.text_in_string(["family", "priority"], line):
                    if self.regexes_match(regexes, line):
                        known_java_found = True
                        start_idx = list_.index(line)
                        max_idx = start_idx + 25
                        # There can be up to 25 slaves with we need to check after
                        self.log_debug("start: {0}, max: {1}".format(start_idx,
                                                                     max_idx))
                    else:
                        self.log_info("Unknown java found: {0}".format(line))
                        break
                        # we found needed family.
                if "slave" in line and start_idx and start_idx <= max_idx:
                    if self.regexes_match(regexes, line):
                        text = ["Current `best'", "status is auto",
                                "link currently points to"]
                        if self.text_in_string(text, line):
                            start_idx += 1
                            continue
                        if "slave" in line:
                            start_idx += 1
                            app = line.split()
                            app = app[1][:-1]
                            if app in self.to_check:
                                self.log_debug(("Found reference to {0}. "
                                                "Path: {1}. Removing from "
                                                "checklist.").format(app, line))
                                self.to_check.remove(app)
            if len(self.to_check) > 0:
                failed_check = self.to_check

        # And let`s try deb company
        if self.distro == 'Ubuntu':
            if java_version[0] > 1:
                need_version = "java-{0}-openjdk-amd64".format(java_version[0])
                need_version_oracle = "java-{0}-oracle".format(java_version[0])
            else:
                need_version = "java-{0}-openjdk-amd64".format(java_version[1])
                need_version_oracle = "java-{0}-oracle".format(java_version[1])
            for binary in self.to_check:
                alternatives, err_code, alt_err = self.log_run_cmd("update-alternatives --display {0}".format(binary))
                if err_code != 0:
                    self.log_debug('Failed to get update-alternatives: stderr = {0}, err_code = {1}'.format(alt_err, err_code))

                # it looks like communicate returns one single string, vs before we returned an array of strings
                if len(alternatives) > 1 and len(alternatives[0]) == 1 and len(alternatives[1]) == 1:
                    lines = alternatives.splitlines()
                else:
                    lines = alternatives[0].splitlines()

                for line in lines:
                    if 'link currently points to' in line:
                        string = line
                        break
                else:
                    self.value = ("Can not find real path for '{0}'. "
                                  "Please check update-alternatives.").format(binary)
                    self.set_state(MapRPrereqCheck.ERROR)
                    return
                self.log_debug("Checking line: '{0}'".format(string))
                self.log_debug("Expecting version: {0}".format(need_version))
                # If not java-X-openjdk-amd64 and java-X-oracle in string that
                # represent current linked version - treat as error.
                self.log_info("need_version = {0}, need_version_oracle = {1}, string = {2}, java_version = {3}".format(need_version, need_version_oracle, string, java_version))
                if all((need_version not in string,
                       (need_version_oracle not in string))):
                    failed_check.append(binary)
                else:
                    known_java_found = True

        if failed_check and known_java_found:
            self.log_error("Failed to check binaries: {0}".format(failed_check))
            self.value = ("'{0}' points to different version than default Java. "
                          "Fix error with alternatives or update-alternatives "
                          "please.").format("', '".join(failed_check))
            self.set_state(MapRPrereqCheck.ERROR)
            return
        elif not known_java_found:
            self.value = ("Unsupported Java distribution found - ignoring, openjdk {0}.x will be installed".format(self.min_jdk))
            self.set_state(MapRPrereqCheck.WARN)
            return

        self.value = ("Java {0}.{1} detected as default "
                      "and correctly configured.").format(*java_version)
        self.set_state(MapRPrereqCheck.VALID)
