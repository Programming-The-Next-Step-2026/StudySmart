# StudySmart

A smart study planner that builds your revision schedule automatically based on your exam dates and availability.

## Features
- Input your exams with dates and estimated study hours
- Set daily available study hours and commitments
- Import commitments automatically from Google Calendar
- Edit/cancel commitments inside the planner 
- Get an automatically generated color coded revision schedule
- Receive warnings when there is not enough time for an exam
- Get personalised study tips based on psychology research

## Installation
```bash
pip install -e .
```

## Usage
```bash
python src/study_smart/app.py
```

## Documentation

To view the documentation, run:

```bash
pdoc --docformat google src/study_smart/schedule.py
```

## Testing

To run the unit tests:

```bash
pytest tests/
```

To run tests with coverage report:

```bash
pytest --cov=study_smart tests/
```

## Google Calendar Integration
To use the Google Calendar import feature you need:
1. A Google account
2. A `credentials.json` file — get this from [Google Cloud Console](https://console.cloud.google.com) by creating a project, enabling the Google Calendar API, and creating OAuth 2.0 credentials (Desktop app)
3. Place `credentials.json` in the root of the project folder
4. On first run a browser window will open asking you to grant calendar access — after that a `token.json` file is saved automatically

Note: `credentials.json` and `token.json` are excluded from version control for security reasons.

## Study Tips
Hard-coded tips, based on pyschological research.