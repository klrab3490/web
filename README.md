# 3D Model Generator

A web application for generating 3D models using OpenSCAD and AI technologies.

## Features

- Generate 3D models from text descriptions
- Convert images to 3D models
- Token-based system for model generation
- Secure payment processing with Razorpay

## Setup

1. Create a virtual environment: `python -m venv venv`
2. Activate the virtual environment: 
   - Windows: `venv\Scripts\activate`
   - Unix/Mac: `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Set up environment variables in `.env` file
5. Run the application: `python run.py`

## Project Structure

The project follows a modular architecture with separation of concerns:
- `app/`: Main application code
  - `api/`: API endpoints
  - `controllers/`: Business logic
  - `models/`: Data models
  - `services/`: External service integrations
  - `security/`: Security utilities
  - `templates/`: HTML templates
  - `static/`: Static assets

## License

MIT
