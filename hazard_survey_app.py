import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from streamlit_folium import st_folium
import folium
from pathlib import Path
from datetime import datetime, date
import os, smtplib, shutil, re
from email.message import EmailMessage
from docx import Document
from fpdf import FPDF
from dotenv import load_dotenv
import io

# --- Load Environment Variables ---
load_dotenv(dotenv_path="C:/tmp/KZN/.env")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", EMAIL_ADDRESS)
APP_PASSWORD = "kzn!23@"
ADMIN_PASSWORD = "kzn!23&"
ADMIN_EMAILS = [ADMIN_EMAIL, "mhugo@srk.co.za"]

# --- DEBUG: Show if .env values are loaded ---
if EMAIL_ADDRESS:
    st.write(f"Email loaded: {EMAIL_ADDRESS} | Password: OK" if EMAIL_PASSWORD else "Password missing!")
else:
    st.error("EMAIL_ADDRESS not found in .env file!")

# --- Configuration ---
BASE_DIR = Path("C:/temp/kzn")
TODAY_FOLDER = datetime.now().strftime("%d_%b_%Y")
SAVE_DIR = BASE_DIR / TODAY_FOLDER
EXCEL_PATH = Path("RiskAssessmentTool.xlsm")
GEOJSON_PATH = Path("KZN_wards.geojson")
MASTER_CSV = BASE_DIR / "all_submissions.csv"
LOGO_PATH = "Logo.png"
SRK_LOGO_PATH = "SRK_Logo.png"

# --- Setup ---
def ensure_save_dir():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    MASTER_CSV.parent.mkdir(parents=True, exist_ok=True)

def cleanup_old_folders(base_dir, days=30):
    now = datetime.now()
    pattern = re.compile(r"\d{2}_[A-Za-z]{3}_\d{4}")
    for folder in base_dir.iterdir():
        if folder.is_dir() and pattern.fullmatch(folder.name):
            try:
                if (now - datetime.strptime(folder.name, "%d_%b_%Y")).days > days:
                    shutil.rmtree(folder)
            except:
                continue

ensure_save_dir()
cleanup_old_folders(BASE_DIR)

def safe_filename(name):
    return re.sub(r'[^A-Za-z0-9_-]', '_', name)

# --- Authentication ---
def password_protection():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    password = st.text_input("Enter password to access the app:", type="password")
    if st.button("Login"):
        if password == APP_PASSWORD:
            st.session_state["authenticated"] = True
            st.success("Access granted. Please continue.")
            st.rerun()
        else:
            st.error("Incorrect password.")

if not st.session_state.get("authenticated", False):
    st.title("KZN Hazard Risk Assessment Survey - Login")
    password_protection()
    st.stop()

# --- Email Sending ---
def send_email(subject, body, to_emails, attachments):
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        st.warning("Email credentials missing in .env. Skipping email sending.")
        return

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = ", ".join(to_emails)
        msg.set_content(body)

        for attachment in attachments:
            with open(attachment, "rb") as f:
                file_data = f.read()
                msg.add_attachment(
                    file_data, maintype="application", subtype="octet-stream",
                    filename=Path(attachment).name
                )

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        st.success(f"Email sent to {to_emails}!")
    except Exception as e:
        st.error(f"Failed to send email: {e}")

# --- Save Responses ---
def append_to_master_csv(df):
    df.to_csv(MASTER_CSV, mode="a", header=not MASTER_CSV.exists(), index=False)

def save_responses(responses, name, ward, email, date_filled, district_muni, local_muni):
    ensure_save_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"{safe_filename(ward)}_{safe_filename(name)}_{timestamp}"

    # Paths for daily folder
    csv_path = SAVE_DIR / f"{base_filename}.csv"
    pdf_path = SAVE_DIR / f"{base_filename}.pdf"
    docx_path = SAVE_DIR / f"{base_filename}.docx"

    # Root copies
    csv_root = BASE_DIR / f"{base_filename}.csv"
    pdf_root = BASE_DIR / f"{base_filename}.pdf"
    docx_root = BASE_DIR / f"{base_filename}.docx"

    df = pd.DataFrame(responses)
    df.insert(0, "Respondent Name", name)
    df.insert(1, "Ward", ward)
    df.insert(2, "District Municipality", district_muni)
    df.insert(3, "Local Municipality", local_muni)
    df.insert(4, "Email", email)
    df.insert(5, "Date", date_filled)

    # Save CSV
    df.to_csv(csv_path, index=False)
    df.to_csv(csv_root, index=False)
    append_to_master_csv(df)

    # Save DOCX
    doc = Document()
    doc.add_heading("KZN Hazard Risk Assessment Survey", 0)
    doc.add_paragraph(
        f"Name: {name}\nWard: {ward}\nDistrict Municipality: {district_muni}\n"
        f"Local Municipality: {local_muni}\nEmail: {email}\nDate: {date_filled}\n---"
    )
    for _, row in df.iterrows():
        doc.add_paragraph(f"Hazard: {row['Hazard']} | Question: {row['Question']} | Response: {row['Response']}")
    doc.save(docx_path)
    shutil.copy(docx_path, docx_root)

    # Save PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="KZN Hazard Risk Assessment Survey", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10,
        txt=f"Name: {name}\nWard: {ward}\nDistrict Municipality: {district_muni}\n"
            f"Local Municipality: {local_muni}\nEmail: {email}\nDate: {date_filled}\n---"
    )
    for _, row in df.iterrows():
        pdf.multi_cell(0, 10, txt=f"Hazard: {row['Hazard']} | Question: {row['Question']} | Response: {row['Response']}")
    pdf.output(pdf_path)
    shutil.copy(pdf_path, pdf_root)

    return csv_path, docx_path, pdf_path

