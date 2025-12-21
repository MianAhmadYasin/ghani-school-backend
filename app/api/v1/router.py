from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, users, students, teachers, classes, grades, attendance, finance, 
    announcements, stationery, papers, settings, attendance_salary,
    notifications, timetables, syllabuses, reports
)
try:
    from app.api.v1.endpoints import grading_schemes
    GRADING_SCHEMES_AVAILABLE = True
except ImportError:
    GRADING_SCHEMES_AVAILABLE = False
# Import events separately since it was just created
try:
    from app.api.v1.endpoints import events
    EVENTS_AVAILABLE = True
except ImportError:
    EVENTS_AVAILABLE = False

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(students.router, prefix="/students", tags=["Students"])
api_router.include_router(teachers.router, prefix="/teachers", tags=["Teachers"])
api_router.include_router(classes.router, prefix="/classes", tags=["Classes"])
api_router.include_router(grades.router, prefix="/grades", tags=["Grades"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])
api_router.include_router(finance.router, prefix="/finance", tags=["Finance"])
api_router.include_router(announcements.router, prefix="/announcements", tags=["Announcements"])
if EVENTS_AVAILABLE:
    api_router.include_router(events.router, prefix="/events", tags=["Events"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(timetables.router, prefix="/timetables", tags=["Timetables"])
api_router.include_router(syllabuses.router, prefix="/syllabuses", tags=["Syllabuses"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(stationery.router, prefix="/stationery", tags=["Stationery"])
api_router.include_router(papers.router, prefix="/papers", tags=["Papers"])

from app.api.v1.endpoints import exams, results, exam_settings
api_router.include_router(exams.router, prefix="/exams", tags=["Exams"])
api_router.include_router(results.router, prefix="/results", tags=["Results"])
api_router.include_router(exam_settings.router, prefix="/exam-settings", tags=["Exam Settings"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(attendance_salary.router, prefix="/attendance-salary", tags=["Attendance-Salary"])
if GRADING_SCHEMES_AVAILABLE:
    api_router.include_router(grading_schemes.router, prefix="/grading-schemes", tags=["Grading Schemes"])




