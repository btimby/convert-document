#!/bin/bash

# wrapper script for unoconv
#
# This script does the following:
# - Can start preview server, soffice or both.
# - If starting preview server, it backgrounds it.
# - If starting soffice, it runs unoconv and backgrounds it.
# - It monitors unoconv, if the process dies it is restarted.
# - It performs a health check by performing a simple conversion.
# - If the health check fails, unoconv is killed and restarted.

PVS_UID=${PVS_UID:-"0"}
PVS_SOFFICE_ADDR=${PVS_SOFFICE_ADDR:-"127.0.0.1"}
PVS_SOFFICE_PORT=${PVS_SOFFICE_PORT:-"2002"}
PVS_USER="$(id -un ${PVS_UID})"

START_SOFFICE=false
START_PREVIEW=false
HOME=/tmp

info() {
    DATE=$(date)
    echo "${DATE} $1"
}

cleanup() {
    if [ "${START_SOFFICE}" == true ]; then
        info "Stopping unoconv..."
    fi
    if [ "${START_PREVIEW}" == true ]; then
        info "Stopping preview server..."
    fi
    exit
}

trap cleanup INT TERM

while true; do
    if [ "$1" == "soffice" ]; then
        START_SOFFICE=true
    elif [ "$1" == "preview" ]; then
        START_PREVIEW=true
    else
        break
    fi
    shift
done

if [ "${START_PREVIEW}" == false && "${START_SOFFICE}" == false ]; then
    eval $@
    exit
fi

if [ "${START_PREVIEW}" == true ]; then
    info "Starting preview server..."
    python3 -m preview &
fi

if [ "${START_SOFFICE}" == false ]; then
    wait
    exit
fi

# dconf complains when LibreOffice starts...
mkdir -p ${HOME}/.cache/dconf
chown -R ${PVS_UID} ${HOME}/.cache

while true; do
    info "Starting unoconv..."
    su -p -s /bin/bash - ${PVS_USER} -c "/usr/local/bin/unoconv -vvv --listener --server=${PVS_SOFFICE_ADDR} --port=${PVS_SOFFICE_PORT} 2>&1 | grep -v func=xmlSecCheckVersionExt" &
    PID=$!

    while true; do
        sleep 10
        # If process has died, restart it.
        pkill -0 soffice.bin > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            info "Unoconv died"
            break
        fi

        # Perform health check.
        timeout 10 bash -c "echo 'Hello world' | unoconv --server=127.0.0.1 --port=2002 --stdin --stdout > /dev/null 2>&1"
        if [ $? -ne 0 ]; then
            info "Health check failed, killing unoconv"
            pkill -9 soffice.bin
            break
        fi
        info "Unoconv is alive"
    done
done
