#!/bin/bash
#
# Script to start OnAIR
#

# Install runtime dependencies needed by the IsolationForest learner plugin
# (sklearn for the model, numpy as a transitive dep). pip is fast enough
# (~5s) to comfortably finish before the 20s SBN-handshake settle below;
# run BEFORE the sleep so the driver never imports a missing module.
# Versions track what train.py was last run with — see project memory.
pip install --quiet scikit-learn==1.7.2 numpy 2>/dev/null || true

sleep 20
python3 cf/onair/driver.py --save cf/onair/nos3_security.ini
