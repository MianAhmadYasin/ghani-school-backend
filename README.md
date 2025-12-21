# Backend API - Ghani Grammar School System

FastAPI-based backend for the School Management System with complete Supabase integration.

---

## 🚀 **Quick Start**

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env  # Edit with your Supabase credentials

# Start server
uvicorn main:app --reload
```

**Server:** http://localhost:8000  
**API Docs:** http://localhost:8000/docs  
**ReDoc:** http://localhost:8000/redoc

---

## 📁 **Project Structure**

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── endpoints/         # API route handlers
│   │   │   ├── auth.py        # Authentication
│   │   │   ├── students.py    # Student management
│   │   │   ├── teachers.py    # Teacher management
│   │   │   ├── classes.py     # Class management
│   │   │   ├── grades.py      # Grading system
│   │   │   ├── attendance.py  # Attendance tracking
│   │   │   ├── finance.py     # Finance operations
│   │   │   ├── announcements.py # Announcements
│   │   │   ├── papers.py      # Exam papers
│   │   │   ├── events.py      # Events management
│   │   │   ├── stationery.py  # Stationery
│   │   │   └── users.py       # User management
│   │   └── router.py          # Main API router
│   ├── core/
│   │   ├── config.py          # Configuration
│   │   ├── security.py        # JWT & authentication
│   │   └── supabase.py        # Supabase client
│   └── models/                # Pydantic models
│       ├── user.py
│       ├── student.py
│       ├── teacher.py
│       ├── class_model.py
│       ├── grade.py
│       ├── attendance.py
│       ├── finance.py
│       ├── stationery.py
│       ├── announcement.py
│       ├── event.py
│       ├── syllabus.py
│       └── timetable.py
├── main.py                    # FastAPI application entry
├── requirements.txt           # Python dependencies
├── database_schema.sql        # Main database schema
├── events_database_schema.sql # Events table (if missing)
├── .env.example               # Environment variables template
└── README.md                  # This file
```

---

## 🗄️ **Database Tables**

### **All tables in Supabase:**
1. `auth.users` - Supabase built-in
2. `public.profiles` - User profiles
3. `public.students` - Student records
4. `public.teachers` - Teacher records
5. `public.classes` - Class management
6. `public.grades` - Academic grades
7. `public.attendance` - Attendance tracking
8. `public.stationery_items` - Inventory
9. `public.stationery_distributions` - Distribution tracking
10. `public.salary_records` - Salary management
11. `public.expenses` - Expense tracking
12. `public.donations` - Donation records
13. `public.announcements` - Announcements
14. `public.notifications` - Notifications
15. `public.papers` - Exam papers
16. `public.syllabuses` - Syllabus uploads
17. `public.events` - Events management
18. `public.timetables` - Timetable configuration
19. `public.timetable_entries` - Timetable periods

---

## 🔌 **API Endpoints**

### **Authentication (`/api/v1/auth`)**
- `POST /signup` - Register new user
- `POST /login` - User login
- `GET /me` - Get current user
- `POST /logout` - Logout
- `POST /change-password` - Change password

### **Students (`/api/v1/students`)**
- `GET /` - List students
- `POST /` - Create student
- `GET /{id}` - Get student
- `PUT /{id}` - Update student
- `DELETE /{id}` - Delete student

### **Teachers (`/api/v1/teachers`)**
- `GET /` - List teachers
- `POST /` - Create teacher
- `GET /{id}` - Get teacher
- `PUT /{id}` - Update teacher
- `DELETE /{id}` - Delete teacher

### **Classes (`/api/v1/classes`)**
- `GET /` - List classes
- `POST /` - Create class
- `GET /{id}` - Get class
- `PUT /{id}` - Update class
- `DELETE /{id}` - Delete class
- `POST /{id}/add-students` - Add students to class

