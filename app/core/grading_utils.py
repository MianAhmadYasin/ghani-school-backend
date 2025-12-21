"""Grade calculation utilities for the School Management System."""
from typing import Dict, Optional, List
from app.core.config import settings
from supabase import Client as SupabaseClient


def calculate_grade(marks: float, grading_system: str = "standard", criteria: Optional[List[Dict]] = None) -> str:
    """
    Calculate letter grade from marks (0-100).
    
    Args:
        marks: Numeric marks (0-100)
        grading_system: Grading system to use ("standard", "strict", "lenient") - deprecated, use criteria instead
        criteria: List of grading criteria dicts with keys: grade_name, min_marks, max_marks
    
    Returns:
        Letter grade (A+, A, B+, B, C+, C, D, F) or grade from custom criteria
    
    Grading Systems (fallback if no criteria):
    - standard: A+ (90-100), A (80-89), B+ (70-79), B (60-69), C+ (50-59), C (40-49), D (33-39), F (0-32)
    - strict: A+ (95-100), A (85-94), B+ (75-84), B (65-74), C+ (55-64), C (45-54), D (40-44), F (0-39)
    - lenient: A+ (85-100), A (75-84), B+ (65-74), B (55-64), C+ (45-54), C (35-44), D (30-34), F (0-29)
    """
    if marks < 0 or marks > 100:
        raise ValueError(f"Marks must be between 0 and 100, got {marks}")
    
    # Use custom criteria if provided
    if criteria:
        # Sort by display_order (highest first) to check from top grades down
        sorted_criteria = sorted(criteria, key=lambda x: x.get("display_order", 0), reverse=True)
        for criterion in sorted_criteria:
            min_marks = float(criterion.get("min_marks", 0))
            max_marks = float(criterion.get("max_marks", 100))
            if min_marks <= marks <= max_marks:
                return criterion.get("grade_name", "F")
        # If no match found, return lowest grade
        if sorted_criteria:
            return sorted(sorted_criteria, key=lambda x: x.get("display_order", 0))[0].get("grade_name", "F")
    
    # Fallback to hardcoded systems
    if grading_system == "strict":
        boundaries = {
            "A+": (95, 100),
            "A": (85, 94.99),
            "B+": (75, 84.99),
            "B": (65, 74.99),
            "C+": (55, 64.99),
            "C": (45, 54.99),
            "D": (40, 44.99),
            "F": (0, 39.99)
        }
    elif grading_system == "lenient":
        boundaries = {
            "A+": (85, 100),
            "A": (75, 84.99),
            "B+": (65, 74.99),
            "B": (55, 64.99),
            "C+": (45, 54.99),
            "C": (35, 44.99),
            "D": (30, 34.99),
            "F": (0, 29.99)
        }
    else:  # standard
        boundaries = {
            "A+": (90, 100),
            "A": (80, 89.99),
            "B+": (70, 79.99),
            "B": (60, 69.99),
            "C+": (50, 59.99),
            "C": (40, 49.99),
            "D": (33, 39.99),
            "F": (0, 32.99)
        }
    
    # Find the grade
    for grade, (min_marks, max_marks) in boundaries.items():
        if min_marks <= marks <= max_marks:
            return grade
    
    # Fallback (should never reach here)
    return "F"


def grade_to_gpa(grade: str, criteria: Optional[List[Dict]] = None) -> float:
    """
    Convert letter grade to GPA (0.0 to 4.0 scale).
    
    Args:
        grade: Letter grade (A+, A, B+, B, C+, C, D, F) or custom grade name
        criteria: List of grading criteria dicts with keys: grade_name, gpa_value
    
    Returns:
        GPA value (0.0 to 4.0)
    """
    # Use custom criteria if provided
    if criteria:
        for criterion in criteria:
            if criterion.get("grade_name", "").upper() == grade.upper():
                return float(criterion.get("gpa_value", 0.0))
    
    # Fallback to default mapping
    gpa_map = {
        "A+": 4.0,
        "A": 4.0,
        "B+": 3.5,
        "B": 3.0,
        "C+": 2.5,
        "C": 2.0,
        "D": 1.0,
        "F": 0.0
    }
    return gpa_map.get(grade.upper(), 0.0)


def is_passing_grade(grade: str, criteria: Optional[List[Dict]] = None) -> bool:
    """
    Check if a grade is passing.
    
    Args:
        grade: Letter grade
        criteria: List of grading criteria dicts with keys: grade_name, is_passing
    
    Returns:
        True if passing, False if failing
    """
    # Use custom criteria if provided
    if criteria:
        for criterion in criteria:
            if criterion.get("grade_name", "").upper() == grade.upper():
                return bool(criterion.get("is_passing", True))
    
    # Fallback to default (F is failing)
    return grade.upper() != "F"


def get_active_grading_scheme(db: SupabaseClient) -> Optional[Dict]:
    """
    Get the active/default grading scheme from database.
    
    Args:
        db: Supabase client
    
    Returns:
        Dict with scheme and criteria, or None if not found
    """
    try:
        # Try to get default scheme first
        default_response = db.table("grading_schemes").select("*").eq("is_default", True).eq("is_active", True).single().execute()
        
        if not default_response.data:
            # If no default, get first active scheme
            active_response = db.table("grading_schemes").select("*").eq("is_active", True).order("created_at").limit(1).single().execute()
            if not active_response.data:
                return None
            scheme = active_response.data
        else:
            scheme = default_response.data
        
        # Fetch criteria
        criteria_response = db.table("grading_criteria").select("*").eq("grading_scheme_id", scheme["id"]).order("display_order").execute()
        
        return {
            "scheme": scheme,
            "criteria": criteria_response.data or []
        }
    except Exception as e:
        # Log error but return None gracefully
        from app.core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Failed to fetch active grading scheme: {str(e)}")
        return None


def calculate_gpa(grades: list[str], criteria: Optional[List[Dict]] = None) -> Optional[float]:
    """
    Calculate overall GPA from a list of grades.
    
    Args:
        grades: List of letter grades
        criteria: List of grading criteria dicts with keys: grade_name, gpa_value
    
    Returns:
        Average GPA, or None if no grades provided
    """
    if not grades:
        return None
    
    total_gpa = sum(grade_to_gpa(grade, criteria=criteria) for grade in grades)
    return round(total_gpa / len(grades), 2)


def validate_marks(marks: float, min_marks: float = 0.0, max_marks: float = 100.0) -> None:
    """
    Validate marks are within acceptable range.
    
    Args:
        marks: Numeric marks
        min_marks: Minimum possible marks (default 0)
        max_marks: Maximum possible marks (default 100)
    
    Raises:
        ValueError if marks are outside the valid range
    """
    if marks < min_marks:
        raise ValueError(f"Marks cannot be less than {min_marks}, got {marks}")
    if marks > max_marks:
        raise ValueError(f"Marks cannot exceed {max_marks}, got {marks}")

