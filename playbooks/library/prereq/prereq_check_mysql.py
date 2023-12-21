from __future__ import print_function

import os
import sys

from contextlib import contextmanager
from ansible.module_utils.mapr_prereq_check import MapRPrereqCheck
from ansible.module_utils import pymysql


# this should work on python2 as well
@contextmanager
def redirect_stdout(new_target):
    old_target, sys.stdout = sys.stdout, new_target
    try:
        yield new_target
    finally:
        sys.stdout = old_target


class PrereqCheckMySQL(MapRPrereqCheck):
    """This prereq check tries to check connectivity to SQL server

    It use bundled pymysql which is pure-python realization of MySQL client.
    """

    def __init__(self, ansible_module):
        super(PrereqCheckMySQL, self).__init__(ansible_module, "MySQL", "check_mysql")

        self.use_external_mysql = self.ansible_module.params['use_external_mysql']
        self.fresh_install = self.ansible_module.params['fresh_install']
        self.security = self.ansible_module.params['security']
        self.mysql_host = self.ansible_module.params['mysql_host']
        self.db_admin_user = self.ansible_module.params['db_admin_user']
        self.db_admin_password = self.ansible_module.params['db_admin_password']
        self.db_admin_password_set = self.ansible_module.params['db_admin_password_set']
        self.use_shared_mysql = self.ansible_module.params['use_shared_mysql']
        self.mysql_socket = self.ansible_module.params['mysql_socket']
        self.fqdn = ansible_module.params['fqdn']

    def process(self):
        # We run prereq when secure cluster used and shared mysql used and it is not fresh install,
        # when it is fresh installation with external database and password provided,
        # when it is incremental install with external database and password provided,
        # otherwise - skip.
        skip = True
        if not self.fresh_install and self.security and self.use_shared_mysql and self.fqdn == self.mysql_host:
            skip = False
        if self.fresh_install and self.use_external_mysql and self.db_admin_password:
            skip = False
        if not self.fresh_install and self.use_external_mysql and self.db_admin_password:
            skip = False

        if skip is True:
            self.value = "Skipped"
            self.required = "Skipped"
            self.set_state(MapRPrereqCheck.VALID)
            return
        if not self.db_admin_password and self.db_admin_password_set:
            if self.security and self.use_shared_mysql:
                self.value = "Missing DB password."
                self.required = "DB Password should be provided."
                self.set_state(MapRPrereqCheck.ERROR)
                return
        # Good to go, let`s check connectivity
        self.required = "Connected"
        connection = None
        if self.use_shared_mysql:
            host = 'localhost'
        else:
            host = self.mysql_host
        try:
            with open(os.devnull, 'w') as f, redirect_stdout(f):
                if self.db_admin_password:
                    self.log_debug("mysql: Trying sql connection with pw")
                    connection = pymysql.connect(host=host,
                                                 user=self.db_admin_user,
                                                 password=self.db_admin_password)
                else:
                    self.log_debug("mysql: Trying sql connection without pw")
                    try:
                        self.log_debug("mysql: Trying sql connection without pw - no socket")
                        connection = pymysql.connect(host=host,
                                                 user=self.db_admin_user)
                    except Exception as exc:
                        self.log_debug("mysql: Exception - connection without pw didn't work - socket={0}".format(self.mysql_socket))
                        if self.mysql_socket is not None and self.mysql_socket != '':
                            self.log_debug("mysql: Trying sql connection without pw - socket")
                            connection = pymysql.connect(host=host,
                                                 unix_socket=self.mysql_socket,
                                                 user=self.db_admin_user)
                            self.log_debug("mysql: Trying sql connection without pw - socket - succeeded")
                        else:
                            self.log_debug("mysql: Trying sql connection without pw - socket - but no socket given")
                            raise Exception("mysql: Network connections failed, but no unix socket to fallback on")
        except Exception as exc:
            self.log_debug("mysql: connections to mysql failed - either configuration issue, network issue or authentication issue")
            mysqltype = "embedded"
            if self.use_shared_mysql:
                mysqltype = "shared"
                mysqlconnectivity_msg = ""
            if self.use_external_mysql:
                mysqlconnectivity_msg = " and connectivity"
                mysqltype = "external"
            self.value = 'Could not connect to {0} MySQL on host: {1} - check database admin pw{2}'.format(mysqltype, host, mysqlconnectivity_msg,)
            self.set_state(MapRPrereqCheck.ERROR)
            self.log_error("Error: {}".format(exc))
            return

        finally:
            if connection is not None:
                connection.close()

        self.value = "Connected"
        self.set_state(MapRPrereqCheck.VALID)
