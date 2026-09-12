'''
Prepare the CT: 
Crop around aorta -> Normalize intensities -> Remove irrelevant regions -> Enhance vessels
'''

import SimpleITK as sitk
import numpy as np


def load_nifti(path):
  """
  Load a nifti file using SimpleITK.

  Returns:
  - image: SimpleITK image
  - array: NumPy array
  """

  image = sitk.ReadImage(str(path))
  array = sitk.GetArrayFromImage(image)

  return image, array


def load_case(ct_path, mask_path):
  """
  Load the CT volume and aorta mask for one case.
  """

  ct_image, ct_array = load_nifti(ct_path)
  mask_image, mask_array = load_nifti(mask_path)

  # Making sure CT and mask use the same spatial grid.
  if ct_image.GetSize() != mask_image.GetSize():
    raise ValueError("CT and mask have different dimensions.")

  if ct_image.GetSpacing() != mask_image.GetSpacing():
    raise ValueError("CT and mask have different voxel spacing.")

  if ct_image.GetOrigin() != mask_image.GetOrigin():
    raise ValueError("CT and mask have different physical origins.")

  if ct_image.GetDirection() != mask_image.GetDirection():
    raise ValueError("CT and mask have different physical directions.")

  # Make sure the mask is binary
  mask_array = mask_array > 0

  return {
    "ct_image": ct_image,
    "ct": ct_array,
    "mask_image": mask_image,
    "mask": mask_array,
  }


def get_bounding_box(mask):
    """
    Return the bounding box of the non-zero mask.

    NumPy array order:
        z, y, x

    Returns:
        min_coords
        max_coords
    """

    coords = np.argwhere(mask > 0)

    if len(coords) == 0:
        raise ValueError("Aorta mask is empty.")

    min_coords = coords.min(axis=0)
    max_coords = coords.max(axis=0)

    return min_coords, max_coords


def crop_around_aorta(ct, mask, spacing, margin_mm=15):
    """
    Crop CT and aorta mask around the aorta.

    The margin is specified in physical millimetres rather than
    voxels because the challenge uses physical distances.

    Args:
        ct: CT NumPy array in (z, y, x)
        mask: binary mask in (z, y, x)
        spacing: SimpleITK spacing in (x, y, z)
        margin_mm: physical margin around the aorta

    Returns:
        cropped_ct
        cropped_mask
        crop_info
    """

    min_coords, max_coords = get_bounding_box(mask)

    # NumPy dimensions are z, y, x.
    # SimpleITK spacing is x, y, z.
    spacing_xyz = np.asarray(spacing)
    spacing_zyx = spacing_xyz[::-1]

    # Convert physical margin into voxels.
    margin_voxels = np.ceil(
        margin_mm / spacing_zyx
    ).astype(int)

    # Expand bounding box.
    start = np.maximum(
        min_coords - margin_voxels,
        0
    )

    end = np.minimum(
        max_coords + margin_voxels + 1,
        np.array(ct.shape)
    )

    z0, y0, x0 = start
    z1, y1, x1 = end

    cropped_ct = ct[z0:z1, y0:y1, x0:x1]
    cropped_mask = mask[z0:z1, y0:y1, x0:x1]

    crop_info = {
        "start_zyx": start,
        "end_zyx": end,
        "margin_mm": margin_mm,
    }

    return cropped_ct, cropped_mask, crop_info


def normalize_ct(ct):
    """
    Normalize CT intensities using robust percentile clipping.

    The extreme CT values are clipped, then the result is scaled
    approximately to [0, 1].
    """

    lower = np.percentile(ct, 1)
    upper = np.percentile(ct, 99.5)

    clipped = np.clip(ct, lower, upper)

    normalized = (
        clipped - lower
    ) / (upper - lower)

    return normalized.astype(np.float32)


def get_cropped_origin(image, start_zyx):
    """
    Calculate the physical origin of a cropped image.

    start_zyx is in NumPy order:
        z, y, x

    SimpleITK expects:
        x, y, z
    """

    start_z, start_y, start_x = start_zyx

    start_xyz = (
        int(start_x),
        int(start_y),
        int(start_z)
    )

    return image.TransformIndexToPhysicalPoint(start_xyz)


