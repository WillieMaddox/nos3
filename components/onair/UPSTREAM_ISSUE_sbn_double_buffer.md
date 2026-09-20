# sbn_adapter: consecutive frames alternate between two stale buffers

#189 mentions this staleness in passing but leaves the design question open; this issue adds measurements of how large the effect is on a live SBN stream, since whatever is decided there probably applies here too.

Observed against `main` (`v0.0.13`).

## What happens

A message that arrives while one buffer is the write target updates that buffer only; the other keeps whatever it last saw. `get_next()` then flips between them every frame, so the consumer gets two partially-stale snapshots in turns rather than one current view.

The behaviour is already noted at `onair/data_handling/sbn_adapter.py:30`:

```python
# Note: The double buffer does not clear between switching. If fresh data doesn't come in, stale data is returned (delayed by 1 frame)
```

The listener writes to `self.currentData[(self.double_buffer_read_index + 1) % 2]` (`get_current_data`, line 183) and `get_next` flips the index and returns the other buffer (lines 143-146). Nothing ever copies a field between the two, so they drift apart field by field depending on which buffer was the write target when each message arrived.

## How to see it

Any deployment where messages arrive slower than the frame rate. Take a single field and read it down consecutive frames: instead of one sequence you get two, taken in turns.

```
frame     1    2    3    4    5    6    7    8
buffer    A    B    A    B    A    B    A    B
value     a₁   b₁   a₁   b₁   a₂   b₁   a₂   b₂
```

Neither value is wrong. Each is that buffer's last known value for the field, and they update independently. A steadily incrementing counter therefore reads as two sequences oscillating around each other rather than as one rising line.

## Why it matters

Measured on one deployment: roughly a tenth of all changing fields alternated on more than half the frames, and for those fields a difference taken between consecutive frames carried **4–6× the spread** of the same difference taken between same-buffer frames. The artifact is larger than the signal it sits on.

Two consequences that bite in practice:

- a frozen field oscillates instead of holding still, so a stalled stream cannot be detected by testing for equality
- a counter appears to step backwards every other frame, so `value < previous` checks fire constantly

Workarounds exist, but each costs sensitivity, and the artifact looks like real vehicle behaviour.

## Possible fix

One option is to blank the frame when the buffer switches. That removes the staleness, but where many message types arrive at different rates most fields would then be empty in most frames, and anyone wanting a current value per field has to add carry-forward back themselves.

An option that keeps frames populated: emit only genuine updates. Compare each incoming frame against a reference for **its own buffer**, write the changed fields to a shared output, and carry the rest forward.

```
for each frame, from buffer b:
    for each field that differs from ref[b]:
        out[field] = new value
    ref[b] = frame
    emit out
```

Fields that have never been received should keep the existing `[0]` placeholder rather than turning blank, or consumers that distinguish "never received" from "received zero" change behaviour silently — related to #154. Either fix changes the values a frame carries without changing the fields themselves, so it is a behavioural change for any downstream consumer.

We have this working offline over recorded data and are happy to open a PR, though #189 probably wants settling first so both adapters behave the same way.
