
# Drop this in the “targets/NOS3/procedures” directory and then rebuild the COSMOS plugin. Then run it from the “Script Runner” in the COSMOS UI.

import random

from openc3.script import *  # type: ignore

cmd_list = get_all_cmds("NOS3")  # type: ignore

for i in range(120):
    index = random.randint(0, len(cmd_list))
    message = cmd_list[index]

    target_name = message["target_name"]
    packet_name = message["packet_name"]
    params = ""
    for item in message["items"]:
        if item["data_type"] == "DERIVED":
            continue
        if item["data_type"] == "STRING":
            val = f"'{item["default"]}'"
        else:
            val = item["default"]
        name = item["name"]
        params += f"{name} {val}, "

    params = params[:-2]

    print(f"{target_name} {packet_name} with {params}")
    cmd(f"{target_name} {packet_name} with {params}")  # type: ignore

    # Small delay between iterations
    wait(1)  # type: ignore
