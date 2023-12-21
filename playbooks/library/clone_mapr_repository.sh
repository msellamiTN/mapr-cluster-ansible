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

createDebianRepository() {
    DIR=$1
    mkdir -p $DIR/binary
    mkdir -p $DIR/dists/binary/binary-all
    cat > $DIR/apt-binary-release.conf <<EOM
APT::FTPArchive::Release::Origin "MapR Techonologies, Inc.";
APT::FTPArchive::Release::Label "MapR Techonologies, Inc.";
APT::FTPArchive::Release::Suite "stable";
APT::FTPArchive::Release::Codename "binary";
APT::FTPArchive::Release::Architectures "all";
APT::FTPArchive::Release::Components "binary";
APT::FTPArchive::Release::Description "MapR Techonologies, Inc.";
EOM

    cat > $DIR/apt-ftparchive.conf <<EOM
Dir {
  ArchiveDir ".";
  CacheDir ".";
};

Default {
  Packages::Compress ". gzip bzip2";
  Contents::Compress "gzip bzip2";
};

BinDirectory "dists" {
  Packages "binary/Packages";
  Contents "binary/Contents-all";
};

Tree "dists" {
  Sections "binary";
  Architectures "all";
};

Default {
  Packages {
    Extensions ".deb";
  };
};
EOM

    cat > $DIR/dists/Release <<EOM
Architectures: all
Codename: binary
Components: binary
Date: $(date)
Description: MapR Techonologies, Inc.
Label: MapR Techonologies, Inc.
Origin: MapR Techonologies, Inc.
Suite: stable
EOM
}

# At the top-level of the Debian repository create the indexing script
# $1 - the pathname of where the Debian repository was to be created.
createDebianArchiveScript() {
    DIR=$1/$REPO
    cd $DIR
    cat > $DIR/update-archive.sh <<EOM
#!/bin/bash -x

cd $DIR

apt-ftparchive generate apt-ftparchive.conf
apt-ftparchive -c apt-binary-release.conf release dists/binary >dists/Release

EOM
    chmod 755 update-archive.sh
}

# Set up for different distribution.  We'll use "package.ezmeral.hpe.com",
# since that is guaranteed to have the tarballs with all the packages.
echo "${REPO_ARG}" | grep -q "^[1-9]"
if [ $? -eq 0 ] ; then
    REPO_TOP="${REPO_URL}/v${REPO_ARG}"
elif [ $REPO_ARG = "ecosystem" ] ; then
    REPO_TOP="${REPO_URL}/ecosystem"
else
    exit_fail "Error: unrecognized repo specification ($REPO_ARG)"
fi

# TO BE DONE: check for SUSE zypper as well
if which dpkg &> /dev/null ; then
    REPO_TOP=${REPO_TOP}/ubuntu
    HTTPD_TOP=/var/www
    THIS_DISTRO=Debian
elif which rpm &> /dev/null ; then
    REPO_TOP=${REPO_TOP}/redhat
    HTTPD_TOP=/var/www/html
    THIS_DISTRO=RedHat
else
    exit_fail "Unrecognized Linux system; unable to create local repository"
fi

# Make sure we have a location for the repository 
#	Default: the HTTPD_TOP directory for the distribution
if [ -z "${LOCAL_REPO_PATH}" ] ; then
    LOCAL_REPO_PATH=$HTTPD_TOP/mapr/$(basename ${REPO_TOP%/*})
    [ ! -d $HTTPD_TOP ] && LOG_WARN "Defaulting to HTTPD data directory for "
        "repository location, but $HTTPD_TOP directory does not yet exist. "\
        "Please install the HTTP service on this node."
fi
if [ ! -d $LOCAL_REPO_PATH ] ; then
    LOG_RUN_CMD mkdir -p $LOCAL_REPO_PATH
    [ $CMD_RET -ne 0 ] && exit_fail "Could not create local repository path ($LOCAL_REPO_PATH)"
fi

pkg=$(curl $REPO_TOP/ 2> /dev/null | grep -e "\.tgz" | cut -d\" -f8)
[ -z "${pkg}" ] && exit_fail "No packages found in $REPO_TOP"

REPO_TARBALL=${REPO_TOP}/$pkg
LOG "Downloading $REPO_TARBALL to /tmp, (will display curl status-bar)"

#	For debug, only download if it's not already there
if [ ! -r /tmp/$pkg ] ; then
    LOG_RUN_CMD curl $REPO_TARBALL -o /tmp/$pkg
    [ $CMD_RET -ne 0 ] && exit_fail "Error: Failed to download $REPO_TARBALL to /tmp/$pkg"
fi

#	TO BE DONE: be smarter here about overwriting files
if [ $THIS_DISTRO = "RedHat" ] ; then
    LOG "Extracting packages to $LOCAL_REPO_PATH"
    tar x -C $LOCAL_REPO_PATH -f /tmp/$pkg
    [ $? -ne 0 ] && exit_fail "Error: Extraction of $pkg to $LOCAL_REPO_PATH failed"
    LOG "Generating repository artifacts"
    createrepo $LOCAL_REPO_PATH
elif [ $THIS_DISTRO = "Debian" ] ; then
    createDebianRepository     "$LOCAL_REPO_PATH"
    createDebianArchiveScript  "$LOCAL_REPO_PATH"
    LOG "Extracting packages to $LOCAL_REPO_PATH/dists/binary"
    LOG_RUN_CMD tar x -C $LOCAL_REPO_PATH/dists/binary -f /tmp/$pkg
    [ $CMD_RET -ne 0 ] && exit_fail "Extraction of $pkg to $LOCAL_REPO_PATH failed"
    LOG "Generating repository artifacts"
    $LOCAL_REPO_PATH/update-archive.sh
fi

[ ! -d $LOCAL_REPO_PATH/pub ] && mkdir $LOCAL_REPO_PATH/pub
[ ! -f $LOCAL_REPO_PATH/pub/gnugpg.key ] && curl -o $LOCAL_REPO_PATH/pub/gnugpg.key $REPO_URL/pub/gnugpg.key 2> /dev/null
[ ! -f $LOCAL_REPO_PATH/pub/maprgpg.key ] && curl -o $LOCAL_REPO_PATH/pub/maprgpg.key $REPO_URL/pub/maprgpg.key 2> /dev/null
# Test that the repo is accessible vi http://
if [ ${LOCAL_REPO_PATH#$HTTPD_TOP} != ${LOCAL_REPO_PATH} ] ; then
    LOG "Verifying access to newly generated repository"
    curl http://localhost/${LOCAL_REPO_PATH#$HTTPD_TOP}/ 2> /dev/null |  grep -e "mapr" | cut -d\" -f8
fi

# ??? Should we add details regarding how to use the repo here ???
[ ${LOCAL_REPO_PATH#$HTTPD_TOP} != ${LOCAL_REPO_PATH} ] && \
    local_repo="http://$(hostname -s)/${LOCAL_REPO_PATH#$HTTPD_TOP}" || \
    local_repo="file://${LOCAL_REPO_PATH}"
exit_change "SUCCESS; Repository is available at $local_repo"
