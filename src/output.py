'''
This produces the JSON.

For example:

{
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

'''
