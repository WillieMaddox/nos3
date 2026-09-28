#!/bin/bash
#
# Convenience script for NOS3 development
# Use with the Dockerfile in the deployment repository
# https://github.com/nasa-itc/deployment
#

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
source $SCRIPT_DIR/env.sh

# NOS3 GPIO
rm -rf /tmp/gpio_fake

# NOS3 Stored HK
rm -rf $BASE_DIR/fsw/build/exe/cpu1/scratch/*

# Docker stop
cd $SCRIPT_DIR; $DFLAG compose down > /dev/null 2>&1
$DCALL ps --filter ancestor="$DBOX" -aq | xargs $DCALL stop > /dev/null 2>&1 &
$DCALL ps --filter=name="^sc0" -aq | xargs $DCALL stop > /dev/null 2>&1 &
$DCALL ps --filter=name="nos_*" -aq | xargs $DCALL stop > /dev/null 2>&1 &
$DCALL ps --filter=name="ait*" -aq | xargs $DCALL stop > /dev/null 2>&1 &
# $DCALL ps --filter=name="influxdb*" -aq | xargs $DCALL stop > /dev/null 2>&1 &
$DCALL ps --filter=name="ttc-command*" -aq | xargs $DCALL stop > /dev/null 2>&1 &

# Intentionally wait to complete
wait 

# Docker cleanup
$DCALL container prune -f > /dev/null 2>&1

# Disconnect COSMOS operator from NOS3 networks before removing them
$DCALL network disconnect nos3-sc01 cosmos-openc3-operator-1 > /dev/null 2>&1
$DCALL network disconnect nos3-core cosmos-openc3-operator-1 > /dev/null 2>&1
# Remove NOS3 networks (-q avoids header line in xargs, "nos3-" avoids matching unrelated networks)
$DCALL network ls --filter=name="nos3-" -q | xargs $DCALL network rm > /dev/null 2>&1
$DCALL network rm nos3-core > /dev/null 2>&1
rm /dev/shm/Blackboard 2> /dev/null

# 42
rm -rf $USER_NOS3_DIR/42/NOS3InOut
rm -rf /tmp/gpio*

# COSMOS
yes | rm $GSW_DIR/Gemfile > /dev/null 2>&1
yes | rm $GSW_DIR/Gemfile.lock > /dev/null 2>&1

exit 0
