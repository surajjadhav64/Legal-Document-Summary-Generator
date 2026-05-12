import os
import re
import getpass
import requests
import json
import matplotlib.pyplot as plt
import streamlit as st
from io import BytesIO
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain_groq import ChatGroq
from fpdf import FPDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import tempfile
from bs4 import BeautifulSoup
import feedparser
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Load environment variables
load_dotenv()

# Initialize Langchain Groq model
if not os.environ.get("GROQ_API_KEY"):
    os.environ["GROQ_API_KEY"] = getpass.getpass("Enter API key for Groq: ")

model = ChatGroq(model="llama-3.1-8b-instant", api_key=os.environ.get("GROQ_API_KEY"))

# Function to connect to Google Sheets
def connect_to_google_sheets():
    
    client = gspread.authorize(creds)
    return client

def store_updates_in_google_sheet(updates):
    print("Storing updates in Google Sheets...")  # Debug statement
    client = connect_to_google_sheets()
    sheet = client.open_by_key(sheet_id).sheet1  # Access the first sheet

    for _, update in updates.items():  # Iterate over the values of the dictionary
        try:
            print(f"Storing update: {update}")  # Debug statement
            sheet.append_row([update['title'], update['release_date']])  # Adjust fields as necessary
            print(f"Successfully stored: {update}")  # Success message
        except Exception as e:
            print(f"Error storing update: {e}")  # Log error

# Function to extract text from PDF
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

# Function to split text into chunks based on token estimate
def split_text_into_chunks(input_text, max_tokens=2000):
    words = input_text.split()
    chunks = []
    current_chunk = []
    current_token_count = 0
    
    for word in words:
        estimated_tokens = len(word.split())
        if current_token_count + estimated_tokens > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_token_count = estimated_tokens
        else:
            current_chunk.append(word)
            current_token_count += estimated_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

# Function to generate summary for each chunk
def generate_summary(text):
    prompt = f"Please summarize the following content:\n\n{text}"
    
    try:
        response = model.invoke(prompt)
        if hasattr(response, 'content'):
            summary = response.content
        else:
            summary = str(response)
        
        return summary.strip() if summary else "No summary available."
    except Exception as e:
        st.error(f"Error generating summary: {str(e)}")
        return None

# Function to save summary to a PDF
def save_summary_to_pdf(summary_text):
    try:
        summary_stream = BytesIO()
        summary_stream.write(summary_text.encode('utf-8'))
        summary_stream.seek(0)
        return summary_stream
    except Exception as e:
        raise RuntimeError(f"Failed to save summary to PDF: {e}")

# Function to detect key clauses and their purposes
def detect_key_clauses(text):
    clauses = {
        "Confidentiality Clause": r"(?i)(confidentiality|non-disclosure)[^.!?]*",
        "Liability Clause": r"(?i)(liability|indemnity)[^.!?]*",
        "Termination Clause": r"(?i)(termination|end|expire)[^.!?]*",
        "Force Majeure Clause": r"(?i)(force majeure)[^.!?]*",
        "Governing Law Clause": r"(?i)(governing law|jurisdiction)[^.!?]*",
        "Dispute Resolution Clause": r"(?i)(dispute resolution|arbitration|mediation)[^.!?]*",
        "Amendment Clause": r"(?i)(amendment|modification)[^.!?]*",
        "Warranty Clause": r"(?i)(warranty|guarantee)[^.!?]*",
    }
    detected_clauses = {}
    for clause_name, regex in clauses.items():
        matches = re.findall(regex, text)
        if matches:
            detected_clauses[clause_name] = list(set(matches))  # Unique matches
    return detected_clauses

# Function to detect hidden obligations and dependencies
def detect_hidden_obligations(text):
    obligations = {
        "Payment Obligations": r"(?i)(payment|fee|cost)[^.!?]*",
        "Reporting Obligations": r"(?i)(reporting|notification|inform)[^.!?]*",
        "Performance Obligations": r"(?i)(perform|provide|deliver)[^.!?]*",
        "Compliance Obligations": r"(?i)(compliance|law|regulation)[^.!?]*",
    }
    detected_obligations = {}
    for obligation_name, regex in obligations.items():
        matches = re.findall(regex, text)
        if matches:
            detected_obligations[obligation_name] = list(set(matches))  # Unique matches
    return detected_obligations

