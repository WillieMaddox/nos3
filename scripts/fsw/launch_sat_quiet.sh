#!/bin/bash
#
# Headless mirror of cfg/build/launch.sh.
# Used by `make launch-quiet` for automated reset/verification testing.
#
# Differences from cfg/build/launch.sh:
#   - All containers are started with `docker run -d` instead of a
#     gnome-terminal tab + `docker run -it`.
#   - The 42 graphics container omits `-e DISPLAY` and the X11 socket bind.
#   - No firefox is launched for the OpenC3 web UI.
#   - The FSW container still uses `fsw_respawn.sh` as its entrypoint so that
#     `kill -TERM core-cpu1` results in a Tier-1 PO restart inside the same
#     container (matches `cfg/build/launch.sh`, NOT `scripts/ci_launch.sh`).
#
# `cfg/build/launch.sh` and `scripts/fsw/launch_sat.sh` are intentionally left
# untouched.

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
source $SCRIPT_DIR/../env.sh

if [ ! -d $USER_NOS3_DIR ]; then
    echo ""
    echo "    Need to run make prep first!"
    echo ""
    exit 1
fi

if [ ! -d $BASE_DIR/cfg/build ]; then
    echo ""
    echo "    Need to run make config first!"
    echo ""
    exit 1
fi

# Detached variant of $DFLAGS (-it -> -d -t -i). Mounts /etc/passwd and /etc/group
# read-only and runs as the host user, same as the interactive launcher.
# All three flags matter:
#   -d : background, so the script can move on to the next container
#   -i : stdin held open. nos_engine_server_standalone and cryptolib's
#        ./support/standalone print an interactive menu/banner and exit at
#        stdin EOF if there is no stdin attached.
#   -t : allocate a pseudo-TTY. cFS (core-cpu1) wedges inside CFE_FS_EarlyInit
#        without a TTY on its stdio — the FSW container appears Up but
#        core-cpu1 sits in hrtimer_nanosleep with no progress, no SBN, no
#        telemetry, no OnAIR CSV. With -t cFS proceeds normally and TimeTics
#        advance.
DRUN="${DFLAGS/-it/-d -t -i}"

echo "Make data folders..."
mkdir $FSW_DIR/data 2> /dev/null
mkdir $FSW_DIR/data/cam 2> /dev/null
mkdir $FSW_DIR/data/evs 2> /dev/null
mkdir $FSW_DIR/data/hk 2> /dev/null
mkdir $FSW_DIR/data/inst 2> /dev/null
touch $FSW_DIR/data/dummy.txt
echo "1234567890" > $FSW_DIR/data/dummy.txt
truncate -s 1M $FSW_DIR/data/dummy.txt
mkdir /tmp/nos3 2> /dev/null
mkdir /tmp/nos3/data 2> /dev/null
mkdir /tmp/nos3/data/cam 2> /dev/null
mkdir /tmp/nos3/data/evs 2> /dev/null
mkdir /tmp/nos3/data/hk 2> /dev/null
mkdir /tmp/nos3/data/inst 2> /dev/null
mkdir /tmp/nos3/uplink 2> /dev/null
cp $BASE_DIR/fsw/build/exe/cpu1/cf/cfe_es_startup.scr /tmp/nos3/uplink/tmp0.so 2> /dev/null
cp $BASE_DIR/fsw/build/exe/cpu1/cf/sample.so /tmp/nos3/uplink/tmp1.so 2> /dev/null

echo "Create ground networks..."
$DNETWORK inspect nos3-core > /dev/null 2>&1 || \
$DNETWORK create \
    --driver=bridge \
    --subnet=192.168.41.0/24 \
    --gateway=192.168.41.1 \
    nos3-core
echo ""

# GSW (cosmos-openc3-operator-1) is expected to be already running from
# ~/.nos3/cosmos/openc3.sh start. The quiet variant does NOT open firefox.
export GSW="cosmos-openc3-operator-1"

echo "Create NOS interfaces..."
export GND_CFG_FILE="-f nos3-simulator.xml"
$DRUN -v $SIM_DIR:$SIM_DIR --name "nos-terminal"     --network=nos3-core -w $SIM_BIN $DBOX ./nos3-single-simulator $GND_CFG_FILE stdio-terminal
$DRUN -v $SIM_DIR:$SIM_DIR --name "nos-udp-terminal" --network=nos3-core -w $SIM_BIN $DBOX ./nos3-single-simulator $GND_CFG_FILE udp-terminal
$DRUN -v $SIM_DIR:$SIM_DIR --name "nos-sim-bridge"   --network=nos3-core -w $SIM_BIN $DBOX ./nos3-sim-cmdbus-bridge $GND_CFG_FILE
echo ""

# Single-spacecraft, matching cfg/build/launch.sh.
export SATNUM=1

