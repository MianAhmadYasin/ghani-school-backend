-- =====================================================
-- COMPREHENSIVE EXAM MANAGEMENT SYSTEM SCHEMA
-- Supports approval workflow, bulk uploads, and flexible exam types
-- Compatible with existing database structure
-- =====================================================

-- ============================================
-- CHECK FOR REQUIRED FUNCTION
-- ============================================
-- Create handle_updated_at function if it doesn't exist
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- EXAMS TABLE
-- Generic exam management for different exam types
-- ============================================
CREATE TABLE IF NOT EXISTS public.exams (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    exam_name TEXT NOT NULL,
    exam_type TEXT NOT NULL CHECK (exam_type IN ('term_exam', 'mid_term', 'final', 'quiz', 'assignment', 'annual', 'custom')),
    term TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    class_id UUID REFERENCES public.classes(id) ON DELETE CASCADE NOT NULL,
    subject TEXT NOT NULL,
    total_marks DECIMAL(6,2) NOT NULL DEFAULT 100.00,
    passing_marks DECIMAL(6,2) NOT NULL DEFAULT 50.00,
    exam_date DATE,
    duration_minutes INTEGER,
    instructions TEXT,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL NOT NULL,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'completed', 'archived')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    UNIQUE(exam_name, class_id, subject, term, academic_year)
);

-- ============================================
-- ENHANCE PAPERS TABLE
-- Add approval workflow fields (papers table already exists)
-- ============================================
DO $$
BEGIN
    -- Verify/Create foreign key constraint for uploaded_by if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_schema = 'public' 
        AND table_name = 'papers' 
        AND constraint_name = 'papers_uploaded_by_fkey'
    ) THEN
        ALTER TABLE public.papers 
        ADD CONSTRAINT papers_uploaded_by_fkey 
        FOREIGN KEY (uploaded_by) REFERENCES auth.users(id) ON DELETE SET NULL;
    END IF;

    -- Add approval_status column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'papers' 
        AND column_name = 'approval_status'
    ) THEN
        ALTER TABLE public.papers 
        ADD COLUMN approval_status TEXT DEFAULT 'draft' 
        CHECK (approval_status IN ('draft', 'pending', 'approved', 'rejected'));
    END IF;

    -- Add exam_id column if it doesn't exist (nullable initially due to circular dependency)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'papers' 
        AND column_name = 'exam_id'
    ) THEN
        ALTER TABLE public.papers 
        ADD COLUMN exam_id UUID REFERENCES public.exams(id) ON DELETE SET NULL;
    END IF;

    -- Add submitted_for_approval_at column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'papers' 
        AND column_name = 'submitted_for_approval_at'
    ) THEN
        ALTER TABLE public.papers 
        ADD COLUMN submitted_for_approval_at TIMESTAMP WITH TIME ZONE;
    END IF;

    -- Add approved_by column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'papers' 
        AND column_name = 'approved_by'
    ) THEN
        ALTER TABLE public.papers 
        ADD COLUMN approved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL;
    END IF;

    -- Add approved_at column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'papers' 
        AND column_name = 'approved_at'
    ) THEN
        ALTER TABLE public.papers 
        ADD COLUMN approved_at TIMESTAMP WITH TIME ZONE;
    END IF;

    -- Add rejection_reason column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'papers' 
        AND column_name = 'rejection_reason'
    ) THEN
        ALTER TABLE public.papers 
        ADD COLUMN rejection_reason TEXT;
    END IF;

    -- Add rejected_by column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'papers' 
        AND column_name = 'rejected_by'
    ) THEN
        ALTER TABLE public.papers 
        ADD COLUMN rejected_by UUID REFERENCES auth.users(id) ON DELETE SET NULL;
    END IF;
END $$;

-- ============================================
-- EXAM RESULTS TABLE
-- Store marks linked to specific exams
-- ============================================
CREATE TABLE IF NOT EXISTS public.exam_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    exam_id UUID REFERENCES public.exams(id) ON DELETE CASCADE NOT NULL,
    student_id UUID REFERENCES public.students(id) ON DELETE CASCADE NOT NULL,
    marks_obtained DECIMAL(6,2) NOT NULL CHECK (marks_obtained >= 0),
    total_marks DECIMAL(6,2) NOT NULL CHECK (total_marks > 0),
    grade TEXT,
    percentage DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_marks > 0 THEN ROUND((marks_obtained / total_marks * 100)::numeric, 2)
            ELSE 0
        END
    ) STORED,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'absent', 'absent_with_excuse', 'incomplete')),
    remarks TEXT,
    uploaded_by UUID REFERENCES auth.users(id) ON DELETE SET NULL NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    UNIQUE(exam_id, student_id)
);