### **Grades (`/api/v1/grades`)**
- `GET /` - List grades
- `POST /` - Create grade
- `POST /bulk` - Bulk create grades
- `GET /{id}` - Get grade
- `PUT /{id}` - Update grade
- `DELETE /{id}` - Delete grade

### **Attendance (`/api/v1/attendance`)**
- `GET /` - List attendance
- `POST /` - Mark attendance
- `POST /bulk` - Bulk mark attendance
- `GET /{id}` - Get attendance
- `PUT /{id}` - Update attendance
- `DELETE /{id}` - Delete attendance

### **Finance (`/api/v1/finance`)**
- `GET /stationery/items` - List stationery
- `POST /stationery/items` - Create stationery item
- `PUT /stationery/items/{id}` - Update item
- `DELETE /stationery/items/{id}` - Delete item
- `POST /stationery/distributions` - Distribute stationery
- `GET /salaries` - List salary records
- `POST /salaries` - Create salary record
- `GET /expenses` - List expenses
- `POST /expenses` - Create expense
- `GET /donations` - List donations
- `POST /donations` - Record donation

### **Announcements (`/api/v1/announcements`)**
- `GET /` - List announcements
- `POST /` - Create announcement
- `GET /{id}` - Get announcement
- `PUT /{id}` - Update announcement
- `DELETE /{id}` - Delete announcement

### **Papers (`/api/v1/papers`)**
- `GET /` - List papers
- `POST /` - Upload paper
- `GET /stats` - Get statistics
- `GET /{id}` - Get paper
- `PUT /{id}` - Update paper
- `DELETE /{id}` - Delete paper

### **Events (`/api/v1/events`)**
- `GET /` - List events
- `POST /` - Create event
- `GET /stats` - Get statistics
- `GET /{id}` - Get event
- `PUT /{id}` - Update event
- `DELETE /{id}` - Delete event

**Full API documentation:** http://localhost:8000/docs

---

## 🔐 **Authentication**

### **How it Works:**
1. User logs in with email/password
2. Backend validates credentials with Supabase
3. Returns JWT access token
4. Frontend stores token
5. Token included in all API requests
6. Backend validates token for each request

### **Roles:**
- `admin` - Full system access
- `principal` - School-wide access
- `teacher` - Class and student management
- `student` - View own data

---

## 🧪 **Testing**

### **Using Swagger UI:**
```bash
# Open API docs
http://localhost:8000/docs

# Test endpoints:
1. Click endpoint
2. Click "Try it out"
3. Fill parameters
4. Click "Execute"
5. See response
```

### **Using cURL:**
```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@school.com","password":"admin123"}'

# Get students (with token)
curl -X GET http://localhost:8000/api/v1/students \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## 📊 **Database Integration**

All endpoints use `supabase_admin` client from `app/core/supabase.py`:

```python
from app.core.supabase import supabase_admin

# Example: Get students
response = supabase_admin.table("students").select("*").execute()
students = response.data
```

---

## 🚀 **Deployment**

See `../DEPLOYMENT.md` for production deployment instructions.

**Recommended:**
- Railway / Render for backend hosting
- Keep Supabase for database
- Use environment variables for secrets

---

## 📝 **Development**

### **Add New Endpoint:**
1. Create model in `app/models/`
2. Create endpoint in `app/api/v1/endpoints/`
3. Register in `app/api/v1/router.py`
4. Test in Swagger docs

### **Database Changes:**
1. Update schema in Supabase
2. Update Pydantic models
3. Update endpoint logic
4. Test changes

---

## 🛠️ **Dependencies**

Key packages (see `requirements.txt`):
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `supabase` - Supabase client
- `pydantic` - Data validation
- `python-jose` - JWT handling
- `passlib` - Password hashing
- `python-multipart` - File uploads

---

## 📚 **Resources**

- FastAPI Docs: https://fastapi.tiangolo.com
- Supabase Docs: https://supabase.com/docs
- Pydantic Docs: https://docs.pydantic.dev

---

**Backend API is production-ready!** ✅
