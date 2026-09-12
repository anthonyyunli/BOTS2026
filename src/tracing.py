"""Trace proximal daughter centerlines through blood-like lumen outside the aorta."""

from itertools import product

import numpy as np
import SimpleITK as sitk
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, minimum_spanning_tree
from skimage.graph import MCP_Geometric
from skimage.morphology import skeletonize

from src.geometry import calculate_direction, estimate_radius, find_seed


def _trace_component(component, start, spacing, normal, max_length_mm):
    """Connect the contact voxel to a skeleton, then walk its proximal trunk."""
    radius = ndimage.distance_transform_edt(np.pad(component, 1), sampling=spacing)
    radius = radius[1:-1, 1:-1, 1:-1]
    skeleton = skeletonize(component, method="lee")
    if not skeleton.any():
        # Lee thinning can erase symmetric, even-width tubes. In that case use
        # distance maxima in cross-sections perpendicular to the initial normal.
        axis = int(np.argmax(np.abs(normal)))
        sections = np.moveaxis(component, axis, 0)
        radii = np.moveaxis(radius, axis, 0)
        centers = np.moveaxis(skeleton, axis, 0)
        for plane, (section, section_radius) in enumerate(zip(sections, radii)):
            labels, count = ndimage.label(section)
            for label in range(1, count + 1):
                region = labels == label
                peaks = np.argwhere(region & (section_radius == section_radius[region].max()))
                center = peaks[np.argmin(np.sum((peaks - peaks.mean(axis=0))**2, axis=1))]
                centers[plane, center[0], center[1]] = True
    points = np.argwhere(skeleton)
    if len(points) < 2:
        return []

    # The contact need not survive thinning. Connect it through lumen only.
    costs = np.where(component, 1.0 / (radius + min(spacing)), np.inf)
    search = MCP_Geometric(costs, sampling=tuple(spacing))
    costs, _ = search.find_costs([tuple(start)], points.tolist(), find_all_ends=False)
    root = int(np.argmin(costs[tuple(points.T)]))
    if not np.isfinite(costs[tuple(points[root])]):
        return []
    path = [np.asarray(point) for point in search.traceback(tuple(points[root]))]

    # Build a physical-distance graph. A spanning tree removes tiny voxel cycles.
    node_ids = np.full(component.shape, -1, dtype=np.int32)
    node_ids[tuple(points.T)] = np.arange(len(points))
    rows, columns, weights = [], [], []
    for offset in product((-1, 0, 1), repeat=3):
        if offset == (0, 0, 0):
            continue
        neighbours = points + offset
        valid = np.all((neighbours >= 0) & (neighbours < component.shape), axis=1)
        source = np.flatnonzero(valid)
        target = node_ids[tuple(neighbours[valid].T)]
        connected = target >= 0
        rows.extend(source[connected])
        columns.extend(target[connected])
        weights.extend([float(np.linalg.norm(np.asarray(offset) * spacing))]
                       * int(connected.sum()))
    graph = coo_matrix((weights, (rows, columns)), shape=(len(points), len(points)))
    tree = minimum_spanning_tree(graph.tocsr())
    distances, parents = dijkstra(tree, directed=False, indices=root,
                                  return_predecessors=True)
    children = [[] for _ in points]
    for node, parent in enumerate(parents):
        if parent >= 0:
            children[parent].append(node)

    # Ignore skeleton spurs shorter than 2 mm when deciding whether a trunk splits.
    reach = np.zeros(len(points))
    for node in np.argsort(distances)[::-1]:
        for child in children[node]:
            reach[node] = max(reach[node], distances[child] - distances[node] + reach[child])

    length = sum(np.linalg.norm((b - a) * spacing) for a, b in zip(path, path[1:]))
    node = root
    while length < max_length_mm:
        options = children[node]
        if node == root:
            options = [child for child in options
                       if np.dot((points[child] - points[node]) * spacing, normal) > 0]
        substantial = [child for child in options
                       if distances[child] - distances[node] + reach[child] >= 2.0]
        if len(substantial) > 1 or not options:
            break
        child = max(options, key=lambda item: distances[item] - distances[node] + reach[item])
        length += np.linalg.norm((points[child] - points[node]) * spacing)
        path.append(points[child])
        node = child
    return path