# --- Map Display ---
def display_map(gdf, selected_ward=None):
    m = folium.Map(location=[-29.5, 31.1], zoom_start=7)

    def style_function(feature):
        ward_name = feature["properties"][gdf.columns[0]]
        if ward_name == selected_ward:
            return {"fillColor": "blue", "color": "black", "weight": 2, "fillOpacity": 0.7}
        return {"fillColor": "green", "color": "black", "weight": 1, "fillOpacity": 0.3}

    def highlight_function(feature):
        return {"fillColor": "yellow", "color": "black", "weight": 2, "fillOpacity": 0.5}

    folium.GeoJson(
        data=gdf.__geo_interface__,
        style_function=style_function,
        highlight_function=highlight_function,
        tooltip=folium.GeoJsonTooltip(fields=[gdf.columns[0]], aliases=["Ward:"])
    ).add_to(m)

    return st_folium(m, height=500)

# --- Questions ---
questions_with_descriptions = {
    "Has this hazard occurred in the past?": [
        "0 - Has not occurred and has no chance of occurrence",
        "1 - Has not occurred but there is real potential for occurrence",
        "2 - Has occurred but only once",
        "3 - Has occurred but only a few times or rarely",
        "4 - Has occurred regularly or at least once a year",
        "5 - Occurs multiple times during a single year",
    ],
    "How frequently does it occur?": [
        "0 - Unknown / Not applicable",
        "1 - Decreasing",
        "2 - Stable",
        "3 - Marginally increasing",
        "4 - Increasing",
        "5 - Increasing rapidly",
    ],
    "What is the typical duration of the hazard?": [
        "0 - Unknown / Not applicable",
        "1 - Few minutes",
        "2 - Few hours",
        "3 - Few days",
        "4 - Few weeks",
        "5 - Few months",
    ],
    "What is the area of impact?": [
        "0 - None",
        "1 - Single property",
        "2 - Single Ward",
        "3 - Few wards",
        "4 - Entire municipality",
        "5 - Larger than municipality",
    ],
    "What is the impact on people?": [
        "0 - None",
        "1 - Low impact / Discomfort",
        "2 - Minimal impact / Minor injuries",
        "3 - Serious injuries / Health problems no fatalities",
        "4 - Fatalities / Serious health problems but confined",
        "5 - Multiple fatalities spread over wide area",
    ],
    "What is the impact on infrastructure and services?": [
        "0 - None",
        "1 - Low impact / Minor damage / Minor disruption",
        "2 - Some structural damage / Short term disruption of services",
        "3 - Medium structural damage / 1 Week disruption",
        "4 - Serious structural damage / Disruption of longer than a week",
        "5 - Total disruption of structure / Disruption of longer than a month",
    ],
    "What is the impact on the environment?": [
        "0 - Not applicable / No effects",
        "1 - Minor effects",
        "2 - Medium effects",
        "3 - Severe",
        "4 - Severe effects over wide area",
        "5 - Total destruction",
    ],
    "What is the level of economic disruption?": [
        "0 - No disruption",
        "1 - Some disruption",
        "2 - Medium disruption",
        "3 - Severe short-term disruption",
        "4 - Severe long-term disruption",
        "5 - Total stop in activities",
    ],
    "How predictable is the hazard?": [
        "0 - Not applicable",
        "1 - Effective early warning",
        "3 - Partially predictable",
        "5 - No early warning",
    ],
    "What is the urgency or priority level?": [
        "0 - Not applicable / No effects",
        "1 - Low priority",
        "2 - Medium priority",
        "3 - Medium high priority",
        "4 - High priority",
        "5 - Very high priority",
    ],
}
capacity_questions = [
    "Sufficient staff/human resources",
    "Experience and special knowledge",
    "Equipment",
    "Funding",
    "Facilities",
    "Prevention and mitigation plans",
    "Response and recovery plans",
]
capacity_options = [
    "Strongly Disagree",
    "Disagree",
    "Neutral",
    "Agree",
    "Strongly Agree",
]