-- ============================================
-- EXAM SETTINGS TABLE
-- School-specific exam configuration
-- ============================================
CREATE TABLE IF NOT EXISTS public.exam_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_name TEXT NOT NULL DEFAULT 'Default School',
    terms_config JSONB NOT NULL DEFAULT '["First Term", "Second Term", "Third Term", "Final"]'::jsonb,
    exam_types JSONB NOT NULL DEFAULT '["term_exam", "mid_term", "final", "quiz", "assignment", "annual"]'::jsonb,
    default_grading_criteria JSONB,
    bulk_upload_enabled BOOLEAN DEFAULT true,
    approval_required BOOLEAN DEFAULT true,
    auto_calculate_grade BOOLEAN DEFAULT true,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- Insert default exam settings if not exists
-- Use a single row approach with idempotent insert
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.exam_settings LIMIT 1) THEN
        INSERT INTO public.exam_settings (school_name, terms_config, exam_types)
        VALUES (
            'Default School',
            '["First Term", "Second Term", "Third Term", "Final"]'::jsonb,
            '["term_exam", "mid_term", "final", "quiz", "assignment", "annual"]'::jsonb
        );
    END IF;
END $$;

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================
CREATE INDEX IF NOT EXISTS idx_exams_class_id ON public.exams(class_id);
CREATE INDEX IF NOT EXISTS idx_exams_subject ON public.exams(subject);
CREATE INDEX IF NOT EXISTS idx_exams_term ON public.exams(term);
CREATE INDEX IF NOT EXISTS idx_exams_academic_year ON public.exams(academic_year);
CREATE INDEX IF NOT EXISTS idx_exams_created_by ON public.exams(created_by);
CREATE INDEX IF NOT EXISTS idx_exams_status ON public.exams(status);
CREATE INDEX IF NOT EXISTS idx_exams_exam_type ON public.exams(exam_type);

CREATE INDEX IF NOT EXISTS idx_papers_exam_id ON public.papers(exam_id);
CREATE INDEX IF NOT EXISTS idx_papers_approval_status ON public.papers(approval_status);
CREATE INDEX IF NOT EXISTS idx_papers_submitted_at ON public.papers(submitted_for_approval_at);

CREATE INDEX IF NOT EXISTS idx_exam_results_exam_id ON public.exam_results(exam_id);
CREATE INDEX IF NOT EXISTS idx_exam_results_student_id ON public.exam_results(student_id);
CREATE INDEX IF NOT EXISTS idx_exam_results_uploaded_by ON public.exam_results(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_exam_results_status ON public.exam_results(status);

-- ============================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================

-- Enable RLS on new tables
ALTER TABLE public.exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exam_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exam_settings ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist to avoid conflicts
DROP POLICY IF EXISTS "Teachers can view exams for their classes" ON public.exams;
DROP POLICY IF EXISTS "Teachers can create exams for their classes" ON public.exams;
DROP POLICY IF EXISTS "Teachers can update their exams" ON public.exams;
DROP POLICY IF EXISTS "Admin can manage all exams" ON public.exams;
DROP POLICY IF EXISTS "Teachers can view results for their exams" ON public.exam_results;
DROP POLICY IF EXISTS "Students can view own results" ON public.exam_results;
DROP POLICY IF EXISTS "Teachers can create results for their exams" ON public.exam_results;
DROP POLICY IF EXISTS "Teachers can update results for their exams" ON public.exam_results;
DROP POLICY IF EXISTS "Admin can manage all results" ON public.exam_results;
DROP POLICY IF EXISTS "Authenticated users can view exam settings" ON public.exam_settings;
DROP POLICY IF EXISTS "Admin can manage exam settings" ON public.exam_settings;

-- Exams: Teachers can manage exams for their classes, Admins can manage all
CREATE POLICY "Teachers can view exams for their classes" ON public.exams
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.classes c
            INNER JOIN public.teachers t ON c.teacher_id = t.id
            WHERE c.id = exams.class_id AND t.user_id = auth.uid()
        )
        OR (auth.jwt()->>'role') IN ('admin', 'principal', 'service_role')
    );

CREATE POLICY "Teachers can create exams for their classes" ON public.exams
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.classes c
            INNER JOIN public.teachers t ON c.teacher_id = t.id
            WHERE c.id = exams.class_id AND t.user_id = auth.uid()
        )
        OR (auth.jwt()->>'role') IN ('admin', 'principal', 'service_role')
    );

CREATE POLICY "Teachers can update their exams" ON public.exams
    FOR UPDATE USING (
        (created_by = auth.uid() AND status = 'draft')
        OR (auth.jwt()->>'role') IN ('admin', 'principal', 'service_role')
    );

CREATE POLICY "Admin can manage all exams" ON public.exams
    FOR ALL USING ((auth.jwt()->>'role') IN ('admin', 'principal', 'service_role'));

-- Exam Results: Teachers can view/upload results for their exams, Students can view their own
CREATE POLICY "Teachers can view results for their exams" ON public.exam_results
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.exams e
            WHERE e.id = exam_results.exam_id 
            AND (e.created_by = auth.uid() OR EXISTS (
                SELECT 1 FROM public.classes c
                INNER JOIN public.teachers t ON c.teacher_id = t.id
                WHERE c.id = e.class_id AND t.user_id = auth.uid()
            ))
        )
        OR (auth.jwt()->>'role') IN ('admin', 'principal', 'service_role')
    );

