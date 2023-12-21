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
#    We expect a simple argument list for this script :
#        ZK_NODES    # comma-separated list of ZK hostnames nodes
#        MAX_WAIT    # maximum wait time in seconds (optional)
MAX_WAIT=${MAX_WAIT:-600}
# On SuSE, use netcat instead of nc
which netcat > /dev/null 2>&1
[ $? -eq 0 ] && NC=netcat || NC=nc
# Not sure how to handle this error.  For now, just bail
[ -z "${ZK_NODES:-}" ] && exit_fail "No Zookeeper nodes specified; will not wait"
# We'll really wait for a quorum of ZK nodes
ZK_QUORUM=0
function find_zk_nodes() {
    for zn in ${ZK_NODES//,/ } ; do
        # srvr cmdn returns "This ZooKeeper instance is not currently serving requests"
        # when we do not have a quorum
        mode=$(echo "srvr" | ${SUDO:-} $NC $zn 5181 | grep Mode | awk '{print $2}')
        case "$mode" in
            follower|leader|standalone)
                ZK_QUORUM=1;;
        esac
        if [ "$ZK_QUORUM" -eq 1 ]; then
            break
        fi
    done
    test 1 -eq $ZK_QUORUM
}

RETRY_TOTAL=$MAX_WAIT && RETRY_SLEEP=5 && run_with_retry find_zk_nodes
if [ $CMD_RET -ne 0 ] && which systemctl > /dev/null 2>&1 ; then
  systemctl stop mapr-zookeeper
fi
[ $CMD_RET -eq 0 ] && exit_change "Zookeeper service on-line" || exit_fail "Failed to detect MapR Zookeeper within $MAX_WAIT seconds.  Confirm that the mapr-zookeeper service is running and that no external firewall is blocking port 5181"