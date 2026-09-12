# Candidate Detection Design

## Scope

Implement candidate discovery in `src/detection.py`. The detector proposes possible direct daughter origins. It does not crop or normalize images, enhance vessels, trace paths, reject endpoint caps, merge duplicates, calculate final daughter geometry, or format output.

## Module boundary

`preprocessing.py` supplies a cropped CT image and matching cropped aorta mask while preserving their SimpleITK geometry. It may normalize or enhance the CT before detection.

`detection.py` consumes those images and returns wall-contact candidates.

`tracing.py` validates that each candidate continues through a daughter vessel for at least 5 mm. `filtering.py` rejects false positives, endpoint caps, and duplicates. `geometry.py` calculates the refined ostium, seed, direction, and radius.

## Public interface

```python
detect_candidates(ct_image, aorta_mask_image) -> list[dict]
```

Each result contains only data needed by downstream modules:

```python
{
    "index_xyz": [x, y, z],
    "point_xyz_mm": [x_mm, y_mm, z_mm],
    "volume_mm3": component_volume,
}
```

`index_xyz` follows SimpleITK index order. `point_xyz_mm` comes from `TransformIndexToPhysicalPoint`, never manual spacing arithmetic. Results use stable physical-coordinate ordering so array traversal cannot change candidate order.

## Detection method

1. Cast the aorta mask to binary.
2. Reject an empty mask with `ValueError`.
3. Use the aorta's 25th intensity percentile as the lower vessel threshold. This avoids a fixed CTA enhancement value and remains valid if preprocessing only crops the source CT. Do not impose an upper threshold; downstream tracing can reject bright calcification that does not persist as a vessel.
4. Calculate a signed Maurer distance map with image spacing enabled.
5. Select blood-like voxels outside the aorta and within 3 mm of its wall.
6. Group those voxels with fully connected 3D connected components.
7. For each component, select its voxel nearest the aortic wall and nearest the component's wall-contact centre. This voxel is a candidate, not a final ostium.
8. Return candidates in physical-coordinate order.

The detector favors recall. Later modules own anatomical and path-based rejection. No vesselness stage belongs in this first implementation because preprocessing owns enhancement and the extra scale parameters are not yet supported by development annotations.

## Error handling

The detector raises `ValueError` for an empty mask. Preprocessing owns grid and geometry validation, so detection does not duplicate those checks. It does not catch SimpleITK type or dimensionality errors.

## Testing

Use small synthetic 3D SimpleITK images because checked-in `.nii` files are empty placeholders. Tests cover:

- one lateral wall-contact candidate;
- two separate contacts remain two candidates;
- distant bright structures are ignored;
- returned indices use `(x, y, z)` order;
- returned physical points respect spacing, origin, and direction;
- an empty mask fails clearly.

Tests use Python's standard `unittest` library. No dependency is added.
