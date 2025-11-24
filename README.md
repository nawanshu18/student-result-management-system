Student Result Management System — Streamlit App

A modern, secure, and responsive Student Result Management System built using Python + Streamlit + SQLite3.
This app includes Admin + Student login, advanced analytics, downloadable reports, OTP verification, and a beautiful animated UI.

Features
	•	Admin Login (3 methods)
	•	Password login
	•	Email OTP login
	•	Security question verification
	•	Student Login (Roll + DOB)
	•	Analytics Dashboard
	•	Subject-wise averages
	•	Distribution charts
	•	Top-performers (optional)
	•	Downloadable Reports
	•	HTML report
	•	PDF report (via ReportLab)
	•	Bulk CSV Import for students & marks
	•	Export All Data
	•	CSV
	•	Excel
	•	Full database
	•	Modern UI
	•	Dark mode
	•	Animated cards
	•	Gradient background
	•	Secure Data Storage (SQLite3)

⸻

Tech Stack
	•	Frontend & Backend: Streamlit
	•   Database: SQLite3
	•	Charts: Altair
	•	PDF Engine: ReportLab
	•	Language: Python 3

Installation
git clone https://github.com/nawanshu18/student-result-management-system.git
cd student-result-management-system
pip install -r requirements.txt
streamlit run app.py

Folder Structure
student-result-management-system/
│── app.py
│── .gitignore
│── README.md
│── student_db.sqlite   (auto-created)
│── main.ipynb          (optional)

Usage Workflow

Admin Panel
	•	Add/update students
	•	Add marks with max marks
	•	Import CSV
	•	Export data
	•	Set security question
	•	Change password
	•	View analytics

Student Dashboard
	•	Login using roll number + DOB
	•	View marks, percentage, totals
	•	Download report (HTML/PDF)

⸻

Security
	•	Password hashing (SHA-256)
	•	OTP-based admin login
	•	DOB-based student login
	•	Security question fallback

Support

If you like this project, give it a ⭐ on GitHub!
