import os
import sys
import SimpleITK as sitk

file_name = sys.argv[1]

os.makedirs(".debug", exist_ok=True)

ct_image = sitk.ReadImage(file_name)
sitk.WriteImage(ct_image, ".debug/ct.nii.gz")