# Function to generate context for detected clauses
def generate_clause_context(clause_name):
    context_dict = {
        "Confidentiality Clause": "This clause is important to protect sensitive information shared between parties.",
        "Liability Clause": "This clause limits the liability of one or both parties in case of damages or losses.",
        "Termination Clause": "This clause outlines the conditions under which the agreement can be terminated.",
        "Force Majeure Clause": "This clause protects parties from liability if an unforeseen event prevents them from fulfilling their obligations.",
        "Governing Law Clause": "This clause specifies the jurisdiction whose laws will govern the agreement.",
        "Dispute Resolution Clause": "This clause outlines the method for resolving disputes that arise from the agreement.",
        "Amendment Clause": "This clause defines how changes to the agreement can be made.",
        "Warranty Clause": "This clause provides assurances regarding the quality and performance of the subject matter.",
    }
    return context_dict.get(clause_name, "No context available for this clause.")

# Function to generate context for hidden obligations
def generate_obligation_context(obligation_name):
    context_dict = {
        "Payment Obligations": "This obligation refers to the responsibility of one party to pay fees or costs as required by the agreement.",
        "Reporting Obligations": "This obligation entails the requirement to report or notify the other party about specific events or actions.",
        "Performance Obligations": "This obligation involves ensuring that certain actions or deliverables are completed as specified in the agreement.",
        "Compliance Obligations": "This obligation requires adherence to relevant laws and regulations applicable to the agreement.",
    }
    return context_dict.get(obligation_name, "No context available for this obligation.")

# Function to detect risks in the text
def detect_risks(text, summary):
    risk_phrases = [
        {"phrase": "penalty", "summary": "This indicates financial or legal consequences.", "risk_level": "High"},
        {"phrase": "liability", "summary": "This suggests potential financial responsibility.", "risk_level": "Medium"},
        {"phrase": "default", "summary": "This can lead to serious legal consequences.", "risk_level": "High"},
        {"phrase": "breach", "summary": "This may expose the party to significant penalties.", "risk_level": "High"},
        {"phrase": "suspension", "summary": "This indicates risks of halting services.", "risk_level": "Medium"},
        {"phrase": "should", "summary": "This implies a recommendation, which may not be mandatory.", "risk_level": "Low"},
        {"phrase": "may be required", "summary": "This suggests that obligations could exist under certain conditions.", "risk_level": "Low"},
        {"phrase": "indemnify", "summary": "This entails a duty to compensate for harm or loss, indicating potential financial risk.", "risk_level": "High"},
        {"phrase": "termination for cause", "summary": "This indicates a risk of ending the contract due to specific failures.", "risk_level": "High"},
        {"phrase": "compliance", "summary": "Non-compliance with regulations can lead to legal penalties.", "risk_level": "High"},
    ]
    
    detected_risks = []
    
    for item in risk_phrases:
        if item["phrase"].lower() in text.lower() or item["phrase"].lower() in summary.lower():
            phrase_start = text.lower().find(item["phrase"].lower())
            context = text[phrase_start - 50: phrase_start + 200]
            detected_risks.append({
                "phrase": item["phrase"],
                "summary": item["summary"],
                "context": context.strip(),
                "risk_level": item["risk_level"]
            })
    
    return detected_risks

# Function to calculate overall risk score
def calculate_overall_risk_score(detected_risks):
    risk_scores = {
        "High": 3,
        "Medium": 2,
        "Low": 1
    }
    total_score = sum(risk_scores.get(risk['risk_level'], 0) for risk in detected_risks)
    return total_score

