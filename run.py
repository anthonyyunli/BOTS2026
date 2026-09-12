"""Run daughter detection, tracing and JSON export for one CT case."""

import argparse
from pathlib import Path
from time import perf_counter

import SimpleITK as sitk

from src.detection import detect_candidates
from src.filtering import filter_candidates
from src.io import load_nifti_image
from src.output import write_output
from src.preprocessing import preprocess_case
from src.tracing import trace_candidates


def run_pipeline(ct_image, aorta_mask_image):
    """Return traced daughter geometry from two SimpleITK images."""
    data = preprocess_case(ct_image, aorta_mask_image)
    ct_image, aorta_mask_image = data["ct_image"], data["aorta_mask_image"]
    candidates = detect_candidates(ct_image, aorta_mask_image)
    candidates = filter_candidates(
        candidates, ct_image.GetSize()[::-1], ct_image.GetSpacing(),
        duplicate_distance_mm=0.0,  # Nearby origins can be separate daughters.
    )
    return trace_candidates(ct_image, aorta_mask_image, candidates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--aorta-mask", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--case-id", help="Defaults to the image's parent directory name.")
    args = parser.parse_args()
    sitk.ProcessObject.SetGlobalDefaultNumberOfThreads(4)
    started = perf_counter()
    try:
        daughters = run_pipeline(load_nifti_image(args.image), load_nifti_image(args.aorta_mask))
        case_id = args.case_id or Path(args.image).resolve().parent.name
        write_output(case_id, daughters, args.output)
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"Pipeline failed: {error}\n")
    print(f"{case_id}: {len(daughters)} daughters, {perf_counter() - started:.2f}s; {args.output}")

if __name__ == "__main__":
    main()
