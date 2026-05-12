# Legal-Document-Summary-Generator
Overview
The Legal Document Summary Generator is a web application designed to help users analyze legal documents by extracting key information, generating summaries, identifying clauses and obligations, assessing risks, and providing regulatory updates. The app leverages various libraries and APIs to offer a comprehensive analysis of uploaded PDF documents.

# Features
> PDF Upload: Users can upload legal documents in PDF format.
> Text Extraction: Extracts text from the uploaded PDF for analysis.
> Summary Generation: Generates a concise summary of the document.
> Clause Detection: Identifies key legal clauses within the document.
> Obligation Detection: Detects hidden obligations and dependencies.
> Risk Analysis: Assesses risks associated with the document and provides an overall risk score.
> Regulatory Updates: Fetches and displays the latest updates related to GDPR.
> Email Reports: Allows users to send generated reports via email.
> Interactive Chatbot: Users can ask questions about the document, and the chatbot provides answers based on the content.

# Technologies Used
Python: The main programming language used for backend logic.
Streamlit: A framework for building web applications in Python.
Langchain Groq: For generating summaries and answering questions.
Google Sheets API: For storing updates in Google Sheets.
BeautifulSoup: For web scraping to fetch GDPR recitals.
Matplotlib: For visualizing detected clauses and risks.
FPDF: For generating PDF reports.
