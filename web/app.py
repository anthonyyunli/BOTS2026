# web/app.py

import sys
import json
from pathlib import Path
import tempfile

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

import SimpleITK as sitk
import streamlit as st
import numpy as np
import plotly.graph_objects as go

from src.preprocessing import preprocess_case
from src.detection import detect_candidates
from src.filtering import filter_candidates
from src.io import load_nifti_image
from src.output import write_output
from run import run_pipeline

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="BranchSeed",
    page_icon="🫀",
    layout="wide",
)


# ============================================================
# TITLE / INTRO
# ============================================================

st.title("🫀 BranchSeed")

st.markdown(
    """
    ### Automated Aortic Branch Detection

    Upload a CTA volume and its corresponding parent-aorta mask.
    BranchSeed identifies candidate daughter vessels and reports
    their origins, directions, and vessel geometry.
    """
)


# ============================================================
# SIDEBAR — INPUT
# ============================================================

st.sidebar.header("Input")

ct_file = st.sidebar.file_uploader(
    "CT Volume",
    type=["nii", "nii.gz"],
)

mask_file = st.sidebar.file_uploader(
    "Aorta Mask",
    type=["nii", "nii.gz"],
)

run_button = st.sidebar.button(
    "Run Analysis",
    type="primary",
    use_container_width=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def save_uploaded_file(uploaded_file):
    """
    Save a Streamlit uploaded file temporarily so that
    SimpleITK and the pipeline can read it.
    """

    suffix = Path(uploaded_file.name).suffix

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
    ) as temp_file:

        temp_file.write(uploaded_file.getbuffer())

        return temp_file.name


def load_image(path):
    """Load a NIfTI image using SimpleITK."""

    return sitk.ReadImage(path)


def create_aorta_visualization(mask_image, candidates=None, daughters=None):
    """
    Visualize the aorta and candidate points in the same physical
    coordinate system (mm).
    """

    mask = sitk.GetArrayFromImage(mask_image)
    spacing = mask_image.GetSpacing()

    # Get indices of aorta voxels
    z, y, x = np.where(mask > 0)

    # Convert every voxel index to physical coordinates.
    # SimpleITK uses (x, y, z), while NumPy gives (z, y, x).
    points = np.column_stack((x, y, z))

    physical_points = np.array([
        mask_image.TransformIndexToPhysicalPoint(
            (int(px), int(py), int(pz))
        )
        for px, py, pz in points
    ])

    fig = go.Figure()

    # Aorta
    fig.add_trace(
        go.Scatter3d(
            x=physical_points[:, 0],
            y=physical_points[:, 1],
            z=physical_points[:, 2],
            mode="markers",
            marker=dict(
                size=2,
                opacity=0.25,
            ),
            name="Aorta",
        )
    )

    # Candidate points
    if candidates:
        candidate_x = [
            candidate["point_xyz_mm"][0]
            for candidate in candidates
        ]

        candidate_y = [
            candidate["point_xyz_mm"][1]
            for candidate in candidates
        ]

        candidate_z = [
            candidate["point_xyz_mm"][2]
            for candidate in candidates
        ]

        labels = [
            f"branch-{i + 1}"
            for i in range(len(candidates))
        ]

        fig.add_trace(
            go.Scatter3d(
                x=candidate_x,
                y=candidate_y,
                z=candidate_z,
                mode="markers+text",
                marker=dict(
                    size=7,
                ),
                text=labels,
                textposition="top center",
                name="Detected candidates",
            )
        )

    for i, daughter in enumerate(daughters or [], start=1):
        path = np.asarray(daughter["centerline_points_mm"])
        seed = np.asarray(daughter["seed_xyz_mm"])
        normal = np.asarray(daughter["direction_xyz"])
        fig.add_trace(go.Scatter3d(
            x=path[:, 0], y=path[:, 1], z=path[:, 2],
            mode="lines+markers", line=dict(width=6), marker=dict(size=3),
            name=f"branch_{i:03d}",
        ))
        fig.add_trace(go.Cone(
            x=[seed[0]], y=[seed[1]], z=[seed[2]],
            u=[normal[0]], v=[normal[1]], w=[normal[2]],
            sizemode="absolute", sizeref=2, showscale=False,
            name=f"branch_{i:03d} direction",
        ))

    fig.update_layout(
        scene=dict(
            xaxis_title="X (mm)",
            yaxis_title="Y (mm)",
            zaxis_title="Z (mm)",
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        height=700,
    )

    return fig


def add_candidate_points(fig, candidates):
    """Add detected candidate points to the 3D figure."""

    if not candidates:
        return fig

    x = []
    y = []
    z = []

    for candidate in candidates:

        point = candidate["point_xyz_mm"]

        x.append(point[0])
        y.append(point[1])
        z.append(point[2])

    fig.add_trace(
        go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode="markers+text",
            marker=dict(
                size=7,
                symbol="circle",
            ),
            text=[
                f"branch_{i + 1:03d}"
                for i in range(len(candidates))
            ],
            textposition="top center",
            name="Detected candidates",
        )
    )

    return fig


