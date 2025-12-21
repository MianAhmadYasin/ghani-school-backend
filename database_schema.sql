-- School Management System Database Schema
-- Run this in your Supabase SQL Editor

-- Note: Supabase already provides auth.users table
-- We extend it with custom tables

-- ============================================
-- PROFILES TABLE (extends auth.users)
-- ============================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- ============================================
-- TEACHERS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.teachers (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE NOT NULL,
    employee_id TEXT UNIQUE NOT NULL,
    join_date DATE NOT NULL,
    qualification TEXT NOT NULL,
    subjects TEXT[] NOT NULL,
    salary_info JSONB NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- ============================================
-- CLASSES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.classes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    section TEXT NOT NULL,
    teacher_id UUID REFERENCES public.teachers(id) ON DELETE SET NULL,
    academic_year TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    UNIQUE(name, section, academic_year)
);

-- ============================================
-- STUDENTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.students (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE NOT NULL,
    admission_number TEXT UNIQUE NOT NULL,
    admission_date DATE NOT NULL,
    class_id UUID REFERENCES public.classes(id) ON DELETE SET NULL,
    guardian_info JSONB NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'graduated', 'transferred')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- ============================================
-- GRADES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.grades (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id UUID REFERENCES public.students(id) ON DELETE CASCADE NOT NULL,
    class_id UUID REFERENCES public.classes(id) ON DELETE CASCADE NOT NULL,
    subject TEXT NOT NULL,
    marks DECIMAL(5,2) NOT NULL,
    grade TEXT NOT NULL,
    term TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    remarks TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- ============================================
-- ATTENDANCE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.attendance (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late', 'excused')),
    marked_by UUID REFERENCES auth.users(id) ON DELETE SET NULL NOT NULL,
    remarks TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    UNIQUE(user_id, date)
);

-- ============================================
-- STATIONERY ITEMS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.stationery_items (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    unit TEXT NOT NULL,
    reorder_level INTEGER NOT NULL DEFAULT 10,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- ============================================
-- STATIONERY DISTRIBUTIONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.stationery_distributions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id UUID REFERENCES public.students(id) ON DELETE CASCADE NOT NULL,
    item_id UUID REFERENCES public.stationery_items(id) ON DELETE CASCADE NOT NULL,
    quantity INTEGER NOT NULL,
    distributed_date DATE NOT NULL,
    distributed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- ============================================
-- SALARY RECORDS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.salary_records (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    teacher_id UUID REFERENCES public.teachers(id) ON DELETE CASCADE NOT NULL,
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    year INTEGER NOT NULL,
    basic_salary DECIMAL(10,2) NOT NULL,
    deductions DECIMAL(10,2) DEFAULT 0.00,
    bonuses DECIMAL(10,2) DEFAULT 0.00,
    net_salary DECIMAL(10,2) NOT NULL,
    paid_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    UNIQUE(teacher_id, month, year)
);

-- ============================================
-- EXPENSES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.expenses (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    category TEXT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    description TEXT NOT NULL,
    date DATE NOT NULL,
    recorded_by UUID REFERENCES auth.users(id) ON DELETE SET NULL NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- ============================================
-- DONATIONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.donations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    donor_name TEXT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    date DATE NOT NULL,
    purpose TEXT,
    receipt_number TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- ============================================
-- INDEXES FOR BETTER PERFORMANCE
-- ============================================

-- Profiles
CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON public.profiles(user_id);

-- Students
CREATE INDEX IF NOT EXISTS idx_students_user_id ON public.students(user_id);
CREATE INDEX IF NOT EXISTS idx_students_class_id ON public.students(class_id);
CREATE INDEX IF NOT EXISTS idx_students_status ON public.students(status);
CREATE INDEX IF NOT EXISTS idx_students_admission_number ON public.students(admission_number);

-- Teachers
CREATE INDEX IF NOT EXISTS idx_teachers_user_id ON public.teachers(user_id);
CREATE INDEX IF NOT EXISTS idx_teachers_employee_id ON public.teachers(employee_id);
CREATE INDEX IF NOT EXISTS idx_teachers_status ON public.teachers(status);

-- Classes
CREATE INDEX IF NOT EXISTS idx_classes_teacher_id ON public.classes(teacher_id);
CREATE INDEX IF NOT EXISTS idx_classes_academic_year ON public.classes(academic_year);

-- Grades
CREATE INDEX IF NOT EXISTS idx_grades_student_id ON public.grades(student_id);
CREATE INDEX IF NOT EXISTS idx_grades_class_id ON public.grades(class_id);
CREATE INDEX IF NOT EXISTS idx_grades_academic_year ON public.grades(academic_year);
CREATE INDEX IF NOT EXISTS idx_grades_term ON public.grades(term);

-- Attendance
CREATE INDEX IF NOT EXISTS idx_attendance_user_id ON public.attendance(user_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON public.attendance(date);
CREATE INDEX IF NOT EXISTS idx_attendance_status ON public.attendance(status);

-- Stationery
CREATE INDEX IF NOT EXISTS idx_stationery_category ON public.stationery_items(category);
CREATE INDEX IF NOT EXISTS idx_distributions_student_id ON public.stationery_distributions(student_id);
CREATE INDEX IF NOT EXISTS idx_distributions_item_id ON public.stationery_distributions(item_id);
CREATE INDEX IF NOT EXISTS idx_distributions_date ON public.stationery_distributions(distributed_date);

-- Salary
CREATE INDEX IF NOT EXISTS idx_salary_teacher_id ON public.salary_records(teacher_id);
CREATE INDEX IF NOT EXISTS idx_salary_year_month ON public.salary_records(year, month);

-- Finance
CREATE INDEX IF NOT EXISTS idx_expenses_category ON public.expenses(category);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON public.expenses(date);
CREATE INDEX IF NOT EXISTS idx_donations_date ON public.donations(date);

-- ============================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================

-- Enable RLS on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.students ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teachers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.grades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stationery_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stationery_distributions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salary_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.donations ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can view and update their own profile, admins can see all
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert profiles" ON public.profiles
    FOR INSERT WITH CHECK (auth.jwt()->>'role' = 'service_role');

CREATE POLICY "Service role can do anything on profiles" ON public.profiles
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Students: Students see their own data, teachers/admins see all
CREATE POLICY "Students can view own data" ON public.students
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert students" ON public.students
    FOR INSERT WITH CHECK (auth.jwt()->>'role' = 'service_role');

CREATE POLICY "Service role can do anything on students" ON public.students
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Teachers: Teachers see their own data, admins see all
CREATE POLICY "Teachers can view own data" ON public.teachers
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert teachers" ON public.teachers
    FOR INSERT WITH CHECK (auth.jwt()->>'role' = 'service_role');

CREATE POLICY "Service role can do anything on teachers" ON public.teachers
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Classes: All authenticated users can view classes
CREATE POLICY "Authenticated users can view classes" ON public.classes
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can do anything on classes" ON public.classes
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Grades: Students see their own grades, teachers/admins see relevant grades
CREATE POLICY "Students can view own grades" ON public.grades
    FOR SELECT USING (
        student_id IN (SELECT id FROM public.students WHERE user_id = auth.uid())
    );

-- Teachers can view grades for their assigned classes
CREATE POLICY "Teachers can view class grades" ON public.grades
    FOR SELECT USING (
        class_id IN (
            SELECT id FROM public.classes 
            WHERE teacher_id IN (
                SELECT id FROM public.teachers WHERE user_id = auth.uid()
            )
        )
    );

-- Admin/Principal can manage all grades
CREATE POLICY "Admin can manage grades" ON public.grades
    FOR ALL USING (
        (auth.jwt()->>'role') IN ('admin', 'principal', 'service_role')
    );

-- Teachers can insert grades for their assigned classes
CREATE POLICY "Teachers can insert class grades" ON public.grades
    FOR INSERT WITH CHECK (
        class_id IN (
            SELECT id FROM public.classes 
            WHERE teacher_id IN (
                SELECT id FROM public.teachers WHERE user_id = auth.uid()
            )
        )
    );

-- Teachers can update grades for their assigned classes
CREATE POLICY "Teachers can update class grades" ON public.grades
    FOR UPDATE USING (
        class_id IN (
            SELECT id FROM public.classes 
            WHERE teacher_id IN (
                SELECT id FROM public.teachers WHERE user_id = auth.uid()
            )
        )
    );

CREATE POLICY "Service role can do anything on grades" ON public.grades
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Attendance: Users see their own attendance, teachers/admins see all
CREATE POLICY "Users can view own attendance" ON public.attendance
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Service role can do anything on attendance" ON public.attendance
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Stationery Items: All authenticated users can view
CREATE POLICY "Authenticated users can view stationery items" ON public.stationery_items
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can do anything on stationery items" ON public.stationery_items
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Stationery Distributions: Students see their own, staff see all
CREATE POLICY "Students can view own distributions" ON public.stationery_distributions
    FOR SELECT USING (
        student_id IN (SELECT id FROM public.students WHERE user_id = auth.uid())
    );

CREATE POLICY "Service role can do anything on distributions" ON public.stationery_distributions
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Salary, Expenses, Donations: Admin/Principal only
CREATE POLICY "Service role can do anything on salary" ON public.salary_records
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

CREATE POLICY "Service role can do anything on expenses" ON public.expenses
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

CREATE POLICY "Service role can do anything on donations" ON public.donations
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- ============================================
-- UPDATED_AT TRIGGER FUNCTION
-- ============================================

CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.students
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.teachers
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.classes
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.grades
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.stationery_items
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.salary_records
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.expenses
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.donations
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();