def preprocess_case(ct_path, mask_path, margin_mm=15):
    """
    Complete preprocessing pipeline.

    Returns:
        A dictionary containing:
        - ct_image: cropped SimpleITK CT image
        - aorta_mask_image: cropped SimpleITK aorta mask image
        - ct: cropped, normalized NumPy CT array
        - mask: cropped NumPy aorta mask
        - spacing: voxel spacing in mm
        - origin: physical origin of cropped image
        - direction: image orientation
        - crop_info: information about the crop
    """

    case = load_case(ct_path, mask_path)

    ct_image = case["ct_image"]
    ct = case["ct"]
    mask_image = case["mask_image"]
    mask = case["mask"]

    # Crop around the aorta
    ct_crop, mask_crop, crop_info = crop_around_aorta(
        ct,
        mask,
        ct_image.GetSpacing(),
        margin_mm=margin_mm,
    )

    # Normalize CT for downstream processing
    ct_processed = normalize_ct(ct_crop)

    # Create SimpleITK images from the cropped arrays
    #
    # Important:
    # GetImageFromArray expects NumPy order (z, y, x).
    cropped_ct_image = sitk.GetImageFromArray(
        ct_processed
    )

    cropped_mask_image = sitk.GetImageFromArray(
        mask_crop.astype(np.uint8)
    )

    # Calculate the physical origin of the cropped image.
    cropped_origin = get_cropped_origin(
        ct_image,
        crop_info["start_zyx"]
    )

    # Preserve physical coordinate information.
    cropped_ct_image.SetSpacing(ct_image.GetSpacing())
    cropped_ct_image.SetOrigin(cropped_origin)
    cropped_ct_image.SetDirection(ct_image.GetDirection())

    cropped_mask_image.SetSpacing(mask_image.GetSpacing())
    cropped_mask_image.SetOrigin(cropped_origin)
    cropped_mask_image.SetDirection(mask_image.GetDirection())

    return {
        # These are what detection.py will use
        "ct_image": cropped_ct_image,
        "aorta_mask_image": cropped_mask_image,

        # These are useful for other algorithms
        "ct": ct_processed,
        "mask": mask_crop,

        # Physical information
        "spacing": ct_image.GetSpacing(),
        "origin": cropped_origin,
        "direction": ct_image.GetDirection(),

        # Useful for converting cropped coordinates later
        "crop_info": crop_info,
    }


def inspect_case(ct_image, ct, mask):
  print("CT shape:", ct.shape)
  print("CT spacing:", ct_image.GetSpacing())

  print("CT min:", np.min(ct))
  print("CT max:", np.max(ct))
  print("CT mean:", np.mean(ct))

  print("\nCT percentiles:")
  
  for p in [1, 5, 25, 50, 75, 95, 99, 99.5, 99.9]:
    print(f"{p}%: {np.percentile(ct, p):.2f}")

  print("\nMask unique values:", np.unique(mask))
  print("Aorta voxels:", np.sum(mask > 0))

  print("\nMask bounding box:")
  print(get_bounding_box(mask))


def get_bounding_box(mask):
    """
    Return the bounding box of the non-zero mask.

    NumPy array order is:
        z, y, x
    """

    coords = np.argwhere(mask > 0)

    if len(coords) == 0:
        raise ValueError("Aorta mask is empty.")

    min_coords = coords.min(axis=0)
    max_coords = coords.max(axis=0)

    return min_coords, max_coords


def get_cropped_origin(image, start_zyx):
    """
    Calculate the physical origin of a cropped image.

    start_zyx is in NumPy array order:
        z, y, x

    SimpleITK expects:
        x, y, z
    """

    start_z, start_y, start_x = start_zyx

    start_xyz = (
        int(start_x),
        int(start_y),
        int(start_z)
    )

    return image.TransformIndexToPhysicalPoint(start_xyz)