# Function to plot bar chart for detected key clauses
def plot_detected_key_clauses_chart(detected_clauses):
    clause_names = list(detected_clauses.keys())
    occurrence_counts = [len(occurrences) for occurrences in detected_clauses.values()]

    plt.figure(figsize=(6, 3))  # Reduced size
    plt.bar(clause_names, occurrence_counts, color='skyblue')
    plt.title('Detected Key Clauses', fontsize=10)
    plt.xlabel('Clause Names', fontsize=8)
    plt.ylabel('Occurrences', fontsize=8)
    plt.xticks(rotation=45, fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()  # Close the figure after saving to prevent display
    return buf

# Function to plot bar chart for detected hidden obligations
def plot_detected_hidden_obligations_chart(detected_obligations):
    obligation_names = list(detected_obligations.keys())
    occurrence_counts = [len(occurrences) for occurrences in detected_obligations.values()]

    plt.figure(figsize=(6, 3))  # Reduced size
    plt.bar(obligation_names, occurrence_counts, color='lightgreen')
    plt.title('Detected Hidden Obligations and Dependencies', fontsize=10)
    plt.xlabel('Obligation Names', fontsize=8)
    plt.ylabel('Occurrences', fontsize=8)
    plt.xticks(rotation=45, fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()  # Close the figure after saving to prevent display
    return buf

# Function to plot bar chart for detected risks by risk level
def plot_risk_level_bar_chart(detected_risks):
    risk_levels = [risk['risk_level'] for risk in detected_risks]
    risk_counts = {level: risk_levels.count(level) for level in set(risk_levels)}

    plt.figure(figsize=(4, 3))  # Smaller figure size
    plt.bar(risk_counts.keys(), risk_counts.values(), color='salmon')
    plt.xticks(rotation=45, ha='right')
    plt.title("Detected Risks by Level", fontsize=10)
    plt.xlabel("Risk Level")
    plt.ylabel("Count")

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()  # Close the figure after saving to prevent display
    return buf

# Function to generate the complete report as a PDF
def generate_complete_report(summary_text, detected_clauses, detected_obligations, risks, updates):
    # Debug statement
    print(f"Updates passed to report: {updates}")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="Legal Document Report", ln=True, align='C')
    pdf.cell(200, 10, txt="Summary:", ln=True)
    pdf.multi_cell(0, 10, summary_text.encode('latin-1', 'replace').decode('latin-1'))  # Handle encoding

    pdf.cell(200, 10, txt="Detected Key Clauses:", ln=True)
    for clause, occurrences in detected_clauses.items():
        pdf.cell(0, 10, txt=f"{clause}: {', '.join(occurrences)}", ln=True)

    pdf.cell(200, 10, txt="Hidden Obligations:", ln=True)
    for obligation, occurrences in detected_obligations.items():
        pdf.cell(0, 10, txt=f"{obligation}: {', '.join(occurrences)}", ln=True)

    # Add Regulatory Updates
    pdf.cell(200, 10, txt="Regulatory Updates:", ln=True)
    for update in updates:
        if isinstance(update, dict) and 'title' in update and 'link' in update:
            pdf.cell(0, 10, txt=f"{update['title']}: {update['link']}", ln=True)
        else:
            pdf.cell(0, 10, txt="Invalid update format", ln=True)

    # Add charts to the PDF
    for image_buf in [plot_detected_key_clauses_chart(detected_clauses), 
                      plot_detected_hidden_obligations_chart(detected_obligations), 
                      plot_risk_level_bar_chart([])]:  # Pass an empty list for now
        image_path = tempfile.mktemp(suffix='.png')
        with open(image_path, 'wb') as img_file:
            img_file.write(image_buf.getvalue())
        pdf.image(image_path, x=10, w=180)  # Adjust size as necessary

    # Write to a temporary file and then read back
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        pdf.output(temp_file.name)
        temp_file.seek(0)
        pdf_output = BytesIO(temp_file.read())
        
    return pdf_output

# Function to send email with the report
def send_email(report_pdf, recipient_email):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = "Your Legal Document Report"

    body = "Attached is your legal document report."
    msg.attach(MIMEText(body, 'plain'))

    attachment = MIMEApplication(report_pdf.read(), _subtype='pdf')
    attachment.add_header('Content-Disposition', 'attachment', filename='report.pdf')
    msg.attach(attachment)

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True, None  # Return success and no error
    except Exception as e:
        return False, str(e)  # Return failure and the error message

# Function to fetch the latest GDPR updates from the RSS feed
def fetch_latest_gdpr_updates():
    url = "https://gdpr-info.eu/"
    feed = feedparser.parse(url)

    updates = []
    
    # Extract the latest 3 updates
    for entry in feed.entries[:3]:
        title = entry.title
        link = entry.link
        updates.append({"update": title, "link": link})

    return updates

# Function to fetch live recitals from the GDPR website
def fetch_gdpr_recitals():
    url = "https://gdpr-info.eu/recitals/"
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code != 200:
        st.error("Failed to fetch data from the GDPR website.")
        return {}

    soup = BeautifulSoup(response.content, 'html.parser')

    recitals = {}
    # Locate all recital links
    articles = soup.find_all('div', class_='artikel')
    
    # Extract each recital's link and title
    for i, article in enumerate(articles):
        if i >= 3:  # Limit to the first 3 recitals
            break
        link = article.find('a')['href']
        number = article.find('span', class_='nummer').text.strip('()')
        title = article.find('span', class_='titel').text.strip()
        
        # Fetch the content of each recital
        rec_response = requests.get(link)
        if rec_response.status_code == 200:
            rec_soup = BeautifulSoup(rec_response.content, 'html.parser')
            content = rec_soup.find('div', class_='entry-content').get_text(strip=True)

            # Extract the release date (adjust the selector if necessary)
            date_element = rec_soup.find('time')
            release_date = date_element['datetime'] if date_element else "Date not available"

            recitals[number] = {
                'title': title,
                'content': content,
                'release_date': release_date
            }
        else:
            print(f"Failed to fetch recital {number} from {link}")

    return recitals

# Function to answer questions about the document
def answer_question(question, document_text):
    prompt = f"The following is a legal document:\n\n{document_text}\n\nBased on this document, answer the following question: {question}"
    
    try:
        response = model.invoke(prompt)
        if hasattr(response, 'content'):
            answer = response.content
        else:
            answer = str(response)
        
        return answer.strip() if answer else "No answer available."
    except Exception as e:
        st.error(f"Error answering question: {str(e)}")
        return None

# Streamlit app configuration
st.set_page_config(page_title="Legal Document Summary Generator", page_icon="⚖", layout="wide")

# Upload section
st.header("📤 Upload Your Legal Document")
uploaded_pdf = st.file_uploader("Upload a PDF", type=["pdf"])

# Initialize session state for updates
if 'updates' not in st.session_state:
    st.session_state.updates = []

if uploaded_pdf:
    try:
        extracted_text = extract_text_from_pdf(uploaded_pdf)
        text_chunks = split_text_into_chunks(extracted_text)

        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
            ["Extracted Text", "Summary", "Key Clauses", "Hidden Obligations",
             "Risk Analysis", "Regulatory Updates", "Chatbot"]
        )

        with tab1:
            st.subheader("📄 Extracted Text")
            st.text_area("Extracted Text:", extracted_text, height=300)

        # In Tab 2 for Summary
        with tab2:
            st.subheader("📋 Summary")
            summaries = []
            with st.spinner("Generating summary..."):
                for chunk in text_chunks:
                    summary = generate_summary(chunk)
                    if summary:
                        summaries.append(summary)

            final_summary = " ".join(summaries)
            st.text_area("Generated Summary:", final_summary, height=300)

            # Save the summary to a PDF and get the bytes-like object
            pdf_data = save_summary_to_pdf(final_summary)

            # Create a download button for the PDF
            st.download_button(
                label="Download Summary as PDF",
                data=pdf_data.getvalue(),  # Use getvalue() to get the bytes
                file_name="summary.pdf",
                mime="application/pdf"
            )

        with tab3:
            st.subheader("🔍 Detected Key Clauses")
            detected_clauses = detect_key_clauses(extracted_text)

            st.write(f"**Document Name:** {uploaded_pdf.name}")

            if detected_clauses:
                for clause_name, occurrences in detected_clauses.items():
                    st.markdown(f"### **{clause_name}**")
                    st.write(f"**Occurrences:** {', '.join(occurrences)}")
                    context = generate_clause_context(clause_name)
                    st.write(f"**Context:** {context}")

                clause_chart_buf = plot_detected_key_clauses_chart(detected_clauses)
                st.image(clause_chart_buf.getvalue(), caption="Detected Key Clauses Chart")

            else:
                st.write("No key clauses detected in the document.")

        with tab4:
            st.subheader("🔍 Hidden Obligations and Dependencies")
            detected_obligations = detect_hidden_obligations(extracted_text)

            st.write(f"**Document Name:** {uploaded_pdf.name}")

            if detected_obligations:
                for obligation_name, occurrences in detected_obligations.items():
                    st.markdown(f"### **{obligation_name}**")
                    st.write(f"**Occurrences:** {', '.join(occurrences)}")
                    context = generate_obligation_context(obligation_name)
                    st.write(f"**Context:** {context}")

                obligation_chart_buf = plot_detected_hidden_obligations_chart(detected_obligations)
                st.image(obligation_chart_buf.getvalue(), caption="Detected Hidden Obligations Chart")

            else:
                st.write("No hidden obligations detected in the document.")

        with tab5:
            st.subheader("Risk Analysis")
            detected_risks = detect_risks(extracted_text, final_summary)
            overall_risk_score = calculate_overall_risk_score(detected_risks)

            st.write(f"*Overall Risk Score:* {overall_risk_score}")

            if detected_risks:
                for risk in detected_risks:
                    with st.expander(risk['phrase'], expanded=False):
                        st.write(f"*Summary:* {risk['summary']} (Risk Level: {risk['risk_level']})")
                        short_context = risk['context'].strip().split('. ')[0] + '.'  # Take the first sentence
                        st.write(f"*Context:* {short_context}")
            else:
                st.write("No risks detected.")

            # Generate images for the risk analysis charts
            risk_level_chart_buf = plot_risk_level_bar_chart(detected_risks)
            st.image(risk_level_chart_buf.getvalue(), caption="Detected Risks by Level Chart")

        # GDPR Updates Tab
        with tab6:
            updates = fetch_latest_gdpr_updates()  # Fetch updates immediately
            print(updates)
            

            # Fetch and display GDPR recitals
            st.subheader("Regulatory Updates")
            recitals = fetch_gdpr_recitals()
            if st.button("Fetch Live Updates"):
                with st.spinner("Fetching updates..."):
                    
                    if recitals:
                        for number, details in recitals.items():
                            st.markdown(f"**Recital {number}: {details['title']}**")
                            st.write(details['content'])
                            st.write(f"**Release Date:** {details['release_date']}")
                    else:
                        st.write("No recitals found.")
                        
            if recitals:
                st.session_state.updates = recitals  # Store updates in session state
                store_updates_in_google_sheet(recitals)  # Store updates in Google Sheets
                st.success("Updates stored successfully.")
            else:
                st.write("No updates found to store.")
        
            # Update session state with fetched updates
            st.session_state.updates = recitals
            
            # Store updates into Google Sheets
            store_updates_in_google_sheet(recitals)

            # Send Report Section
            st.subheader("📧 Send Report via Email")
            email_address = st.text_input("Enter your email address:")
            
            if st.button("Send Report"):
                report_pdf = generate_complete_report(
                    final_summary, 
                    detected_clauses, 
                    detected_obligations, 
                    {},  # Pass an empty dict for risks
                    st.session_state.updates  # Pass the stored updates
                )
                success, error = send_email(report_pdf, email_address)
                
                if success:
                    st.success("Report sent successfully!")
                else:
                    st.error(f"Error sending report: {error}")

        # Chatbot Tab
        with tab7:
            st.subheader("🤖 Chatbot")
            question = st.text_input("Ask a question about the document:")
            if question:
                with st.spinner("Getting answer..."):
                    answer = answer_question(question, extracted_text)
                    if answer:
                        st.write(f"**Answer:** {answer}")
                    else:
                        st.write("Sorry, I couldn't find an answer to that question.")

    except RuntimeError as e:
        st.error(f"❌ {e}")