def display_results(results):
    """
    Display the final prediction dictionary.

    Expected structure:

    {
        "case_id": "...",
        "parent": {
            "instance_id": "aorta"
        },
        "daughters": [...]
    }
    """

    daughters = results.get("daughters", [])

    st.subheader("Results")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Daughter vessels detected",
            len(daughters),
        )

    with col2:
        st.metric(
            "Parent vessel",
            results.get(
                "parent",
                {}
            ).get(
                "instance_id",
                "aorta"
            ),
        )

    if not daughters:
        st.warning(
            "No eligible daughter vessels were detected."
        )
        st.download_button(
            label="Download Prediction JSON",
            data=json.dumps(results, indent=2),
            file_name="prediction.json",
            mime="application/json",
        )
        return

    st.subheader("Detected Daughter Vessels")

    rows = []

    for daughter in daughters:

        rows.append(
            {
                "Instance": daughter.get(
                    "instance_id",
                    ""
                ),
                "Radius (mm)": daughter.get(
                    "radius_mm",
                    None
                ),
                "Ostium (mm)": str(
                    daughter.get(
                        "ostium_xyz_mm",
                        []
                    )
                ),
                "Seed (mm)": str(
                    daughter.get(
                        "seed_xyz_mm",
                        []
                    )
                ),
                "Direction": str(
                    daughter.get(
                        "direction_xyz",
                        []
                    )
                ),
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
    )

    st.download_button(
        label="Download Prediction JSON",
        data=json.dumps(
            results,
            indent=2
        ),
        file_name="prediction.json",
        mime="application/json",
        use_container_width=True,
    )


# ============================================================
# MAIN APPLICATION
# ============================================================

if ct_file is None or mask_file is None:

    st.info(
        "Upload a CT volume and aorta mask to begin."
    )

else:

    st.success(
        f"CT loaded: {ct_file.name}"
    )

    st.success(
        f"Aorta mask loaded: {mask_file.name}"
    )

    # --------------------------------------------------------
    # RUN ANALYSIS
    # --------------------------------------------------------

    if run_button:

        with st.spinner(
            "Running BranchSeed pipeline..."
        ):

            try:

                with tempfile.TemporaryDirectory() as directory:
                    ct_path = Path(directory) / ("ct.nii.gz" if ct_file.name.endswith(".gz") else "ct.nii")
                    mask_path = Path(directory) / ("mask.nii.gz" if mask_file.name.endswith(".gz") else "mask.nii")
                    ct_path.write_bytes(ct_file.getvalue())
                    mask_path.write_bytes(mask_file.getvalue())
                    ct_image = load_nifti_image(ct_path)
                    mask_image = load_nifti_image(mask_path)
                    daughters = run_pipeline(ct_image, mask_image)
                    case_id = ct_file.name.removesuffix(".gz").removesuffix(".nii")
                    results = write_output(case_id, daughters, str(Path(directory) / "prediction.json"))

                st.session_state["mask_image"] = mask_image
                st.session_state["daughters"] = daughters
                st.session_state["results"] = results
                st.session_state["analysis_complete"] = True

                st.success(
                    "Analysis completed successfully!"
                )

            except Exception as e:

                st.session_state["analysis_complete"] = False

                st.error(
                    f"Pipeline failed: {e}"
                )

                st.exception(e)


# ============================================================
# DISPLAY VISUALIZATION
# ============================================================

if st.session_state.get(
    "analysis_complete",
    False
):

    daughters = st.session_state["daughters"]

    st.divider()

    st.header("Visualization")

    fig = create_aorta_visualization(
        st.session_state["mask_image"],
        daughters=daughters,
    )
    
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Lines show traced proximal centerlines. Arrows show the ostium-to-seed direction."
    )

    st.divider()

    display_results(st.session_state["results"])
