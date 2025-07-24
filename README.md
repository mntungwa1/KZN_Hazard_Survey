# KZN Hazard Risk Assessment Survey App

This repository contains a **Streamlit web application** for conducting hazard risk assessments across wards in KwaZulu-Natal (KZN).  
The app allows users to select wards interactively from a map, evaluate hazard risks, and export the results in multiple formats (CSV, Excel, Word, PDF, ZIP).

---

## **Features**
- **Password-protected login** using `.env` credentials.
- **Interactive map** with clickable wards (using `folium` and `streamlit-folium`).
- **Hazard selection & risk scoring** with custom hazards.
- **Automatic report generation** in CSV, Excel, Word, and PDF formats.
- **Email integration** for sending completed surveys.
- **Downloadable ZIP file** with all report formats.

---

## **Installation**

### **1. Clone the Repository**
```bash
git clone https://github.com/mntungwa1/KZN_Hazard_Survey.git
cd KZN_Hazard_Survey
"# KZN_Hazard_Survey" 
"# KZN_Hazard_Survey" 

# KZN Hazard Risk Assessment Survey

This is a Streamlit-based web application for conducting hazard risk assessments in KZN.

## How to Run Locally
1. Install Python 3.10 or higher.
2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the app:
   ```bash
   streamlit run hazard_survey_app.py
   ```

## Deploying on Streamlit Cloud
1. Upload all files to a public GitHub repository.
2. Go to [Streamlit Cloud](https://streamlit.io/cloud).
3. Click **New App**, select your repository, and deploy.
