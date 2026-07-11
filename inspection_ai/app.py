"""
Streamlit UI for AI Inspection Report Automation.
"""

import asyncio
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inspection_ai.services import (
    ProjectManager,
    PDFProcessor,
    ImageProcessor,
    MappingService,
    PlaywrightService,
    ReviewService,
    AsyncExtractService,
    transform_extracted_data,
    get_quire_fields_from_extraction,
)


def main():
    st.set_page_config(page_title="AI Inspection Report", layout="wide")

    if "project_id" not in st.session_state:
        st.session_state.project_id = None

    page = st.sidebar.radio(
        "Navigation", ["Dashboard", "Upload", "Review", "Automation"]
    )

    if page == "Dashboard":
        dashboard_page()
    elif page == "Upload":
        upload_page()
    elif page == "Review":
        review_page()
    elif page == "Automation":
        automation_page()


def dashboard_page():
    st.title("AI Inspection Report - Dashboard")

    project_name = st.text_input("Project Name")

    if st.button("Create Project"):
        pm = ProjectManager()
        pm.create_project(project_name)
        st.session_state.project_id = pm.project_id
        st.success(f"Project created: {pm.project_id}")

    if st.session_state.project_id:
        st.info(f"Current Project: {st.session_state.project_id}")


def upload_page():
    st.title("Upload Files")

    if not st.session_state.project_id:
        st.warning("Create a project first")
        return

    pm = ProjectManager(st.session_state.project_id)

    handwritten_pdf = st.file_uploader("Handwritten Questionnaire", type=["pdf"])
    scanned_pdf = st.file_uploader("Scanned Report", type=["pdf"])
    images = st.file_uploader(
        "Building Images", type=["jpg", "png"], accept_multiple_files=True
    )

    if st.button("Start Processing"):
        progress_placeholder = st.empty()
        progress_bar = st.progress(0)

        async def process_all():
            handwritten_path = None
            scanned_path = None

            if handwritten_pdf:
                handwritten_path = _save_uploaded_file(
                    handwritten_pdf, pm.project_path, "handwritten"
                )
                pm.save_document_output({"status": "processing"})

            if scanned_pdf:
                scanned_path = _save_uploaded_file(
                    scanned_pdf, pm.project_path, "scanned"
                )
                pm.save_document_output({"status": "processing"})

            pdf_results = {}
            image_results = []

            if handwritten_path or scanned_path:
                progress_placeholder.info("Processing PDFs...")
                progress_bar.progress(25)
                pdf_processor = PDFProcessor(pm)
                pdf_results = await pdf_processor.process_pdfs(
                    handwritten_path or "", scanned_path or ""
                )
                pm.save_document_output(pdf_results)

            if images:
                progress_placeholder.info("Processing images...")
                progress_bar.progress(50)
                image_paths = []
                for img in images:
                    img_path = _save_uploaded_file(img, pm.project_path, "images")
                    image_paths.append(img_path)
                image_processor = ImageProcessor(pm)
                image_results = await image_processor.process_images(image_paths)
                pm.save_image_output(image_results)

            progress_placeholder.info("Transforming extracted data...")
            progress_bar.progress(75)
            extracted_data = transform_extracted_data(pdf_results, image_results)
            pm.save_document_output({"extracted_data": extracted_data})

            progress_bar.progress(100)
            progress_placeholder.success("Processing complete")
            return extracted_data

        extracted_data = asyncio.run(process_all())
        st.session_state.extracted_data = extracted_data
        st.success("Processing complete")


