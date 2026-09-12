import SimpleITK as sitk

from src.preprocessing import preprocess_case
from src.detection import detect_candidates

CT_PATH = "data/subject002/orig2.nii"
MASK_PATH = "data/subject002/mask2.nii"

ct_image = sitk.ReadImage(str(CT_PATH))
mask_image = sitk.ReadImage(str(MASK_PATH))

data = preprocess_case(ct_image, mask_image)

print("Preprocessing complete.")
print("Processed CT size:", data["ct_image"].GetSize())
print("Processed mask size:", data["aorta_mask_image"].GetSize())


candidates = detect_candidates(
    data["ct_image"],
    data["aorta_mask_image"]
)

print("\nNumber of candidates:", len(candidates))

for i, candidate in enumerate(candidates):
    print(f"\nCandidate {i + 1}:")
    print(candidate)
