#!/bin/bash
#
# Script to start OnAIR
#

# Runtime deps for the learner plugins. The sequence_detector loads its model as
# an ONNX graph (onnxruntime); it and the rule/consistency/staleness plugins use
# numpy. No sklearn: the IsolationForest + XGBoost frame detectors were retired at
# this cutover.
#
# The container runs as the invoking (non-root) user, and onnxruntime pulls sympy,
# whose wheel writes a man page under /usr/local/share/man (root-only) — a plain
# `pip install` dies there with EACCES and rolls back the whole install. Install
# instead into a host-persistent dir under the repo (bind-mounted, user-writable,
# survives the --rm container) with --target, and put it on PYTHONPATH: --target
# keeps every file, data included, inside that dir. First launch downloads +
# installs (~10 s); later launches reuse it. FAIL LOUD — a detector-less OnAIR must
# never start silently (the old `2>/dev/null || true` hid exactly that).
PYDEPS=/home/maddoxw/git/nasa/nos3/onair_pydeps
export PYTHONPATH="$PYDEPS${PYTHONPATH:+:$PYTHONPATH}"
if ! python3 -c "import onnxruntime" 2>/dev/null; then
  pip install --quiet --target="$PYDEPS" onnxruntime==1.23.2 \
    || { echo "FATAL onair_launch: pip install onnxruntime failed"; exit 1; }
fi
python3 -c "import onnxruntime, numpy" \
  || { echo "FATAL onair_launch: onnxruntime/numpy not importable (see PYTHONPATH=$PYTHONPATH)"; exit 1; }

sleep 20
# -u: unbuffered stdout so the plugins' prints (e.g. [seq] ...) flush to docker
# logs live under the headless launch, instead of block-buffering until exit.
python3 -u cf/onair/driver.py --save cf/onair/nos3_security.ini
