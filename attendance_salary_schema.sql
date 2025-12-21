-- ==================== ATTENDANCE-LINKED SALARY MANAGEMENT SCHEMA ====================
-- This schema manages biometric attendance data and automatic salary calculations

-- School Timing Configuration
CREATE TABLE IF NOT EXISTS public.school_timings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timing_name TEXT NOT NULL DEFAULT 'Default',
    arrival_time TIME NOT NULL DEFAULT '09:00:00',
    departure_time TIME NOT NULL DEFAULT '15:00:00',
    grace_period_minutes INTEGER DEFAULT 5,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Attendance Deduction Rules
CREATE TABLE IF NOT EXISTS public.attendance_rules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    rule_name TEXT NOT NULL,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('late_coming', 'half_day', 'absent', 'early_departure')),
    condition_description TEXT NOT NULL,
    deduction_type TEXT NOT NULL CHECK (deduction_type IN ('percentage', 'fixed_amount', 'full_day', 'half_day')),
    deduction_value NUMERIC NOT NULL DEFAULT 0,
    grace_minutes INTEGER DEFAULT 0,
    max_late_count INTEGER DEFAULT 3, -- After this many late comings, apply deduction
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Biometric Attendance Records
CREATE TABLE IF NOT EXISTS public.biometric_attendance (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    teacher_id UUID NOT NULL REFERENCES public.teachers(id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    check_in_time TIME,
    check_out_time TIME,
    total_hours NUMERIC DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'half_day', 'late', 'early_departure')),
    late_minutes INTEGER DEFAULT 0,
    early_departure_minutes INTEGER DEFAULT 0,
    deduction_amount NUMERIC DEFAULT 0,
    deduction_reason TEXT,
    is_manual_override BOOLEAN DEFAULT false,
    override_reason TEXT,
    uploaded_file_id UUID, -- Reference to uploaded CSV file
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    UNIQUE(teacher_id, attendance_date)
);

-- CSV Upload History
CREATE TABLE IF NOT EXISTS public.csv_upload_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    file_name TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    records_processed INTEGER DEFAULT 0,
    records_successful INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    upload_status TEXT NOT NULL CHECK (upload_status IN ('processing', 'completed', 'failed', 'partial')),
    error_log TEXT,
    uploaded_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Monthly Salary Calculations
CREATE TABLE IF NOT EXISTS public.monthly_salary_calculations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    teacher_id UUID NOT NULL REFERENCES public.teachers(id) ON DELETE CASCADE,
    calculation_month INTEGER NOT NULL CHECK (calculation_month >= 1 AND calculation_month <= 12),
    calculation_year INTEGER NOT NULL,
    basic_salary NUMERIC NOT NULL,
    per_day_salary NUMERIC NOT NULL,
    total_working_days INTEGER NOT NULL,
    present_days INTEGER NOT NULL DEFAULT 0,
    absent_days INTEGER NOT NULL DEFAULT 0,
    half_days INTEGER NOT NULL DEFAULT 0,
    late_days INTEGER NOT NULL DEFAULT 0,
    total_deductions NUMERIC NOT NULL DEFAULT 0,
    net_salary NUMERIC NOT NULL,
    calculation_details JSONB, -- Store detailed breakdown
    is_approved BOOLEAN DEFAULT false,
    approved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    UNIQUE(teacher_id, calculation_month, calculation_year)
);

-- Teacher Salary Configuration
CREATE TABLE IF NOT EXISTS public.teacher_salary_config (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    teacher_id UUID NOT NULL REFERENCES public.teachers(id) ON DELETE CASCADE,
    basic_monthly_salary NUMERIC NOT NULL,
    per_day_salary NUMERIC NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Insert default school timings
INSERT INTO public.school_timings (timing_name, arrival_time, departure_time, grace_period_minutes) VALUES
    ('Default School Hours', '09:00:00', '15:00:00', 5)
ON CONFLICT DO NOTHING;

-- Insert default attendance rules
INSERT INTO public.attendance_rules (rule_name, rule_type, condition_description, deduction_type, deduction_value, grace_minutes, max_late_count) VALUES
    ('Late Coming Rule', 'late_coming', 'Arrival after grace period', 'percentage', 0.5, 5, 3),
    ('Half Day Rule', 'half_day', 'Less than 4 hours worked', 'half_day', 0, 0, 0),
    ('Absent Rule', 'absent', 'No check-in recorded', 'full_day', 0, 0, 0),
    ('Early Departure Rule', 'early_departure', 'Departure before scheduled time', 'percentage', 0.25, 0, 0)
ON CONFLICT DO NOTHING;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_biometric_attendance_teacher_date ON public.biometric_attendance(teacher_id, attendance_date);
CREATE INDEX IF NOT EXISTS idx_biometric_attendance_date ON public.biometric_attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_biometric_attendance_status ON public.biometric_attendance(status);
CREATE INDEX IF NOT EXISTS idx_monthly_salary_teacher_month_year ON public.monthly_salary_calculations(teacher_id, calculation_month, calculation_year);
CREATE INDEX IF NOT EXISTS idx_csv_upload_history_date ON public.csv_upload_history(upload_date);
CREATE INDEX IF NOT EXISTS idx_teacher_salary_config_teacher ON public.teacher_salary_config(teacher_id);
CREATE INDEX IF NOT EXISTS idx_teacher_salary_config_active ON public.teacher_salary_config(is_active);

-- Enable RLS
ALTER TABLE public.school_timings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biometric_attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.csv_upload_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.monthly_salary_calculations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teacher_salary_config ENABLE ROW LEVEL SECURITY;

-- RLS Policies for school_timings
CREATE POLICY "Authenticated users can view school timings" ON public.school_timings
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can manage school timings" ON public.school_timings
    FOR ALL USING (auth.role() = 'service_role');

-- RLS Policies for attendance_rules
CREATE POLICY "Authenticated users can view attendance rules" ON public.attendance_rules
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can manage attendance rules" ON public.attendance_rules
    FOR ALL USING (auth.role() = 'service_role');

-- RLS Policies for biometric_attendance
CREATE POLICY "Authenticated users can view biometric attendance" ON public.biometric_attendance
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can manage biometric attendance" ON public.biometric_attendance
    FOR ALL USING (auth.role() = 'service_role');

-- RLS Policies for csv_upload_history
CREATE POLICY "Authenticated users can view upload history" ON public.csv_upload_history
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can manage upload history" ON public.csv_upload_history
    FOR ALL USING (auth.role() = 'service_role');

-- RLS Policies for monthly_salary_calculations
CREATE POLICY "Authenticated users can view salary calculations" ON public.monthly_salary_calculations
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can manage salary calculations" ON public.monthly_salary_calculations
    FOR ALL USING (auth.role() = 'service_role');

-- RLS Policies for teacher_salary_config
CREATE POLICY "Authenticated users can view salary config" ON public.teacher_salary_config
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can manage salary config" ON public.teacher_salary_config
    FOR ALL USING (auth.role() = 'service_role');

-- Create triggers for updated_at
CREATE TRIGGER update_school_timings_updated_at BEFORE UPDATE ON public.school_timings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_attendance_rules_updated_at BEFORE UPDATE ON public.attendance_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_biometric_attendance_updated_at BEFORE UPDATE ON public.biometric_attendance
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_monthly_salary_calculations_updated_at BEFORE UPDATE ON public.monthly_salary_calculations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_teacher_salary_config_updated_at BEFORE UPDATE ON public.teacher_salary_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();










