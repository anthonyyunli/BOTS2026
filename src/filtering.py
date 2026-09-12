'''
Algorithm will probably initially find too many things (false positives)

We need to eliminate:
- noise
- unrelated vessels
- artifacts
- vessels branching from another daughter
- cropping edges
- duplicate detections

'''

"""Filter candidate daughter-vessel detections."""

import numpy as np


def filter_candidates(
    candidates,
    image_shape,
    spacing,
    min_volume_mm3=1.0,
    edge_margin_mm=2.0,
    duplicate_distance_mm=2.0,
):
    """
    Remove obvious false-positive candidate detections.

    Parameters
    ----------
    candidates : list of dict
        Candidates returned by detection.py.

    image_shape : tuple
        Image shape in NumPy order:
            (z, y, x)

    spacing : tuple
        Voxel spacing in SimpleITK order:
            (x, y, z)

    min_volume_mm3 : float
        Minimum connected-component volume to keep.

    edge_margin_mm : float
        Distance from the cropped image boundary within which
        candidates are considered edge candidates.

    duplicate_distance_mm : float
        Candidates closer than this distance are treated as
        duplicates.

    Returns
    -------
    filtered_candidates : list of dict
        Candidates that survive the filters.
    """

    if not candidates:
        return []

    filtered = []

    # ---------------------------------------------------------
    # 1. Remove extremely small components
    # ---------------------------------------------------------

    for candidate in candidates:

        if candidate["volume_mm3"] < min_volume_mm3:
            continue

        filtered.append(candidate)

    # ---------------------------------------------------------
    # 2. Remove candidates too close to the crop boundary
    # ---------------------------------------------------------

    spacing_xyz = np.asarray(spacing, dtype=float)

    # Convert image shape from z,y,x to x,y,z.
    shape_xyz = np.asarray(
        image_shape[::-1],
        dtype=float
    )

    for candidate in filtered:

        index_xyz = np.asarray(
            candidate["index_xyz"],
            dtype=float
        )

        # Physical distance to each image boundary.
        distance_from_min = index_xyz * spacing_xyz

        distance_from_max = (
            (shape_xyz - 1) - index_xyz
        ) * spacing_xyz

        distance_to_edge = min(
            distance_from_min.min(),
            distance_from_max.min()
        )

        if distance_to_edge >= edge_margin_mm:
            candidate["edge_candidate"] = False
        else:
            candidate["edge_candidate"] = True

    # Keep non-edge candidates.
    filtered = [
        candidate
        for candidate in filtered
        if not candidate["edge_candidate"]
    ]

    # ---------------------------------------------------------
    # 3. Remove duplicate detections
    # ---------------------------------------------------------

    filtered.sort(
        key=lambda candidate: candidate["volume_mm3"],
        reverse=True
    )

    unique_candidates = []

    for candidate in filtered:

        point = np.asarray(
            candidate["point_xyz_mm"],
            dtype=float
        )

        is_duplicate = False

        for kept in unique_candidates:

            kept_point = np.asarray(
                kept["point_xyz_mm"],
                dtype=float
            )

            distance = np.linalg.norm(
                point - kept_point
            )

            if distance < duplicate_distance_mm:
                is_duplicate = True
                break

        if not is_duplicate:
            unique_candidates.append(candidate)

    return unique_candidates
