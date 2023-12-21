#!/bin/bash

function exit_jre_no_change() {
    exit_jre_helper "false" "$@"
}

function exit_jre_change() {
    exit_jre_helper "true" "$@"
}

function exit_jre_helper() {
    local changed=$1
    shift
    exit_helper "\"version\":\"${j_maj}.${j_min}\", \"jre_only\":\"${JRE_ONLY}\", \"changed\":${changed}, " "$@"
}

function checkJavaVersion() {
    export JDK_REQUIRED=1
    export JDK_QUIET_CHECK=1

    # see if we have a compatible JDK installed
    . "${JAVA_ENV_CHECK_SCRIPT}"
    if [ -z "${JAVA_HOME}" ] ; then
        # we didn't find the complete jdk - look for jre
        export JDK_REQUIRED=0
        . "${JAVA_ENV_CHECK_SCRIPT}"
        [ -n "${JAVA_HOME}" ] && JRE_ONLY=1
    fi

    RV=1
    if [ -n "${JAVA_HOME}" ] ; then
        j_maj=$($JAVA_HOME/bin/java -version 2>&1 | head -n1 | cut -d '.' -f 1)
        j_maj=${j_maj/java version \"} # remove unwanted text
        j_maj=${j_maj/openjdk version \"} # openjdk 8 has a different string
        j_min=$($JAVA_HOME/bin/java -version 2>&1 | head -n1 | cut -d '.' -f 2)
        if [ ${j_maj} -ge $1 ] ; then
            if [ ${j_maj} -eq $1 -a ${j_min} -lt $2 ] ; then
                RV=1 # minor version to low
            else
                [ ${JRE_ONLY} -eq 1 ] && RV=2 || RV=0
            fi
        else
            RV=1 # major version to low
        fi
    fi
    return ${RV}
}

j_maj=0
j_min=0
JRE_ONLY=0
[ -z "${MIN_JAVA_VERSION}" ] && exit_jre_no_change "MIN_JAVA_VERSION not set"
[ -z "${JAVA_ENV_CHECK_SCRIPT}" ] && exit_jre_no_change "JAVA_ENV_CHECK_SCRIPT not set"
[ ! -e "${JAVA_ENV_CHECK_SCRIPT}" ] && exit_jre_no_change "JAVA_ENV_CHECK_SCRIPT does not exist"
# if we do an upgrade we need to make sure tell env.sh what the min is for the version we are upgrading to
if [ "$IS_UPGRADE" -eq 1 ]; then
    export MAPR_UPGRADE_MIN_JAVA_VER=${MIN_JAVA_VERSION}
    export MAPR_UPGRADE_MAX_JAVA_VER=${MAX_JAVA_VERSION}
else
    export MAPR_MIN_JAVA_VER=${MIN_JAVA_VERSION}
    export MAPR_MAX_JAVA_VER=${MAX_JAVA_VERSION}
fi
IFS='.' read -a JAVA_VERSION <<< "${MIN_JAVA_VERSION}"
[ ${#JAVA_VERSION[@]} -ne 2 ] && exit_jre_no_change "Invalid JAVA_VERSION ${MIN_JAVA_VERSION}. Must be of the form: x.y"
checkJavaVersion ${JAVA_VERSION[@]}
RV=$?
if [ ${RV} -eq 1 ]; then
    exit_jre_no_change "requires a minimum java version of ${MIN_JAVA_VERSION}"
elif [ ${RV} -eq 2 ] ; then
    exit_jre_change "minimum java version requirement met. But only JRE is installed. Upgrade to JDK will be performed"
else
    exit_jre_change "minimum java version requirement met"
fi
