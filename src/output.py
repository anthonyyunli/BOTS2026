# goal: take the info found and output it using the json format as given: 
"""
  "case_id": "subject001",
  "parent": {
    "instance_id": "aorta"
  },
  "daughters": [
    {
      "instance_id": "branch_001",
      "parent_instance_id": "aorta",
      "ostium_xyz_mm": [12.4, -31.8, 184.6],
      "seed_xyz_mm": [15.1, -29.7, 181.2],
      "radius_mm": 2.7,
      "direction_xyz": [0.56, 0.43, -0.71]
    }
  ]
}
"""    
import json
import os

# Three inputs: the subject number, the daughter arteries, and where we should save the JSON
def write_output(case_id, daughters, output_path):
    output = {
        "case_id": case_id,  # so case_id could be subject001 depending on what is given by the user
        "parent": {
            "instance_id": "aorta"
        },
        "daughters": []  # empty list of daughters because we don't know how many in total
    }

    # Go through every daughter in the list to print the findings for each
    for i, daughter in enumerate(daughters, start=1):

        output["daughters"].append({  # .append adds something to the list

            # We want to give each daughter a unique branch number
            "instance_id": f"branch_{i:03d}",

            "parent_instance_id": "aorta",

            # Information from geometry.py will come in
            "ostium_xyz_mm": daughter["ostium_xyz_mm"],
            "seed_xyz_mm": daughter["seed_xyz_mm"],
            "radius_mm": daughter["radius_mm"],
            "direction_xyz": daughter["direction_xyz"],
        })

    output_directory = os.path.dirname(output_path)

    if output_directory:
        os.makedirs(output_directory, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, allow_nan=False)
    return output
