# web/app.py

import sys
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


def create_aorta_visualization(mask_image, candidates=None):
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

                ct_path = save_uploaded_file(
                    ct_file
                )

                mask_path = save_uploaded_file(
                    mask_file
                )

                # ------------------------------------------------
                # TEMPORARY PIPELINE
                #
                # Replace this section with your team's
                # final run_pipeline() function once run.py
                # is complete.
                # ------------------------------------------------

                from src.preprocessing import preprocess_case
                from src.detection import detect_candidates
                from src.filtering import filter_candidates

                data = preprocess_case(
                    ct_path,
                    mask_path,
                )

                candidates = detect_candidates(
                    data["ct_image"],
                    data["aorta_mask_image"],
                )

                filtered = filter_candidates(
                    candidates,
                    data["ct_image"].GetSize()[::-1],
                    data["ct_image"].GetSpacing()
                )

                # ------------------------------------------------
                # CURRENT VISUALIZATION
                # ------------------------------------------------

                st.session_state[
                    "data"
                ] = data

                st.session_state[
                    "candidates"
                ] = filtered

                st.session_state[
                    "analysis_complete"
                ] = True

                st.success(
                    "Analysis completed successfully!"
                )

            except Exception as e:

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

    data = st.session_state["data"]

    candidates = st.session_state[
        "candidates"
    ]

    st.divider()

    st.header("Visualization")

    fig = create_aorta_visualization(
    data["aorta_mask_image"],
    filtered
    )
    
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Candidate points represent locations identified "
        "by the detection and filtering stages."
    )

    st.divider()

    st.header("Pipeline Results")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Raw candidates",
            "—",
        )

    with col2:
        st.metric(
            "Filtered candidates",
            len(candidates),
        )

    with col3:
        st.metric(
            "Pipeline status",
            "Complete",
        )

    st.info(
        "Final daughter-vessel geometry will appear here "
        "once tracing and geometry modules are integrated."
    )

