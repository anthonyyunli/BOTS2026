"""Find possible daughter-vessel contacts on the aortic wall."""

import numpy as np
import SimpleITK as sitk


def detect_candidates(ct_image, aorta_mask_image):
    """Return blood-like connected components touching the exterior aortic wall."""
    mask = sitk.Cast(aorta_mask_image > 0, sitk.sitkUInt8)
    mask_array = sitk.GetArrayFromImage(mask).astype(bool)
    if not np.any(mask_array):
        raise ValueError("Aorta mask is empty.")

    ct_array = sitk.GetArrayFromImage(ct_image)
    erosion_radius = [
        max(1, round(2.0 / spacing)) for spacing in mask.GetSpacing()
    ]
    inner_mask = sitk.BinaryErode(mask, erosion_radius, sitk.sitkBall)
    inner_array = sitk.GetArrayFromImage(inner_mask).astype(bool)
    if not np.any(inner_array):
        inner_array = mask_array

    p10, p90 = np.percentile(ct_array[inner_array], [10, 90])
    intensity_margin = max(float(p90 - p10), 1e-6)
    lower_intensity = float(p10)
    upper_intensity = float(p90 + intensity_margin)

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
        & (ct_array <= upper_intensity)
    )
    candidate_image = sitk.GetImageFromArray(candidate_array.astype(np.uint8))
    candidate_image.CopyInformation(aorta_mask_image)
    labels_image = sitk.ConnectedComponent(candidate_image, True)
    labels_array = sitk.GetArrayFromImage(labels_image)

    voxel_volume = float(np.prod(ct_image.GetSpacing()))
    dilated_mask = sitk.BinaryDilate(
        mask,
        [1] * mask.GetDimension(),
        sitk.sitkBox,
    )
    contact_array = sitk.GetArrayFromImage(dilated_mask).astype(bool) & ~mask_array
    candidates = []

    positions = np.argwhere(labels_array > 0)
    if len(positions) == 0:
        return candidates

    position_labels = labels_array[tuple(positions.T)]
    order = np.argsort(position_labels, kind="stable")
    positions = positions[order]
    position_labels = position_labels[order]
    split_at = np.flatnonzero(np.diff(position_labels)) + 1

    normal_image = sitk.GradientRecursiveGaussian(
        distance_image,
        sigma=0.7,
        normalizeAcrossScale=False,
        useImageDirection=True,
    )
    normal_array = sitk.GetArrayFromImage(normal_image)

    for component in np.split(positions, split_at):
        component_contact = contact_array[tuple(component.T)]
        if not np.any(component_contact):
            continue

        contact = component[component_contact]
        contact_center = contact.mean(axis=0)
        z, y, x = contact[np.argmin(np.sum((contact - contact_center) ** 2, axis=1))]
        index_xyz = [int(x), int(y), int(z)]
        point_xyz_mm = ct_image.TransformIndexToPhysicalPoint(index_xyz)
        normal_xyz = normal_array[z, y, x].astype(float)
        normal_length = np.linalg.norm(normal_xyz)
        if normal_length > 0.0:
            normal_xyz /= normal_length

        candidates.append(
            {
                "index_xyz": index_xyz,
                "point_xyz_mm": [float(value) for value in point_xyz_mm],
                "normal_xyz": [float(value) for value in normal_xyz],
                "volume_mm3": float(len(component) * voxel_volume),
            }
        )

    return sorted(candidates, key=lambda candidate: candidate["point_xyz_mm"])
