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

  return {
    "ct_image": ct_image,
    "ct": ct_array,
    "mask_image": mask_image,
    "mask": mask_array,
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