def trace_candidates(ct_image, aorta_mask_image, candidates, max_length_mm=10.0):
    """Return daughter geometry and centerlines for contacts traceable at least 5 mm.

    All output points use SimpleITK physical coordinates. The normal only chooses
    the initial outward direction; subsequent points follow the segmented lumen.
    """
    if not 5.0 <= max_length_mm <= 10.0:
        raise ValueError("max_length_mm must be between 5 and 10 mm.")
    if ct_image.GetDimension() != 3 or not ct_image.IsSameImageGeometryAs(aorta_mask_image):
        raise ValueError("CT and aorta mask must share a 3D image geometry.")
    if not candidates:
        return []

    ct = sitk.GetArrayFromImage(ct_image)
    mask_image = sitk.Cast(aorta_mask_image > 0, sitk.sitkUInt8)
    mask = sitk.GetArrayFromImage(mask_image).astype(bool)
    if not mask.any():
        return []
    spacing = np.asarray(ct_image.GetSpacing()[::-1])
    inner = sitk.BinaryErode(mask_image, [max(1, round(2.0 / s))
                                        for s in ct_image.GetSpacing()], sitk.sitkBall)
    inner = sitk.GetArrayFromImage(inner).astype(bool)
    low, high = np.percentile(ct[inner if inner.any() else mask], [10, 90])
    lumen = (ct >= low) & (ct <= high + max(float(high - low), 1e-6)) & ~mask
    contact = ndimage.binary_dilation(mask, structure=np.ones((3, 3, 3))) & ~mask
    wall_distance = ndimage.distance_transform_edt(~mask, sampling=spacing)
    z_limits = np.flatnonzero(mask.any(axis=(1, 2)))[[0, -1]]
    direction = np.asarray(ct_image.GetDirection()).reshape(3, 3)
    daughters = []

    for candidate in candidates:
        # Physical points remain valid even if the caller changed the crop.
        start = np.asarray(ct_image.TransformPhysicalPointToIndex(candidate["point_xyz_mm"])[::-1])
        if np.any(start < 0) or np.any(start >= ct.shape):
            continue
        if not lumen[tuple(start)] or not contact[tuple(start)]:
            continue
        if min(start[0] - z_limits[0], z_limits[1] - start[0]) * spacing[0] < 2.0:
            continue  # Exclude superior/inferior mask caps, including internal caps.
        normal = np.asarray(candidate["normal_xyz"], dtype=float)
        if not np.isfinite(normal).all() or np.linalg.norm(normal) == 0:
            continue
        normal = (direction.T @ (normal / np.linalg.norm(normal)))[::-1]

        # Bound work per contact and keep enough background for the radius estimate.
        margin = np.ceil((max_length_mm + 5.0) / spacing).astype(int)
        lower = np.maximum(start - margin, 0)
        upper = np.minimum(start + margin + 1, ct.shape)
        region = tuple(slice(a, b) for a, b in zip(lower, upper))
        labels, _ = ndimage.label(lumen[region], structure=np.ones((3, 3, 3)))
        local_start = start - lower
        component = labels == labels[tuple(local_start)]
        path = _trace_component(component, local_start, spacing, normal, max_length_mm)
        if len(path) < 2:
            continue
        points_mm = [ct_image.TransformIndexToPhysicalPoint(
            [int(value) for value in (point + lower)[::-1]]) for point in path]
        lengths = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(points_mm, axis=0), axis=1))]
        if lengths[-1] < 5.0:
            continue
        if lengths[-1] > max_length_mm:
            endpoint = find_seed(points_mm[0], points_mm, distance_mm=max_length_mm)
            points_mm = points_mm[:int(np.searchsorted(lengths, max_length_mm))] + [endpoint]

        ostium = list(points_mm[0])
        seed = find_seed(ostium, points_mm)
        seed_index = np.asarray(ct_image.TransformPhysicalPointToContinuousIndex(seed)[::-1])
        # Avoid accepting paths that only travel sideways along the aortic wall.
        if ndimage.map_coordinates(wall_distance, seed_index[:, None], order=1)[0] < 2.0:
            continue
        if np.dot((seed_index - start) * spacing, normal) <= 0:
            continue
        local_seed_xyz = (seed_index - lower)[::-1]
        radius = estimate_radius(local_seed_xyz, component, ct_image.GetSpacing())
        if radius <= 0:
            continue
        if any(np.linalg.norm(np.asarray(d["ostium_xyz_mm"]) - ostium) < 1.0
               and np.linalg.norm(np.asarray(d["seed_xyz_mm"]) - seed) < 2.0 for d in daughters):
            continue
        daughters.append({
            "ostium_xyz_mm": ostium,
            "seed_xyz_mm": seed,
            "radius_mm": radius,
            "direction_xyz": calculate_direction(ostium, seed),
            "centerline_points_mm": [list(point) for point in points_mm],
        })

    return sorted(daughters, key=lambda daughter: daughter["ostium_xyz_mm"])