CREATE POLICY "Students can view own results" ON public.exam_results
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.students s
            WHERE s.id = exam_results.student_id AND s.user_id = auth.uid()
        )
    );

CREATE POLICY "Teachers can create results for their exams" ON public.exam_results
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.exams e
            WHERE e.id = exam_results.exam_id 
            AND (e.created_by = auth.uid() OR EXISTS (
                SELECT 1 FROM public.classes c
                INNER JOIN public.teachers t ON c.teacher_id = t.id
                WHERE c.id = e.class_id AND t.user_id = auth.uid()
            ))
        )
        OR (auth.jwt()->>'role') IN ('admin', 'principal', 'service_role')
    );

CREATE POLICY "Teachers can update results for their exams" ON public.exam_results
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.exams e
            WHERE e.id = exam_results.exam_id 
            AND (e.created_by = auth.uid() OR EXISTS (
                SELECT 1 FROM public.classes c
                INNER JOIN public.teachers t ON c.teacher_id = t.id
                WHERE c.id = e.class_id AND t.user_id = auth.uid()
            ))
        )
        OR (auth.jwt()->>'role') IN ('admin', 'principal', 'service_role')
    );

CREATE POLICY "Admin can manage all results" ON public.exam_results
    FOR ALL USING ((auth.jwt()->>'role') IN ('admin', 'principal', 'service_role'));

-- Exam Settings: All authenticated users can view, only admin can modify
CREATE POLICY "Authenticated users can view exam settings" ON public.exam_settings
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Admin can manage exam settings" ON public.exam_settings
    FOR ALL USING ((auth.jwt()->>'role') IN ('admin', 'principal', 'service_role'));

-- Update RLS for papers table approval workflow
-- Note: papers.class_id is VARCHAR, classes.id is UUID, so we need to convert
DROP POLICY IF EXISTS "Teachers can view papers for their classes" ON public.papers;
DROP POLICY IF EXISTS "Teachers can submit papers for approval" ON public.papers;
DROP POLICY IF EXISTS "Principal/Admin can approve papers" ON public.papers;
DROP POLICY IF EXISTS "Teachers can view papers" ON public.papers;

-- Handle papers table where class_id is VARCHAR (stores class name or UUID as text)
CREATE POLICY "Teachers can view papers for their classes" ON public.papers
    FOR SELECT USING (
        -- Try to match by UUID if class_id is a valid UUID
        EXISTS (
            SELECT 1 FROM public.classes c
            INNER JOIN public.teachers t ON c.teacher_id = t.id
            WHERE (c.id::text = papers.class_id OR c.name || '-' || c.section = papers.class_id)
            AND t.user_id = auth.uid()
        )
        OR uploaded_by = auth.uid()
        OR (auth.jwt()->>'role') IN ('admin', 'principal', 'service_role')
    );

CREATE POLICY "Teachers can submit papers for approval" ON public.papers
    FOR INSERT WITH CHECK (
        uploaded_by = auth.uid()
        OR (auth.jwt()->>'role') IN ('admin', 'principal', 'service_role')
    );

CREATE POLICY "Principal/Admin can approve papers" ON public.papers
    FOR UPDATE USING (
        (auth.jwt()->>'role') IN ('admin', 'principal', 'service_role')
        OR (uploaded_by = auth.uid() AND COALESCE(approval_status, 'draft') = 'draft')
    );

-- ============================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================
DROP TRIGGER IF EXISTS set_updated_at_exams ON public.exams;
CREATE TRIGGER set_updated_at_exams BEFORE UPDATE ON public.exams
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at_exam_results ON public.exam_results;
CREATE TRIGGER set_updated_at_exam_results BEFORE UPDATE ON public.exam_results
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at_exam_settings ON public.exam_settings;
CREATE TRIGGER set_updated_at_exam_settings BEFORE UPDATE ON public.exam_settings
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ============================================
-- VERIFICATION AND CLEANUP
-- ============================================
-- Set default approval_status for existing papers (only if column exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'papers' 
        AND column_name = 'approval_status'
    ) THEN
        UPDATE public.papers 
        SET approval_status = 'draft' 
        WHERE approval_status IS NULL;
    END IF;
END $$;

-- Comments for documentation
COMMENT ON TABLE public.exams IS 'Generic exam management table supporting multiple exam types';
COMMENT ON TABLE public.exam_results IS 'Student exam results linked to specific exams';
COMMENT ON TABLE public.exam_settings IS 'School-specific exam configuration and settings';
COMMENT ON COLUMN public.papers.approval_status IS 'Approval workflow status: draft, pending, approved, rejected';
COMMENT ON COLUMN public.papers.exam_id IS 'Link to exams table (nullable, set after exam creation)';
