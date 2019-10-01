#!/bin/bash

# wrapper script for unoconv to filter annoying messages from soffice.bin

PVS_UID=${PVS_UID:-"0"}
PVS_SOFFICE_ADDR=${PVS_SOFFICE_ADDR:-"127.0.0.1"}
PVS_SOFFICE_PORT=${PVS_SOFFICE_PORT:-"2002"}
PVS_USER="$(id -un ${PVS_UID})"

START_SOFFICE=false
START_PREVIEW=false
HOME=/tmp

cleanup() {
    if [ "${START_SOFFICE}" == true ]; then
        echo "Stopping unoconv..."
    fi
    if [ "${START_PREVIEW}" == true ]; then
        echo "Stopping preview server..."
    fi
    exit
}

trap cleanup INT TERM

while true;
do
    if [ "$1" == "soffice" ]; then
        START_SOFFICE=true
    elif [ "$1" == "preview" ]; then
        START_PREVIEW=true
    else
        break
    fi
    shift
done

if [ "${START_PREVIEW}" == true ]; then
    echo "Starting preview server..."
    python3 -m preview &
fi

if [ "${START_SOFFICE}" == false ]; then
    wait
    exit
fi

# dconf complains when LibreOffice starts...
mkdir -p ${HOME}/.cache/dconf
chown -R ${PVS_UID} ${HOME}/.cache

echo "Starting unoconv..."
while true;
do
    su -p -s /bin/bash - ${PVS_USER} -c "/usr/local/bin/unoconv --listener --server=${PVS_SOFFICE_ADDR} --port=${PVS_SOFFICE_PORT} 2>&1 | grep -v func=xmlSecCheckVersionExt"

    echo "Restarting unoconv..."
    sleep 1
done