def _save_uploaded_file(uploaded_file, project_path: str, file_type: str) -> str:
    os.makedirs(os.path.join(project_path, "uploads", file_type), exist_ok=True)
    file_path = os.path.join(project_path, "uploads", file_type, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def review_page():
    st.title("Review & Edit")

    if not st.session_state.project_id:
        st.warning("Create a project first")
        return

    pm = ProjectManager(st.session_state.project_id)
    review_service = ReviewService(pm)

    review_data = review_service.get_review_data()

    st.subheader("Document Data")
    for key, value in review_data.get("document_data", {}).items():
        new_value = st.text_input(key, value=value)
        if new_value != value:
            review_service.update_field(key, new_value)

    st.subheader("Image Analysis")
    for img in review_data.get("image_analysis", []):
        with st.expander(f"Image: {img.get('image_name', 'Unknown')}"):
            col1, col2 = st.columns([1, 3])
            with col1:
                st.image(img.get("image_name"), width=150)
            with col2:
                st.markdown(f"**Room:** {img.get('room', 'N/A')}")
                st.markdown(f"**Category:** {img.get('category', 'N/A')}")
                st.markdown(f"**View:** {img.get('view', 'N/A')}")
                st.markdown(
                    f"**Materials:** {', '.join(img.get('materials', [])) or 'N/A'}"
                )
                st.markdown(
                    f"**Systems:** {', '.join(img.get('systems', [])) or 'N/A'}"
                )
                st.markdown(f"**Objects:** {img.get('objects', [])}")
                st.markdown(
                    f"**Visible Damage:** {', '.join(img.get('visible_damage', [])) or 'N/A'}"
                )
                st.markdown(
                    f"**Overall Condition:** {img.get('overall_condition', 'N/A')}"
                )
                st.markdown(f"**Caption:** {img.get('caption', 'N/A')}")
                st.markdown(f"**Mini Caption:** {img.get('mini_caption', 'N/A')}")
                st.markdown(f"**Notes:** {img.get('notes', 'N/A')}")

    st.subheader("Approval")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve Mapping"):
            review_service.approve_mapping()
            st.success("Mapping approved")
    with col2:
        if st.button("Reject Mapping"):
            review_service.reject_mapping()
            st.warning("Mapping rejected")


def automation_page():
    st.title("Automation")

    if not st.session_state.project_id:
        st.warning("Create a project first")
        return

    pm = ProjectManager(st.session_state.project_id)
    review_service = ReviewService(pm)

    if not review_service.is_approved():
        st.warning("Mapping must be approved before auto-fill")
        return

    report_url = st.text_input(
        "Quire Report URL", value="https://app.openquire.com/reports/1762900"
    )

    if st.button("Extract Quire Fields"):
        with st.spinner("Extracting from Quire..."):
            try:

                async def extract_quire():
                    extract_service = AsyncExtractService(
                        st.session_state.get("email", "user@example.com"),
                        st.session_state.get("password", "password"),
                    )
                    return await extract_service.extract(report_url)

                extraction_result = asyncio.run(extract_quire())
                st.session_state.quire_extraction = extraction_result
                st.session_state.quire_fields = get_quire_fields_from_extraction(
                    extraction_result
                )
                st.success("Fields extracted")
            except Exception as e:
                st.error(f"Extraction failed: {e}")

    if st.button("Run Mapping"):
        with st.spinner("Mapping fields..."):
            try:
                mapping_service = MappingService(pm)
                extracted_data = st.session_state.get("extracted_data", {})
                quire_fields = st.session_state.get("quire_fields", [])

                mapped = mapping_service.map_fields(
                    extracted_data,
                    quire_fields,
                    user_approved=True,
                )
                pm.save_mapping_output(mapped)
                st.session_state.mapped_data = mapped
                st.success(f"Mapped {len(mapped.get('field_mappings', []))} fields")

                st.subheader("Mapping Results")
                for m in mapped.get("field_mappings", []):
                    st.write(f"{m.get('canonical_name')}: {m.get('value')}")
            except Exception as e:
                st.error(f"Mapping failed: {e}")

    if st.button("Auto Fill"):
        with st.spinner("Filling form..."):
            try:
                pw = PlaywrightService(
                    st.session_state.get("email", "user@example.com"),
                    st.session_state.get("password", "password"),
                )
                pw.launch()
                pw.login()
                mapped = st.session_state.get("mapped_data", {})
                pw.fill_form(mapped)
                pw.close()
                st.success("Form filled")
            except Exception as e:
                st.error(f"Auto-fill failed: {e}")


if __name__ == "__main__":
    main()
