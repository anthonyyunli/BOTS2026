from src.preprocessing import preprocess_case
from src.detection import detect_candidates


data = preprocess_case(
    "data/subject002/orig2.nii",
    "data/subject002/mask2.nii"
)

print("Preprocessing complete.")
print("Processed CT shape:", data["ct"].shape)
print("Processed mask shape:", data["mask"].shape)


candidates = detect_candidates(
    data["ct_image"],
    data["aorta_mask_image"]
)

print("\nNumber of candidates:", len(candidates))

for i, candidate in enumerate(candidates):
    print(f"\nCandidate {i + 1}:")
    print(candidate)
