-- schema_v2.sql
-- Complete Supabase Schema with strict RLS and new features

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Create Token Blacklist
CREATE TABLE IF NOT EXISTS public.token_blacklist (
    id SERIAL PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Update Existing Tables

-- Users Table
-- Ensure roles are restricted implicitly in RLS or at app layer
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS token_version INT DEFAULT 1;

-- Hospitals Table
-- 'status' enum logically handled via text here: PENDING_PAYMENT, PENDING_VERIFICATION, ACTIVE
ALTER TABLE public.hospitals ADD COLUMN IF NOT EXISTS linked_account_id VARCHAR(255);
ALTER TABLE public.hospitals ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'PENDING_PAYMENT';

-- Doctors Table
ALTER TABLE public.doctors ADD COLUMN IF NOT EXISTS token_version INT DEFAULT 1;

-- Payments Table
ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255) UNIQUE;
ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS split_transfer_id VARCHAR(255);

-- Create Guest Appointments Table
CREATE TABLE IF NOT EXISTS public.guest_appointments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    mobile VARCHAR(20) NOT NULL,
    age INT,
    gender VARCHAR(20),
    preferred_date DATE NOT NULL,
    hospital_id INT NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    doctor_id INT REFERENCES public.doctors(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'pending',
    ip_address VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Enable Row Level Security (RLS) on all tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hospitals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.guest_appointments ENABLE ROW LEVEL SECURITY;

-- 5. Drop old insecure policies (if any exist using the old USING (true) schema)
-- Note: Replace DO with actual drops based on your environment
DO $$ 
DECLARE
    row RECORD;
BEGIN
    FOR row IN SELECT policyname, tablename FROM pg_policies WHERE schemaname = 'public'
    LOOP
        EXECUTE 'DROP POLICY IF EXISTS ' || quote_ident(row.policyname) || ' ON ' || quote_ident(row.tablename);
    END LOOP;
END $$;

-- 6. Create Strict RLS Policies

-- USERS TABLE
CREATE POLICY "Users can view their own profile" 
ON public.users FOR SELECT 
USING (id::text = auth.uid() OR current_setting('request.jwt.claims', true)::json->>'role' = 'admin');

CREATE POLICY "Users can update their own profile" 
ON public.users FOR UPDATE 
USING (id::text = auth.uid());

CREATE POLICY "Admins can manage all users" 
ON public.users FOR ALL 
USING (current_setting('request.jwt.claims', true)::json->>'role' = 'admin');

-- HOSPITALS TABLE
CREATE POLICY "Public can view active hospitals" 
ON public.hospitals FOR SELECT 
USING (status = 'ACTIVE' OR id::text = current_setting('request.jwt.claims', true)::json->>'hospital_id' OR current_setting('request.jwt.claims', true)::json->>'role' = 'admin');

CREATE POLICY "Hospital owners can update their hospital" 
ON public.hospitals FOR UPDATE 
USING (id::text = current_setting('request.jwt.claims', true)::json->>'hospital_id');

-- DOCTORS TABLE
CREATE POLICY "Public can view active doctors" 
ON public.doctors FOR SELECT 
USING (is_active = true OR user_id::text = auth.uid() OR current_setting('request.jwt.claims', true)::json->>'role' = 'admin' OR hospital_id::text = current_setting('request.jwt.claims', true)::json->>'hospital_id');

CREATE POLICY "Doctors can update their own profile" 
ON public.doctors FOR UPDATE 
USING (user_id::text = auth.uid());

-- APPOINTMENTS
CREATE POLICY "Patients can view their own appointments" 
ON public.appointments FOR SELECT 
USING (user_id::text = auth.uid());

CREATE POLICY "Doctors can view their hospital's appointments" 
ON public.appointments FOR SELECT 
USING (hospital_id::text = current_setting('request.jwt.claims', true)::json->>'hospital_id');

CREATE POLICY "Patients can create appointments" 
ON public.appointments FOR INSERT 
WITH CHECK (user_id::text = auth.uid());

-- PAYMENTS
CREATE POLICY "Users can view their own payments" 
ON public.payments FOR SELECT 
USING (user_id::text = auth.uid());

-- Only admins/service role can insert/update payments based on webhooks
CREATE POLICY "Admin/Service can manage payments" 
ON public.payments FOR ALL 
USING (current_setting('request.jwt.claims', true)::json->>'role' = 'admin');

-- GUEST APPOINTMENTS (Service Role / Public insert)
CREATE POLICY "Public can insert guest appointments"
ON public.guest_appointments FOR INSERT
WITH CHECK (true); -- Service layer should rate limit this

CREATE POLICY "Hospitals can view guest appointments"
ON public.guest_appointments FOR SELECT
USING (hospital_id::text = current_setting('request.jwt.claims', true)::json->>'hospital_id');
