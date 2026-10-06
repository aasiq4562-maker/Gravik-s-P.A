PROFILE = {
    # Keep these values current; they are used directly in eligibility checks.
    "college": "Coimbatore Institute of Technology (CIT), Coimbatore, Tamil Nadu, India",
    "current_semester": "3rd semester",
    "cgpa": 8.48,
    "latest_semester_gpa": 8.92,
    "degree": "B.Tech Chemical Engineering",
    "year": "2nd year",
    "country": "India",
    "preferred_regions": ["Tamil Nadu", "Chennai", "India"],
    "interests": [
        "chemical engineering", "process engineering", "reaction engineering",
        "catalysis", "process simulation", "CSTR", "AI/ML for engineering",
        "sustainability", "energy", "materials", "environment",
        "green chemistry", "data science", "computational engineering"
    ],
    "high_value_skills": [
        "research", "MATLAB", "Python", "DWSIM", "Aspen", "simulation",
        "data analysis", "machine learning", "process design"
    ],
    "categories": [
        "research", "internship", "hackathon", "visit",
        "technical_program", "course", "competition", "conference", "seminar", "webinar", "fellowship", "paper_poster", "workshop", "bootcamp", "industrial_visit", "technical_competition"
    ]
}

SEARCH_QUERIES = [
    '"chemical engineering" research internship India 2026',
    '"chemical engineering" summer internship India 2026',
    '"chemical engineering" industrial internship 2026 India',
    '"research internship" IIT undergraduate 2026',
    '"research internship" CSIR undergraduate 2026',
    '"chemical engineering" hackathon 2026 India',
    '"chemical engineering" competition 2026 India',
    '"chemical engineering" technical program 2026 India',
    '"chemical engineering" workshop certificate 2026 India',
    '"chemical engineering" plant visit students 2026 India',
    '"engineering students" laboratory visit 2026 India',
    '"R&D centre visit" students 2026 India',
    '"open day" research laboratory students 2026 India',
    '"sustainability" student competition 2026 India',
    '"energy" technical program students 2026 India',
    '"materials" research internship undergraduate India 2026'
]

DEADLINE_DAYS = [7, 3, 1]
DAILY_LIMIT = 15
MIN_FIT_SCORE = 48

# V4 Free: optional AI. Leave GEMINI_API_KEY unset to use the deterministic fallback.
GEMINI_MODEL = "gemini-3.8-flash"
