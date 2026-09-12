"""Find possible daughter-vessel contacts on the aortic wall."""

import numpy as np
import SimpleITK as sitk


def detect_candidates(ct_image, aorta_mask_image):
    """Return bright connected components touching the exterior aortic wall."""
    mask = sitk.Cast(aorta_mask_image > 0, sitk.sitkUInt8)
    mask_array = sitk.GetArrayFromImage(mask).astype(bool)
    if not np.any(mask_array):
        raise ValueError("Aorta mask is empty.")

    ct_array = sitk.GetArrayFromImage(ct_image)
    lower_intensity = np.percentile(ct_array[mask_array], 25)
    distance_image = sitk.SignedMaurerDistanceMap(
        mask,
        insideIsPositive=False,
        squaredDistance=False,
        useImageSpacing=True,
    )
    distance_array = sitk.GetArrayFromImage(distance_image)

    candidate_array = (
        (~mask_array)
        & (distance_array > 0.0)
        & (distance_array <= 3.0)
        & (ct_array >= lower_intensity)
    )
    candidate_image = sitk.GetImageFromArray(candidate_array.astype(np.uint8))
    candidate_image.CopyInformation(aorta_mask_image)
    labels_image = sitk.ConnectedComponent(candidate_image, True)
    labels_array = sitk.GetArrayFromImage(labels_image)

    voxel_volume = float(np.prod(ct_image.GetSpacing()))
    contact_distance = float(np.linalg.norm(ct_image.GetSpacing()))
    candidates = []

    positions = np.argwhere(labels_array > 0)
    if len(positions) == 0:
        return candidates

    position_labels = labels_array[tuple(positions.T)]
    order = np.argsort(position_labels, kind="stable")
    positions = positions[order]
    position_labels = position_labels[order]
    split_at = np.flatnonzero(np.diff(position_labels)) + 1

    for component in np.split(positions, split_at):
        component_distances = distance_array[tuple(component.T)]
        closest_distance = float(component_distances.min())
        if closest_distance > contact_distance:
            continue

        contact = component[np.isclose(component_distances, closest_distance)]
        contact_center = contact.mean(axis=0)
        z, y, x = contact[np.argmin(np.sum((contact - contact_center) ** 2, axis=1))]
        index_xyz = [int(x), int(y), int(z)]
        point_xyz_mm = ct_image.TransformIndexToPhysicalPoint(index_xyz)

        candidates.append(
            {
                "index_xyz": index_xyz,
                "point_xyz_mm": [float(value) for value in point_xyz_mm],
                "volume_mm3": float(len(component) * voxel_volume),
            }
        )

    return sorted(candidates, key=lambda candidate: candidate["point_xyz_mm"])
