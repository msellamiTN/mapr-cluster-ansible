#!/bin/bash
#
# (c) 2017 MapR Technologies, Inc. All Rights Reserved.
#
# Begin autogenerated shell template

if [ -n "$DEBUG" ] && [ "$DEBUG" -eq 1 ]; then
    set -x
    exec 2> /tmp/do_cfg_$$.out
fi

SED_EXP="s/\s?\([^=]+\)\s?=\s?\(\x22\([^\x22]+\)\x22|\x27\([^\x27]+\)\x27|\(\S+\)\)\s?/\1='\2'/p"
[ -n "${1}"  -a  -f "${1}" ] && eval $(sed -e ${SED_EXP} $1)

function exit_change() {
    exit_helper "\"changed\":true, " "$@"
}

function exit_no_change() {
    exit_helper "\"changed\":false, " "$@"
}

function exit_fail() {
    exit_helper "\"failed\":true, " "$@"
}

function exit_helper() {
    [ -n "${LOGLINES}" ] && log_lines=", \"mapr_logs\":\"${LOGLINES}\""
    echo "{ $1 \"msg\":\"$2\" ${log_lines} }"
    exit 0
}

function LOG() {
    local msg="$@"
    [ "INFO" != "$1" -a "ERROR" != "$1" -a "WARN" != "$1" ] && msg="INFO $@"
    local print_var="$(date +"%F %T %Z") $LOG_LEVEL $(echo "$msg"|tr '\n' ' '|tr '\r' ' '|tr '\"' ' '|tr "\'" ' '|tr '\000-\037' ' ')"
    [ -n "${LOGLINES}" ] && print_var="${LOGLINES}\n${print_var}"
    printf -v LOGLINES "%s" "${print_var}"
}

function LOG_ERROR() {
    LOG "ERROR" "$@"
}

function LOG_INFO() {
    LOG "INFO" "$@"
}

function LOG_WARN() {
    LOG "WARN" "$@"
}

function LOG_RUN_CMD() {
    local cmdstr="$(echo "$@" | cut -d' ' -f1)"
    run_cmd "$@"
    show_cmd_res "$@"
    echo "$@" | grep -q "timeout -s HUP" && check_timeout "$cmdstr" $CMD_RET
}

function run_cmd() {
    local cmd="$@"
    CMD_RES="$(eval $cmd 2>&1)"
    CMD_RET=$?
}

function show_cmd_res() {
    local msg="Command: $@, Status: ${CMD_RET}, Result: ${CMD_RES}"
    [ $CMD_RET -eq 0 ] && LOG_INFO $msg  || LOG_ERROR $msg
}

function exit_with_cmd_ret() {
    local ret=$1
    [ -z "$ret" ] && ret=$CMD_RET
    local script_name="$(basename $0)"
    [ $ret -eq 0 ] && exit_change "${script_name} passed" || exit_fail "${script_name} failed"
}

function run_with_retry() {
    RETRY_SLEEP=${RETRY_SLEEP:-1}
    RETRY_TOTAL=${RETRY_TOTAL:-1}
    local rem_time=$RETRY_TOTAL
    while [ $rem_time -gt 0 ] ; do
        run_cmd "$@"
        [ $CMD_RET -eq 0 ] && break
        sleep $RETRY_SLEEP
        rem_time=$[rem_time - $RETRY_SLEEP]
    done
    show_cmd_res "$@"
    [ $CMD_RET -ne 0 ] && LOG_ERROR "command failed after waiting ${RETRY_TOTAL} seconds, sleeping ${RETRY_SLEEP} seconds between each retry"
}

function get_timeout() {
    local val
    [ -n "$1" ] && val="$1" || val="2"
    local unit
    [ -n "$2" ] && unit="$2" || unit="m"
    type timeout > /dev/null 2>&1 && TIMEOUT="timeout -s HUP ${val}${unit}" || LOG_WARN "timeout cmd not found"
}

function check_timeout() {
    local retval
    local cmdstr=""
    [ -n "$1" ] && cmdstr="($1)"
    [ -n "$2" ] && retval=$2 || retval=$?
    [ $retval -eq 124 ] && LOG_WARN $1 "Command${cmdstr} timed out "
}

[ $(id -u) -ne 0 ] && SUDO="sudo"

LOG "Running $(basename $0)"
# End autogenerated shell template
PACKAGES="$PACKAGE_NAME=$PACKAGE_VERSION.*"
DEPENDS=$(apt-cache depends $PACKAGES | grep 'Depends: mapr-' | grep -v '|' | egrep -v 'mapr-client|mapr-core' | cut -d: -f2)
for depend in $DEPENDS; do
    PACKAGES="$PACKAGES $depend=$PACKAGE_VERSION.*"
done
LOG_RUN_CMD apt-get --allow-unauthenticated -q -y install $PACKAGES
exit_with_cmd_ret
