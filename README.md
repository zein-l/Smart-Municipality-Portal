# Smart-Municipality-Portal



## Project Overview

The Smart Municipality Platform is a digital civic service platform built to transform and modernize public service delivery across Lebanese municipalities. This web-based system streamlines interactions between citizens and municipal authorities, reducing reliance on inefficient manual processes. It provides a scalable, multilingual, and secure solution with features including document requests, complaint management, IDP/immigration data visualization, and a multilingual AI chatbot.

This project was developed as a Final Year Project at the American University of Beirut by engineering students under the guidance of Dr. Ali Hajj.

## Features

- Online user registration, login, and two-factor authentication
- Role-Based Access Control (RBAC) for citizens, employees, and administrators
- Document submission and status tracking
- Complaint management system
- Interactive migration map with real-time IDP data using Leaflet.js
- AI-powered chatbot integrated with a custom knowledge base and NLP
- Multilingual support (Arabic, English, French, Armenian) via Google Translate API
- Cloud-ready microservices architecture
- Online payment integration
- Real-time municipal news, career postings, and tourism listings

## Architecture

The project uses a modular microservices architecture with Python Flask as the backend framework.

**Install dependencies**

pip install -r requirements.txt

**Run the application**

python app.py

**Access the platform**

http://127.0.0.1:5000/


## Testing and Validation

- Manual testing was performed across multiple browsers (Chrome, Firefox).
- API testing was done using Postman.
- Features tested include registration, login, document submission, complaint filing, chatbot queries, multilingual rendering, and map filtering.

## Future Work

- Switch to a production-grade database (e.g., PostgreSQL or MySQL)
- Integrate a custom NLP model for enhanced chatbot performance
- Add analytics dashboard for municipality staff
- Improve accessibility (screen reader, contrast, etc.)
- Fully deploy to cloud with CI/CD


## Tools and Technologies

- Python Flask (backend)
- SQLite (local database)
- HTML/CSS/JavaScript (frontend)
- Leaflet.js (interactive map)
- Google Translate API (multilingual support)
- Postman (API testing)
- Git and GitHub (version control)







