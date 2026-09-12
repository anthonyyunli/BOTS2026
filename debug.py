"""Small NIfTI helpers for inspecting detection variables in NiiVue."""

import argparse
import json
from pathlib import Path

import numpy as np
import SimpleITK as sitk


def write_image(image, name="ct", output_dir=".debug"):
    """Write a SimpleITK image into the debug directory."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name.removesuffix('.nii.gz')}.nii.gz"
    sitk.WriteImage(image, str(path), True)
    print(f"Wrote {path}")
    return path


def view_candidates(
    ct_image,
    candidates,
    aorta_mask_image=None,
    output_dir=".debug",
    point_radius_mm=1.5,
    normal_length_mm=5.0,
):
    """Write CT and labelled candidate geometry for loading together in NiiVue."""
    if len(candidates) > np.iinfo(np.uint16).max:
        raise ValueError("Too many candidates for a uint16 label image.")

    overlay = np.zeros(tuple(reversed(ct_image.GetSize())), dtype=np.uint16)
    spacing = np.asarray(ct_image.GetSpacing(), dtype=float)
    shape_xyz = np.asarray(ct_image.GetSize())

    radius_voxels = np.ceil(point_radius_mm / spacing).astype(int)
    sphere_offsets = []
    for dz in range(-radius_voxels[2], radius_voxels[2] + 1):
        for dy in range(-radius_voxels[1], radius_voxels[1] + 1):
            for dx in range(-radius_voxels[0], radius_voxels[0] + 1):
                offset_xyz = np.array([dx, dy, dz])
                if np.linalg.norm(offset_xyz * spacing) <= point_radius_mm:
                    sphere_offsets.append(offset_xyz)

    def paint(center_xyz, label):
        center_xyz = np.rint(center_xyz).astype(int)
        for offset_xyz in sphere_offsets:
            index_xyz = center_xyz + offset_xyz
            if np.all(index_xyz >= 0) and np.all(index_xyz < shape_xyz):
                x, y, z = index_xyz
                overlay[z, y, x] = label

    step_mm = min(spacing) / 2.0
    line_distances = np.arange(0.0, normal_length_mm + step_mm, step_mm)

    for label, candidate in enumerate(candidates, start=1):
        point_xyz_mm = np.asarray(candidate["point_xyz_mm"], dtype=float)
        normal_xyz = np.asarray(candidate["normal_xyz"], dtype=float)
        normal_length = np.linalg.norm(normal_xyz)

        paint(candidate["index_xyz"], label)
        if normal_length == 0.0:
            continue

        normal_xyz /= normal_length
        for distance_mm in line_distances:
            point_on_line = point_xyz_mm + distance_mm * normal_xyz
            index_xyz = ct_image.TransformPhysicalPointToContinuousIndex(
                point_on_line.tolist()
            )
            paint(index_xyz, label)

    overlay_image = sitk.GetImageFromArray(overlay)
    overlay_image.CopyInformation(ct_image)

    ct_path = write_image(ct_image, "ct", output_dir)
    mask_path = None
    if aorta_mask_image is not None:
        mask_path = write_image(aorta_mask_image, "aorta_mask", output_dir)
    overlay_path = write_image(overlay_image, "candidate_overlay", output_dir)
    paths = [ct_path, mask_path, overlay_path]
    print("Open together in NiiVue:", *(path for path in paths if path), sep="\n  ")
    return overlay_image


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    write_parser = subparsers.add_parser("img")
    write_parser.add_argument("img")
    write_parser.add_argument("--name", default="ct")
    write_parser.add_argument("--output-dir", default=".debug")

    candidates_parser = subparsers.add_parser("cands")
    candidates_parser.add_argument("--img", required=True)
    candidates_parser.add_argument("--mask")
    candidates_parser.add_argument("--cands", required=True)
    candidates_parser.add_argument("--output-dir", default=".debug")

    args = parser.parse_args()
    ct_image = sitk.ReadImage(args.image)

    if args.command == "img":
        write_image(ct_image, args.name, args.output_dir)
        return

    with open(args.candidates, encoding="utf-8") as file:
        candidates = json.load(file)
    if isinstance(candidates, dict):
        candidates = candidates["candidates"]
    mask_image = sitk.ReadImage(args.mask) if args.mask else None
    view_candidates(
        ct_image,
        candidates,
        aorta_mask_image=mask_image,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
