"""Local HTTP bridge from the React viewer to the shared detection pipeline."""

import asyncio
from itertools import product
from pathlib import Path
import re
import tempfile
from time import perf_counter
from uuid import uuid4

import numpy as np
import SimpleITK as sitk
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from run import run_pipeline
from src.io import load_nifti_image
from src.output import write_output

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / ".debug" / "viewer"
ASSETS = {"ct.nii.gz", "aorta.nii.gz", "branches.nii.gz", "prediction.json"}
analysis_lock = asyncio.Lock()
sitk.ProcessObject.SetGlobalDefaultNumberOfThreads(4)


def branch_overlay(image, daughters):
    """Rasterize physical centerlines and ostia on the CT grid for NiiVue."""
    labels = np.zeros(image.GetSize()[::-1], dtype=np.uint16)
    spacing = np.asarray(image.GetSpacing())
    extent = np.ceil(1.2 / spacing).astype(int)
    offsets = np.array([offset for offset in product(
        *(range(-int(value), int(value) + 1) for value in extent))
        if np.linalg.norm(np.asarray(offset) * spacing) <= 1.2])
    for label, daughter in enumerate(daughters, 1):
        points = np.asarray(daughter["centerline_points_mm"])
        for start, end in zip(points, points[1:]):
            steps = max(2, int(np.ceil(np.linalg.norm(end - start) / (spacing.min() / 2))) + 1)
            for point in np.linspace(start, end, steps):
                index = np.asarray(image.TransformPhysicalPointToIndex(point.tolist()))
                voxels = index + offsets
                voxels = voxels[np.all((voxels >= 0) & (voxels < image.GetSize()), axis=1)]
                labels[tuple(voxels[:, ::-1].T)] = label
    overlay = sitk.GetImageFromArray(labels)
    overlay.CopyInformation(image)
    return overlay


def analyze_case(image_path, mask_path, case_id):
    started = perf_counter()
    image, mask = load_nifti_image(image_path), load_nifti_image(mask_path)
    daughters = run_pipeline(image, mask)

    # Keep HU and physical coordinates while framing the viewer around the aorta.
    stats = sitk.LabelShapeStatisticsImageFilter()
    stats.Execute(sitk.Cast(mask > 0, sitk.sitkUInt8))
    bounds = stats.GetBoundingBox(1)
    margin = np.ceil(25.0 / np.asarray(image.GetSpacing())).astype(int)
    start = np.maximum(np.asarray(bounds[:3]) - margin, 0)
    end = np.minimum(np.asarray(bounds[:3]) + bounds[3:] + margin, image.GetSize())
    size = (end - start).tolist()
    image = sitk.RegionOfInterest(image, size, start.tolist())
    mask = sitk.RegionOfInterest(sitk.Cast(mask > 0, sitk.sitkUInt8), size, start.tolist())

    token = uuid4().hex
    folder = RESULTS / token
    folder.mkdir(parents=True, exist_ok=True)
    prediction = write_output(case_id, daughters, str(folder / "prediction.json"))
    for filename, volume in (("ct.nii.gz", image), ("aorta.nii.gz", mask),
                             ("branches.nii.gz", branch_overlay(image, daughters))):
        sitk.WriteImage(volume, str(folder / filename), True)

    return {
        **prediction,
        "daughters": [{**daughter, "centerline_points_mm": trace["centerline_points_mm"]}
                      for daughter, trace in zip(prediction["daughters"], daughters)],
        "runtime_seconds": round(perf_counter() - started, 2),
        "size": image.GetSize(),
        "spacing": image.GetSpacing(),
        "coordinate_system": "LPS",
        "assets": {name: f"/api/results/{token}/{filename}" for name, filename in
                   (("ct", "ct.nii.gz"), ("aorta", "aorta.nii.gz"),
                    ("branches", "branches.nii.gz"), ("prediction", "prediction.json"))},
    }


async def cases(request: Request):
    available = []
    for folder in sorted((ROOT / "data").glob("subject[0-9][0-9][0-9]")):
        number = int(folder.name.removeprefix("subject"))
        if (folder / f"orig{number}.nii").is_file() and (folder / f"mask{number}.nii").is_file():
            available.append(folder.name)
    return JSONResponse({"cases": available})


async def analyze(request: Request):
    try:
        async with request.form(max_files=2, max_fields=1) as form:
            async with analysis_lock:
                case_id = form.get("case_id")
                if case_id:
                    if not isinstance(case_id, str) or not re.fullmatch(r"subject\d{3}", case_id):
                        return JSONResponse({"error": "Choose a valid sample case."}, status_code=400)
                    number = int(case_id.removeprefix("subject"))
                    folder = ROOT / "data" / case_id
                    result = await run_in_threadpool(analyze_case, folder / f"orig{number}.nii",
                                                     folder / f"mask{number}.nii", case_id)
                else:
                    image, mask = form.get("image"), form.get("mask")
                    if not all(getattr(file, "filename", "").lower().endswith((".nii", ".nii.gz"))
                               for file in (image, mask)):
                        return JSONResponse({"error": "Upload both a CT and aorta mask as .nii or .nii.gz."},
                                            status_code=400)
                    with tempfile.TemporaryDirectory(prefix="branchseed-upload-") as directory:
                        paths = []
                        for name, upload in (("ct", image), ("mask", mask)):
                            path = Path(directory) / f"{name}.nii"
                            with path.open("wb") as file:
                                while chunk := await upload.read(1024 * 1024):
                                    file.write(chunk)
                            paths.append(path)
                        case_id = Path(image.filename).name.removesuffix(".gz").removesuffix(".nii")
                        result = await run_in_threadpool(analyze_case, *paths, case_id)
        return JSONResponse(result)
    except (ValueError, RuntimeError, OSError) as error:
        message = str(error).strip().splitlines()[-1]
        return JSONResponse({"error": message}, status_code=422)


async def asset(request: Request):
    token, filename = request.path_params["token"], request.path_params["filename"]
    if not re.fullmatch(r"[a-f0-9]{32}", token) or filename not in ASSETS:
        return JSONResponse({"error": "Asset not found."}, status_code=404)
    path = RESULTS / token / filename
    if not path.is_file():
        return JSONResponse({"error": "Asset not found."}, status_code=404)
    return FileResponse(path, media_type="application/json" if filename.endswith(".json")
                        else "application/octet-stream", filename=filename)


app = Starlette(routes=[Route("/api/cases", cases),
                        Route("/api/analyze", analyze, methods=["POST"]),
                        Route("/api/results/{token}/{filename}", asset)])
