-- =====================================================
-- EVENTS TABLE - Ghani Grammar School
-- =====================================================
-- Execute this in Supabase SQL Editor ONLY if events table doesn't exist
-- This adds the events table to your existing database
-- =====================================================

-- Create events table
CREATE TABLE IF NOT EXISTS public.events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  description TEXT,
  date DATE NOT NULL,
  time TIME,
  location TEXT,
  type TEXT NOT NULL CHECK (type IN ('academic', 'sports', 'cultural', 'meeting', 'other')),
  status TEXT NOT NULL DEFAULT 'upcoming' CHECK (status IN ('upcoming', 'ongoing', 'completed', 'cancelled')),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_events_date ON public.events(date DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON public.events(type);
CREATE INDEX IF NOT EXISTS idx_events_status ON public.events(status);
CREATE INDEX IF NOT EXISTS idx_events_created_by ON public.events(created_by);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON public.events(created_at DESC);

-- Create update trigger
CREATE OR REPLACE FUNCTION update_events_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_events_timestamp ON public.events;
CREATE TRIGGER trigger_update_events_timestamp
    BEFORE UPDATE ON public.events
    FOR EACH ROW
    EXECUTE FUNCTION update_events_updated_at();

-- Enable Row Level Security
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Everyone can view events
DROP POLICY IF EXISTS "events_select_policy" ON public.events;
CREATE POLICY "events_select_policy" 
    ON public.events
    FOR SELECT
    TO authenticated
    USING (true);

-- Only admins and principals can create events
DROP POLICY IF EXISTS "events_insert_policy" ON public.events;
CREATE POLICY "events_insert_policy"
    ON public.events
    FOR INSERT
    TO authenticated
    WITH CHECK ((auth.jwt() ->> 'role') IN ('admin', 'principal'));

-- Only admins and principals can update events
DROP POLICY IF EXISTS "events_update_policy" ON public.events;
CREATE POLICY "events_update_policy"
    ON public.events
    FOR UPDATE
    TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('admin', 'principal'))
    WITH CHECK ((auth.jwt() ->> 'role') IN ('admin', 'principal'));

-- Only admins and principals can delete events
DROP POLICY IF EXISTS "events_delete_policy" ON public.events;
CREATE POLICY "events_delete_policy"
    ON public.events
    FOR DELETE
    TO authenticated
    USING ((auth.jwt() ->> 'role') IN ('admin', 'principal'));

-- Add comment
COMMENT ON TABLE public.events IS 'School events and activities management';

-- Verify table created
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'events') THEN
        RAISE NOTICE '✅ events table created successfully';
    END IF;
END $$;