# --- Hazard Question Rendering ---
def build_hazard_questions(hazards_to_ask):
    responses = []
    for hazard in hazards_to_ask:
        st.markdown(f"### {hazard}")
        for q, opts in questions_with_descriptions.items():
            response = st.radio(q, opts, key=f"{hazard}_{q}", index=0)
            responses.append({"Hazard": hazard, "Question": q, "Response": response})

        for cq in capacity_questions:
            response = st.radio(cq, capacity_options, key=f"{hazard}_{cq}", index=0)
            responses.append({"Hazard": hazard, "Question": cq, "Response": response})
        st.markdown("<hr>", unsafe_allow_html=True)
    return responses

# --- Load Data ---
@st.cache_data(show_spinner=False, ttl=3600)
def load_hazards():
    df = pd.read_excel(EXCEL_PATH, sheet_name="Hazard information", skiprows=1)
    return df.iloc[:, 0].dropna().tolist()

@st.cache_data(show_spinner=False, ttl=3600)
def load_ward_gdf():
    return gpd.read_file(GEOJSON_PATH).to_crs(epsg=4326)

# --- Survey ---
def run_survey():
    st.title("KZN Hazard Risk Assessment Survey")
    hazards = load_hazards()
    gdf = load_ward_gdf()
    selected_ward = st.session_state.get("selected_ward", None)
    map_data = display_map(gdf, selected_ward=selected_ward)

    if map_data.get("last_clicked"):
        pt = Point(map_data["last_clicked"]["lng"], map_data["last_clicked"]["lat"])
        for _, row in gdf.iterrows():
            if row.geometry.contains(pt):
                st.session_state["selected_ward"] = row[gdf.columns[0]]
                break

    ward_display = st.session_state.get("selected_ward", "")
    if ward_display:
        st.success(f"Selected Ward: {ward_display}")

    st.subheader("Select Applicable Hazards")
    selected = st.multiselect("Choose hazards:", hazards)
    custom = st.text_input("Other hazard") if st.checkbox("Add custom hazard") else ""

    if selected or custom:
        if st.button("Proceed"):
            st.session_state["show_form"] = True
            st.rerun()

    if st.session_state.get("show_form"):
        tab1, tab2 = st.tabs(["Respondent Info", "Hazard Risk Evaluation"])
        with tab1:
            with st.form("respondent_form"):
                name = st.text_input("Full Name")
                user_email = st.text_input("Your Email")
                district_muni = st.text_input("District Municipality")
                local_muni = st.text_input("Local Municipality")
                final_ward = ward_display or st.text_input("Ward (if not using map)")
                today = st.date_input("Date", value=date.today())
                proceed = st.form_submit_button("Save & Proceed to Hazard Evaluation")
                if proceed:
                    if not name or not final_ward:
                        st.error("Please fill in your name and ward.")
                    else:
                        st.session_state["respondent_info"] = {
                            "name": name,
                            "email": user_email,
                            "district": district_muni,
                            "local": local_muni,
                            "ward": final_ward,
                            "date": today
                        }
                        st.rerun()

        with tab2:
            if st.button("← Back to Respondent Info"):
                st.rerun()

            with st.form("hazard_form"):
                hazards_to_ask = selected + ([custom] if custom else [])
                responses = build_hazard_questions(hazards_to_ask)
                accept = st.checkbox("I accept all information is true and correct")
                submit = st.form_submit_button("Submit Survey")
                if submit:
                    info = st.session_state.get("respondent_info", {})
                    if not info:
                        st.error("Please complete Respondent Info first.")
                    elif not accept:
                        st.error("You must accept that all information is true and correct.")
                    else:
                        csv_file, doc_file, pdf_file = save_responses(
                            responses, info["name"], info["ward"], info["email"],
                            info["date"], info["district"], info["local"]
                        )
                        st.success("Survey submitted successfully!")
                        if info["email"]:
                            send_email("Your KZN Hazard Survey Submission",
                                       "Thank you for completing the survey.",
                                       [info["email"]], [csv_file, doc_file, pdf_file])
                        send_email("New KZN Hazard Survey Submission",
                                   "A new survey has been submitted.",
                                   ADMIN_EMAILS, [csv_file, doc_file, pdf_file])

# --- Main App ---
st.set_page_config(page_title="KZN Hazard Risk Assessment", layout="wide")
menu = st.sidebar.radio("Navigation", ["Survey"])

if os.path.exists(LOGO_PATH): st.sidebar.image(LOGO_PATH, width=180)
if os.path.exists(SRK_LOGO_PATH): st.sidebar.image(SRK_LOGO_PATH, width=160)

if menu == "Survey":
    run_survey()
