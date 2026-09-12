'''
Once we've identified a daughter artery (a final branch), we need 4 things:

- Ostium: Where the artery leaves the aorta
- Seed: A point 5 mm outward from the ostium along the vessel
- Radius: Local vessel radius at the seed
- Direction: Unit vector pointing from the ostium into the branch

ostium = fimd_ostium(...)
seed = find_seed(...)
direction = calculate_direction(...)
radius = estimate_radius(...)

'''