for (( i=1; i<=$SATNUM; i++ ))
do
    export SC_NUM="sc0"$i
    export SC_NETNAME="nos3-"$SC_NUM
    export SC_CFG_FILE="-f nos3-simulator.xml"

    echo $SC_NUM " - Create spacecraft network..."
    $DNETWORK inspect $SC_NETNAME > /dev/null 2>&1 || $DNETWORK create $SC_NETNAME 2> /dev/null
    echo ""

    echo $SC_NUM " - Connect GSW ${GSW:-cosmos-openc3-operator-1} to spacecraft network..."
    $DNETWORK connect $SC_NETNAME "${GSW:-cosmos-openc3-operator-1}" --alias cosmos --alias active-gs 2> /dev/null || true
    echo ""

    echo $SC_NUM " - 42 (headless: X11 mounts skipped, Graphics Front End disabled)..."
    rm -rf $USER_NOS3_DIR/42/NOS3InOut
    cp -r $BASE_DIR/cfg/build/InOut $USER_NOS3_DIR/42/NOS3InOut
    # 42 calls freeglut/glutInit unconditionally when "Graphics Front End?" is
    # TRUE and aborts with ExitCode=1 if no DISPLAY is available. Patch the
    # runtime copy of Inp_Sim.txt only (the source cfg/InOut/Inp_Sim.txt and
    # cfg/build/InOut/Inp_Sim.txt are left untouched, so `make launch` still
    # gets the GUI).
    sed -i 's/^TRUE\(\s*!  Graphics Front End?\)/FALSE\1/' $USER_NOS3_DIR/42/NOS3InOut/Inp_Sim.txt
    $DRUN -v $USER_NOS3_DIR:$USER_NOS3_DIR --name $SC_NUM"-fortytwo" -h fortytwo --network=$SC_NETNAME -w $USER_NOS3_DIR/42 $DBOX $USER_NOS3_DIR/42/42 NOS3InOut
    echo ""

    echo $SC_NUM " - OnAIR..."
    $DRUN -v $BASE_DIR:$BASE_DIR -v /home/maddoxw/git/nasa/ainos3/data:/home/maddoxw/git/nasa/ainos3/data --name $SC_NUM"-onair" --network=$SC_NETNAME -w $FSW_DIR $DBOX $SCRIPT_DIR/fsw/onair_launch.sh
    echo ""

    echo $SC_NUM " - Flight Software..."
    cd $FSW_DIR
    $DRUN -v $BASE_DIR:$BASE_DIR --name $SC_NUM"-nos-fsw" -h nos-fsw --network=$SC_NETNAME -w $FSW_DIR --sysctl fs.mqueue.msg_max=10000 --ulimit rtprio=99 --cap-add=sys_nice $DBOX $SCRIPT_DIR/fsw/fsw_respawn.sh
    echo ""

    echo $SC_NUM " - Simulators..."
    cd $SIM_BIN
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-nos-engine-server" -h nos-engine-server --network=$SC_NETNAME -w $SIM_BIN $DBOX /usr/bin/nos_engine_server_standalone -f $SIM_BIN/nos_engine_server_config.json
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-truth42sim"        -h truth42sim        --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE truth42sim

    $DNETWORK connect $SC_NETNAME nos-terminal     2> /dev/null || true
    $DNETWORK connect $SC_NETNAME nos-udp-terminal 2> /dev/null || true
    $DNETWORK connect $SC_NETNAME nos-sim-bridge   2> /dev/null || true

    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-cam-sim"      --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE camsim
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-css-sim"      --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-css-sim
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-eps-sim"      --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-eps-sim
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-fss-sim"      --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-fss-sim
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-gps-sim"      --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE gps
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-imu-sim"      --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-imu-sim
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-mag-sim"      --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-mag-sim
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-rw-sim0"      --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-reactionwheel-sim0
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-rw-sim1"      --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-reactionwheel-sim1
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-rw-sim2"      --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-reactionwheel-sim2
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-radio-sim"    -h radio-sim --network=$SC_NETNAME --network-alias=radio-sim -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-radio-sim
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-sample-sim"   --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE sample-sim
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-startrk-sim"  --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-star-tracker-sim
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-thruster-sim" --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-thruster-sim
    $DRUN -v $SIM_DIR:$SIM_DIR --name $SC_NUM"-torquer-sim"  -h trq-sim   --network=$SC_NETNAME -w $SIM_BIN $DBOX ./nos3-single-simulator $SC_CFG_FILE generic-torquer-sim
    echo ""

    echo $SC_NUM " - CryptoLib..."
    $DRUN -v $BASE_DIR:$BASE_DIR --name $SC_NUM"_cryptolib_gsw" --network=$SC_NETNAME --network-alias=cryptolib -w $BASE_DIR/gsw/build $DBOX ./support/standalone
    echo ""
done

echo "NOS Time Driver..."
sleep 8
$DRUN -v $SIM_DIR:$SIM_DIR --name nos-time-driver --network=nos3-core -w $SIM_BIN $DBOX ./nos3-single-simulator $GND_CFG_FILE time
sleep 1
for (( i=1; i<=$SATNUM; i++ ))
do
    export SC_NUM="sc0"$i
    export SC_NETNAME="nos3-"$SC_NUM
    $DNETWORK connect --alias nos-time-driver $SC_NETNAME nos-time-driver 2> /dev/null || true
done
echo ""

echo "Headless docker satellite launch script completed."
