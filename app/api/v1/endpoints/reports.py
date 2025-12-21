from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, Dict, Any
from datetime import date, datetime, timedelta
from app.core.supabase import get_request_scoped_client
from app.core.security import get_current_user, require_role

router = APIRouter()


@router.get("/academic", response_model=Dict[str, Any])
async def get_academic_report(
    class_id: Optional[str] = Query(None),
    term: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Get aggregated academic report data"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        # Get all grades with filters
        query = db.table("grades").select("*")
        if class_id:
            query = query.eq("class_id", class_id)
        if term:
            query = query.eq("term", term)
        if academic_year:
            query = query.eq("academic_year", academic_year)
        
        grades_response = query.execute()
        grades = grades_response.data
        
        # Get students count
        students_query = db.table("students").select("id", count="exact")
        if class_id:
            students_query = students_query.eq("class_id", class_id)
        students_response = students_query.execute()
        total_students = students_response.count or len(students_response.data)
        
        # Get teachers count
        teachers_response = db.table("teachers").select("id", count="exact").execute()
        total_teachers = teachers_response.count or 0
        
        # Get classes count
        classes_query = db.table("classes").select("id", count="exact")
        if academic_year:
            classes_query = classes_query.eq("academic_year", academic_year)
        classes_response = classes_query.execute()
        total_classes = classes_response.count or 0
        
        # Calculate statistics
        if not grades:
            return {
                "total_students": total_students,
                "total_teachers": total_teachers,
                "total_classes": total_classes,
                "pass_percentage": 0,
                "fail_percentage": 0,
                "average_grade": "N/A",
                "top_performers": [],
                "class_wise_stats": []
            }
        
        # Grade mapping
        grade_points = {"A+": 4.0, "A": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7, "C+": 2.3, "C": 2.0, "C-": 1.7, "D": 1.0, "F": 0.0}
        
        # Calculate pass/fail
        total_grades = len(grades)
        passed = sum(1 for g in grades if g.get("grade") != "F")
        failed = total_grades - passed
        
        pass_percentage = (passed / total_grades * 100) if total_grades > 0 else 0
        fail_percentage = (failed / total_grades * 100) if total_grades > 0 else 0
        
        # Calculate average grade
        total_points = sum(grade_points.get(g.get("grade", "F"), 0.0) for g in grades)
        avg_points = total_points / total_grades if total_grades > 0 else 0
        
        # Get top performers (by student)
        student_grades: Dict[str, Dict[str, Any]] = {}
        for grade in grades:
            student_id = grade.get("student_id")
            if student_id not in student_grades:
                student_grades[student_id] = {"grades": [], "total_marks": 0, "count": 0}
            student_grades[student_id]["grades"].append(grade)
            student_grades[student_id]["total_marks"] += float(grade.get("marks", 0))
            student_grades[student_id]["count"] += 1
        
        # Get student names
        student_ids = list(student_grades.keys())
        student_map = {}
        if student_ids:
            students_response = db.table("students").select("id,admission_number,user_id").in_("id", student_ids).execute()
            student_map = {s["id"]: s for s in students_response.data}
            
            # Get user names
            user_ids = [s["user_id"] for s in student_map.values()]
            if user_ids:
                profiles_response = db.table("profiles").select("user_id,full_name").in_("user_id", user_ids).execute()
                profile_map = {p["user_id"]: p["full_name"] for p in profiles_response.data}
                
                for student_id in student_map:
                    student_map[student_id]["full_name"] = profile_map.get(student_map[student_id]["user_id"], "Unknown")
        
        # Calculate top performers
        top_performers = []
        for student_id, data in student_grades.items():
            if data["count"] > 0:
                avg_marks = data["total_marks"] / data["count"]
                student_info = student_map.get(student_id, {})
                top_performers.append({
                    "student_id": student_id,
                    "name": student_info.get("full_name", "Unknown"),
                    "admission_number": student_info.get("admission_number", ""),
                    "average_marks": round(avg_marks, 2),
                    "grade": get_grade_from_marks(avg_marks)
                })
        
        top_performers.sort(key=lambda x: x["average_marks"], reverse=True)
        top_performers = top_performers[:10]  # Top 10
        
        # Class-wise statistics
        class_stats: Dict[str, Dict[str, Any]] = {}
        for grade in grades:
            class_id_grade = grade.get("class_id")
            if class_id_grade not in class_stats:
                class_stats[class_id_grade] = {"total": 0, "passed": 0, "failed": 0, "total_marks": 0}
            class_stats[class_id_grade]["total"] += 1
            if grade.get("grade") != "F":
                class_stats[class_id_grade]["passed"] += 1
            else:
                class_stats[class_id_grade]["failed"] += 1
            class_stats[class_id_grade]["total_marks"] += float(grade.get("marks", 0))
        
        # Get class names
        class_ids = list(class_stats.keys())
        class_wise_stats = []
        if class_ids:
            classes_response = db.table("classes").select("id,name,section").in_("id", class_ids).execute()
            class_map = {c["id"]: c for c in classes_response.data}
            
            for class_id, stats in class_stats.items():
                class_info = class_map.get(class_id, {})
                avg_marks = stats["total_marks"] / stats["total"] if stats["total"] > 0 else 0
                pass_pct = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
                class_wise_stats.append({
                    "class_id": class_id,
                    "class_name": f"{class_info.get('name', 'Unknown')} - {class_info.get('section', '')}",
                    "total_students": stats["total"],
                    "passed": stats["passed"],
                    "failed": stats["failed"],
                    "pass_percentage": round(pass_pct, 2),
                    "average_marks": round(avg_marks, 2)
                })
        
        return {
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_classes": total_classes,
            "pass_percentage": round(pass_percentage, 2),
            "fail_percentage": round(fail_percentage, 2),
            "average_grade": get_grade_from_points(avg_points),
            "top_performers": top_performers,
            "class_wise_stats": class_wise_stats
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/attendance", response_model=Dict[str, Any])
async def get_attendance_report(
    class_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Get aggregated attendance report data"""
    try:
        db = get_request_scoped_client(
            current_user.get("access_token"),
            current_user.get("role") in ["admin", "principal"]
        )
        
        # Get students for class if specified
        student_ids = None
        if class_id:
            students_response = db.table("students").select("user_id").eq("class_id", class_id).execute()
            student_ids = [s["user_id"] for s in students_response.data]
        
        # Get attendance records
        query = db.table("attendance").select("*")
        if student_ids:
            query = query.in_("user_id", student_ids)
        if date_from:
            query = query.gte("date", date_from)
        if date_to:
            query = query.lte("date", date_to)
        
        attendance_response = query.execute()
        attendance_records = attendance_response.data
        
        # Calculate statistics
        total_records = len(attendance_records)
        present = sum(1 for a in attendance_records if a.get("status") == "present")
        absent = sum(1 for a in attendance_records if a.get("status") == "absent")
        late = sum(1 for a in attendance_records if a.get("status") == "late")
        excused = sum(1 for a in attendance_records if a.get("status") == "excused")
        
        # Calculate percentages
        present_percentage = (present / total_records * 100) if total_records > 0 else 0
        absent_percentage = (absent / total_records * 100) if total_records > 0 else 0
        late_percentage = (late / total_records * 100) if total_records > 0 else 0
        
        # Daily attendance trend
        daily_stats: Dict[str, Dict[str, int]] = {}
        for record in attendance_records:
            date_key = record.get("date", "")
            if date_key not in daily_stats:
                daily_stats[date_key] = {"present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0}
            status = record.get("status", "")
            if status in daily_stats[date_key]:
                daily_stats[date_key][status] += 1
            daily_stats[date_key]["total"] += 1
        
        # Get class attendance stats if class_id provided
        class_stats = []
        if class_id:
            class_info_response = db.table("classes").select("id,name,section").eq("id", class_id).execute()
            if class_info_response.data:
                class_info = class_info_response.data[0]
                total_students = len(student_ids) if student_ids else 0
                avg_attendance = (present / (total_students * len(daily_stats))) * 100 if total_students > 0 and daily_stats else 0
                class_stats.append({
                    "class_id": class_id,
                    "class_name": f"{class_info.get('name', '')} - {class_info.get('section', '')}",
                    "total_students": total_students,
                    "average_attendance": round(avg_attendance, 2)
                })
        
        return {
            "total_records": total_records,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "present_percentage": round(present_percentage, 2),
            "absent_percentage": round(absent_percentage, 2),
            "late_percentage": round(late_percentage, 2),
            "daily_trend": [
                {
                    "date": date_key,
                    "present": stats["present"],
                    "absent": stats["absent"],
                    "late": stats["late"],
                    "excused": stats["excused"],
                    "total": stats["total"]
                }
                for date_key, stats in sorted(daily_stats.items())
            ],
            "class_stats": class_stats
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/financial", response_model=Dict[str, Any])
async def get_financial_report(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Get aggregated financial report data"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Get expenses
        expenses_query = db.table("expenses").select("*")
        if date_from:
            expenses_query = expenses_query.gte("date", date_from)
        if date_to:
            expenses_query = expenses_query.lte("date", date_to)
        expenses_response = expenses_query.execute()
        expenses = expenses_response.data
        
        # Get donations
        donations_query = db.table("donations").select("*")
        if date_from:
            donations_query = donations_query.gte("date", date_from)
        if date_to:
            donations_query = donations_query.lte("date", date_to)
        donations_response = donations_query.execute()
        donations = donations_response.data
        
        # Get salary records
        salary_query = db.table("salary_records").select("*")
        if date_from:
            salary_query = salary_query.gte("paid_date", date_from)
        if date_to:
            salary_query = salary_query.lte("paid_date", date_to)
        salary_response = salary_query.execute()
        salaries = salary_response.data
        
        # Calculate totals
        total_expenses = sum(float(e.get("amount", 0)) for e in expenses)
        total_donations = sum(float(d.get("amount", 0)) for d in donations)
        total_salaries = sum(float(s.get("net_salary", 0)) for s in salaries)
        
        # Expense breakdown by category
        expense_by_category: Dict[str, float] = {}
        for expense in expenses:
            category = expense.get("category", "Other")
            expense_by_category[category] = expense_by_category.get(category, 0) + float(expense.get("amount", 0))
        
        # Monthly breakdown
        monthly_stats: Dict[str, Dict[str, float]] = {}
        
        for expense in expenses:
            date_str = expense.get("date", "")
            if date_str:
                month_key = date_str[:7]  # YYYY-MM
                if month_key not in monthly_stats:
                    monthly_stats[month_key] = {"expenses": 0, "donations": 0, "salaries": 0, "net": 0}
                monthly_stats[month_key]["expenses"] += float(expense.get("amount", 0))
        
        for donation in donations:
            date_str = donation.get("date", "")
            if date_str:
                month_key = date_str[:7]
                if month_key not in monthly_stats:
                    monthly_stats[month_key] = {"expenses": 0, "donations": 0, "salaries": 0, "net": 0}
                monthly_stats[month_key]["donations"] += float(donation.get("amount", 0))
        
        for salary in salaries:
            date_str = salary.get("paid_date", "")
            if date_str:
                month_key = date_str[:7]
                if month_key not in monthly_stats:
                    monthly_stats[month_key] = {"expenses": 0, "donations": 0, "salaries": 0, "net": 0}
                monthly_stats[month_key]["salaries"] += float(salary.get("net_salary", 0))
        
        # Calculate net for each month
        for month_key in monthly_stats:
            monthly_stats[month_key]["net"] = (
                monthly_stats[month_key]["donations"] - 
                monthly_stats[month_key]["expenses"] - 
                monthly_stats[month_key]["salaries"]
            )
        
        net_income = total_donations - total_expenses - total_salaries
        
        return {
            "total_expenses": round(total_expenses, 2),
            "total_donations": round(total_donations, 2),
            "total_salaries": round(total_salaries, 2),
            "net_income": round(net_income, 2),
            "expense_by_category": {k: round(v, 2) for k, v in expense_by_category.items()},
            "monthly_breakdown": [
                {
                    "month": month_key,
                    "expenses": round(stats["expenses"], 2),
                    "donations": round(stats["donations"], 2),
                    "salaries": round(stats["salaries"], 2),
                    "net": round(stats["net"], 2)
                }
                for month_key, stats in sorted(monthly_stats.items())
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


def get_grade_from_marks(marks: float) -> str:
    """Convert marks to grade"""
    if marks >= 90:
        return "A+"
    elif marks >= 85:
        return "A"
    elif marks >= 80:
        return "B+"
    elif marks >= 75:
        return "B"
    elif marks >= 70:
        return "B-"
    elif marks >= 65:
        return "C+"
    elif marks >= 60:
        return "C"
    elif marks >= 55:
        return "C-"
    elif marks >= 50:
        return "D"
    else:
        return "F"


def get_grade_from_points(points: float) -> str:
    """Convert grade points to grade letter"""
    if points >= 3.7:
        return "A"
    elif points >= 3.3:
        return "B+"
    elif points >= 3.0:
        return "B"
    elif points >= 2.7:
        return "B-"
    elif points >= 2.3:
        return "C+"
    elif points >= 2.0:
        return "C"
    elif points >= 1.7:
        return "C-"
    elif points >= 1.0:
        return "D"
    else:
        return "F"

