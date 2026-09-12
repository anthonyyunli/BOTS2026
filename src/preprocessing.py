"""Crop and normalize CT data around the supplied aorta mask."""

import numpy as np
import SimpleITK as sitk


def get_bounding_box(mask):
    """Return inclusive minimum and maximum coordinates in NumPy z-y-x order."""
    coords = np.argwhere(mask > 0)
    if len(coords) == 0:
        raise ValueError("Aorta mask is empty.")
    return coords.min(axis=0), coords.max(axis=0)


def crop_around_aorta(ct, mask, spacing, margin_mm=15):
    """Crop CT and mask to the aorta bounding box plus a margin in millimetres."""
    if ct.shape != mask.shape:
        raise ValueError("CT and aorta mask arrays must have the same shape.")
    if margin_mm < 0:
        raise ValueError("margin_mm must be non-negative.")

    minimum, maximum = get_bounding_box(mask)
    spacing_zyx = np.asarray(spacing, dtype=float)[::-1]
    if spacing_zyx.shape != (3,) or np.any(spacing_zyx <= 0):
        raise ValueError("spacing must contain three positive values.")

    margin_voxels = np.ceil(margin_mm / spacing_zyx).astype(int)
    start = np.maximum(minimum - margin_voxels, 0)
    end = np.minimum(maximum + margin_voxels + 1, ct.shape)
    crop = tuple(slice(start[axis], end[axis]) for axis in range(3))

    crop_info = {
        "start_zyx": start,
        "end_zyx": end,
        "margin_mm": margin_mm,
    }
    return ct[crop], mask[crop], crop_info


def normalize_ct(ct):
    """Clip CT to robust percentiles and scale it to [0, 1]."""
    lower, upper = np.percentile(ct, [1, 99.5])
    if upper <= lower:
        return np.zeros(ct.shape, dtype=np.float32)
    return ((np.clip(ct, lower, upper) - lower) / (upper - lower)).astype(
        np.float32
    )


def get_cropped_origin(image, start_zyx):
    """Return the physical point at a crop start given in NumPy z-y-x order."""
    start_xyz = tuple(int(value) for value in reversed(start_zyx))
    return image.TransformIndexToPhysicalPoint(start_xyz)


def preprocess_case(ct_image, mask_image, margin_mm=15):
    """Run preprocessing while preserving the existing result dictionary API."""
    if ct_image.GetDimension() != 3 or mask_image.GetDimension() != 3:
        raise ValueError("CT and aorta mask must be 3D.")
    if not ct_image.IsSameImageGeometryAs(mask_image):
        raise ValueError("CT and aorta mask must use the same image geometry.")

    ct = sitk.GetArrayFromImage(ct_image)
    mask = sitk.GetArrayFromImage(mask_image) > 0
    ct_crop, mask_crop, crop_info = crop_around_aorta(
        ct,
        mask,
        ct_image.GetSpacing(),
        margin_mm,
    )
    ct_processed = normalize_ct(ct_crop)
    cropped_origin = get_cropped_origin(ct_image, crop_info["start_zyx"])

    cropped_ct_image = sitk.GetImageFromArray(ct_processed)
    cropped_ct_image.SetSpacing(ct_image.GetSpacing())
    cropped_ct_image.SetOrigin(cropped_origin)
    cropped_ct_image.SetDirection(ct_image.GetDirection())

    cropped_mask_image = sitk.GetImageFromArray(mask_crop.astype(np.uint8))
    cropped_mask_image.SetSpacing(mask_image.GetSpacing())
    cropped_mask_image.SetOrigin(cropped_origin)
    cropped_mask_image.SetDirection(mask_image.GetDirection())

    return {"ct_image": cropped_ct_image, "aorta_mask_image": cropped_mask_image}


def inspect_case(ct_image, ct, mask):
    """Print CT statistics and basic aorta-mask information."""
    print("CT shape:", ct.shape)
    print("CT spacing:", ct_image.GetSpacing())
    print("CT min:", np.min(ct))
    print("CT max:", np.max(ct))
    print("CT mean:", np.mean(ct))

    print("\nCT percentiles:")
    for percentile in [1, 5, 25, 50, 75, 95, 99, 99.5, 99.9]:
        print(f"{percentile}%: {np.percentile(ct, percentile):.2f}")

    print("\nMask unique values:", np.unique(mask))
    print("Aorta voxels:", np.sum(mask > 0))
    print("\nMask bounding box:")
    print(get_bounding_box(mask))
