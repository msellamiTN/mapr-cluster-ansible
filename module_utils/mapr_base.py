#!/usr/bin/env python
#
# (c) 2020 MapR Technologies, Inc. All Rights Reserved.
#
# Mapr python template for all MapR custom modules

import os
import shlex
import subprocess
import tempfile
import time
from functools import reduce
from ansible.module_utils import six


class MapRBase(object):
    """TODO: Play around with getattr to filter messages by level"""
    _TIMEOUT = 124
    _BLACKLIST = ["password", "pass_word", "secret"]
    _HIDDEN = "**logline hidden due to sensitive data**"
    LOGLINES = []

    @staticmethod
    def get_logs():
        return "\\n".join(MapRBase.LOGLINES)

    @staticmethod
    def get_logs_list():
        return MapRBase.LOGLINES

    def log(self, msg, level):
        if not isinstance(msg, str):
            msg = str(msg)

        if six.PY3:
            cannot_log = [msg.lower().find(badword) != -1 for badword in MapRBase._BLACKLIST]
        else:
            cannot_log = map(lambda badword: msg.lower().find(badword) != -1, MapRBase._BLACKLIST)
        cannot_log = reduce(lambda x, y: x or y, cannot_log, False)

        if cannot_log:
            msg = MapRBase._HIDDEN

        new_msg = "{0} {1} {2}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), level, msg)
        MapRBase.LOGLINES.append(new_msg)

    def log_error(self, msg):
        self.log(msg, "ERROR")

    def log_info(self, msg):
        self.log(msg, "INFO")

    def log_warn(self, msg):
        self.log(msg, "WARN")

    def log_warning(self, msg):
        self.log(msg, "WARNING")

    def log_debug(self, msg):
        self.log(msg, "DEBUG")

    def log_run_cmd(self, cmd, env_dict=None, shell=False, executable=None,
                    treat_err_as_info=False, return_on_first_failure=False, debug=False):

        msg = "Attempting to run command: '{0}'".format(cmd)
        for attr in [env_dict, shell, executable]:
            if attr:
                msg = "{0}, {1}".format(msg, attr)

        self.log_debug(msg)
        result, code, error = self.run_cmd(cmd, env_dict, shell,
                                           executable, treat_err_as_info,
                                           return_on_first_failure, debug)
        self.show_cmd_res(cmd, result, code, treat_err_as_info)
        return result, code, error

    def run_cmd(self, cmd, env_dict=None, shell=False, executable=None, treat_err_as_info=False,
                return_on_first_failure=True, debug=False):

        res_out = None
        res_err = None
        res_out_file = None
        err_code = 0
        conf_env = os.environ.copy()
        if env_dict and isinstance(env_dict, dict):
            for key, val in six.iteritems(env_dict):
                if val:
                    conf_env[key] = val
        qry_list = cmd if isinstance(cmd, list) else [cmd]
        qry_list = [q if isinstance(q, str) else str(q) for q in qry_list]
        qry_list = list([q.encode("ascii") for q in qry_list])
        for qry in qry_list:
            if six.PY2:
                args = qry if shell else shlex.split(qry)
            else:
                args = qry if shell else shlex.split(qry.decode("utf-8"))
            try:
                proc = subprocess.Popen(args=args, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, stdin=res_out_file,
                                        shell=shell, executable=executable,
                                        env=conf_env)
                res_out, res_err = proc.communicate()
                err_code = proc.returncode
              
                if res_out is not None:
                    res_out = res_out.decode('utf-8', 'xmlcharrefreplace')
                    res_out = res_out.strip()
                if res_err is not None:

                    res_err = res_err.decode('utf-8')
                    res_err = res_err.strip()
                if debug:
                    with open('/tmp/run_cmd_{0}.txt'.format(os.getpid()), "a+") as file:
                        file.write('qry = {0}, res_out = {1}, res_err = {2}, err_code = {3}\n'
                                   .format(qry, res_out, res_err, err_code))
                if err_code != 0:
                    if res_err and treat_err_as_info:
                        self.log_info("stderr output: '{0}'".format(res_err))
                    elif res_err:
                        self.log_error("stderr output: '{0}'".format(res_err))
                    if return_on_first_failure:
                        return res_out, err_code, res_err
                if res_out_file is not None and not self.debug:
                    res_out_file.delete()
                if len(qry_list) > 1:
                    if six.PY3:
                        res_out_file = tempfile.NamedTemporaryFile(mode="w", encoding='utf-8')
                    else:
                        res_out_file = tempfile.NamedTemporaryFile()
                    res_out_file.write(res_out)
                    res_out_file.seek(0)
            except Exception as exc:
                err_msg = "Unable to run run command" \
                          " {0} gave exception: {1}".format(qry, exc)
                with open('/tmp/run_cmd_fail_{0}.txt'.format(os.getpid()), "a+") as file:
                    file.write(err_msg + '\n')
                self.log_error(err_msg)
                if return_on_first_failure:
                    return "", -1
                else:
                    err_code = -1
            if err_code != 0 and return_on_first_failure:
                break
        if six.PY2:
            value = "timeout -s HUP"
        else:
            value = b"timeout -s HUP"
        if qry_list[0].find(value) != -1 and err_code == MapRBase._TIMEOUT:
            self.log_warn("Command '{0}' timed out".format(qry_list[0]))
        if res_out is None:
            res_out = ""
        if res_err is None:
            res_err = ""
        return res_out, err_code, res_err

    def show_cmd_res(self, cmd, result, code, treat_err_as_info=False):
        msg = "Command: '{0}', Status: '{1}', Result: '{2}'".format(cmd, code, result)
        if treat_err_as_info:
            self.log_info(msg)
        elif code != 0:
            self.log_error(msg)
        elif code == 0:
            self.log_debug(msg)

    def get_timeout(self, val=2, unit="m"):
        res = ""
        try:
            _, code, _ = self.run_cmd("which timeout")
            if code == 0:
                res = "timeout -s HUP {0}{1}".format(val, unit)
        except Exception:
            pass
        return res

    def check_timeout(self, cmd, code):
        if code == MapRBase._TIMEOUT:
            self.log_warn("Command timed out : {0}".format(cmd))

