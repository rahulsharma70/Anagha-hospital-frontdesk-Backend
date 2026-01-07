-- ============================================
-- Hospital Booking System - Complete Database Schema
-- Supabase PostgreSQL Schema
-- This script uses ALTER TABLE to update existing tables
-- Run this entire file in Supabase SQL Editor
-- ============================================

-- ============================================
-- 1. CORE TABLES - Create or Alter
-- ============================================

-- Create hospitals table if not exists
CREATE TABLE IF NOT EXISTS hospitals (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  mobile TEXT NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alter hospitals table to add all columns
DO $$ 
BEGIN
  -- Address fields
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='address_line1') THEN
    ALTER TABLE hospitals ADD COLUMN address_line1 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='address_line2') THEN
    ALTER TABLE hospitals ADD COLUMN address_line2 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='address_line3') THEN
    ALTER TABLE hospitals ADD COLUMN address_line3 TEXT;
  END IF;
  
  -- Location fields
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='city') THEN
    ALTER TABLE hospitals ADD COLUMN city TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='state') THEN
    ALTER TABLE hospitals ADD COLUMN state TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='pincode') THEN
    ALTER TABLE hospitals ADD COLUMN pincode TEXT;
  END IF;
  
  -- Registration fields
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='registration_date') THEN
    ALTER TABLE hospitals ADD COLUMN registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='approved_date') THEN
    ALTER TABLE hospitals ADD COLUMN approved_date TIMESTAMP;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='plan') THEN
    ALTER TABLE hospitals ADD COLUMN plan TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='expiry_date') THEN
    ALTER TABLE hospitals ADD COLUMN expiry_date DATE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='is_active') THEN
    ALTER TABLE hospitals ADD COLUMN is_active BOOLEAN DEFAULT true;
  END IF;
  
  -- UPI Payment IDs
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='upi_id') THEN
    ALTER TABLE hospitals ADD COLUMN upi_id TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='gpay_upi_id') THEN
    ALTER TABLE hospitals ADD COLUMN gpay_upi_id TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='phonepay_upi_id') THEN
    ALTER TABLE hospitals ADD COLUMN phonepay_upi_id TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='paytm_upi_id') THEN
    ALTER TABLE hospitals ADD COLUMN paytm_upi_id TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='bhim_upi_id') THEN
    ALTER TABLE hospitals ADD COLUMN bhim_upi_id TEXT;
  END IF;
  
  -- WhatsApp Settings
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='whatsapp_enabled') THEN
    ALTER TABLE hospitals ADD COLUMN whatsapp_enabled VARCHAR(10) DEFAULT 'false';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='whatsapp_confirmation_template') THEN
    ALTER TABLE hospitals ADD COLUMN whatsapp_confirmation_template VARCHAR(500);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='whatsapp_followup_template') THEN
    ALTER TABLE hospitals ADD COLUMN whatsapp_followup_template VARCHAR(500);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='whatsapp_reminder_template') THEN
    ALTER TABLE hospitals ADD COLUMN whatsapp_reminder_template VARCHAR(500);
  END IF;
  
  -- SMTP Configuration
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='smtp_host') THEN
    ALTER TABLE hospitals ADD COLUMN smtp_host VARCHAR(255);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='smtp_port') THEN
    ALTER TABLE hospitals ADD COLUMN smtp_port INTEGER DEFAULT 587;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='smtp_username') THEN
    ALTER TABLE hospitals ADD COLUMN smtp_username VARCHAR(255);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='smtp_password') THEN
    ALTER TABLE hospitals ADD COLUMN smtp_password VARCHAR(255);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='smtp_from_email') THEN
    ALTER TABLE hospitals ADD COLUMN smtp_from_email VARCHAR(255);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='smtp_enabled') THEN
    ALTER TABLE hospitals ADD COLUMN smtp_enabled BOOLEAN DEFAULT FALSE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hospitals' AND column_name='smtp_use_ssl') THEN
    ALTER TABLE hospitals ADD COLUMN smtp_use_ssl BOOLEAN DEFAULT FALSE;
  END IF;
END $$;

-- Create users table if not exists
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  mobile TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK (role IN ('patient', 'pharma', 'doctor')),
  password_hash TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alter users table to add all columns
DO $$ 
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='hospital_id') THEN
    ALTER TABLE users ADD COLUMN hospital_id INTEGER REFERENCES hospitals(id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='address_line1') THEN
    ALTER TABLE users ADD COLUMN address_line1 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='address_line2') THEN
    ALTER TABLE users ADD COLUMN address_line2 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='address_line3') THEN
    ALTER TABLE users ADD COLUMN address_line3 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='last_login_at') THEN
    ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP;
  END IF;
  
  -- Pharma Professional fields
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='company_name') THEN
    ALTER TABLE users ADD COLUMN company_name TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='product1') THEN
    ALTER TABLE users ADD COLUMN product1 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='product2') THEN
    ALTER TABLE users ADD COLUMN product2 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='product3') THEN
    ALTER TABLE users ADD COLUMN product3 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='product4') THEN
    ALTER TABLE users ADD COLUMN product4 TEXT;
  END IF;
  
  -- Doctor fields
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='degree') THEN
    ALTER TABLE users ADD COLUMN degree TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='institute_name') THEN
    ALTER TABLE users ADD COLUMN institute_name TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='experience1') THEN
    ALTER TABLE users ADD COLUMN experience1 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='experience2') THEN
    ALTER TABLE users ADD COLUMN experience2 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='experience3') THEN
    ALTER TABLE users ADD COLUMN experience3 TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='experience4') THEN
    ALTER TABLE users ADD COLUMN experience4 TEXT;
  END IF;
END $$;

-- Create appointments table if not exists
CREATE TABLE IF NOT EXISTS appointments (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  doctor_id INTEGER REFERENCES users(id),
  date DATE NOT NULL,
  time_slot TEXT NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed', 'visited')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alter appointments table to add all columns
DO $$ 
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='hospital_id') THEN
    ALTER TABLE appointments ADD COLUMN hospital_id INTEGER REFERENCES hospitals(id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='reason') THEN
    ALTER TABLE appointments ADD COLUMN reason TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='visit_date') THEN
    ALTER TABLE appointments ADD COLUMN visit_date DATE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='followup_date') THEN
    ALTER TABLE appointments ADD COLUMN followup_date DATE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='amount') THEN
    ALTER TABLE appointments ADD COLUMN amount TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='payment_required') THEN
    ALTER TABLE appointments ADD COLUMN payment_required TEXT DEFAULT 'false';
  END IF;
END $$;

-- Create operations table if not exists
CREATE TABLE IF NOT EXISTS operations (
  id SERIAL PRIMARY KEY,
  patient_id INTEGER REFERENCES users(id),
  doctor_id INTEGER REFERENCES users(id),
  specialty TEXT NOT NULL CHECK (specialty IN ('ortho', 'gyn', 'surgery')),
  operation_date DATE NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alter operations table to add all columns
DO $$ 
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='operations' AND column_name='hospital_id') THEN
    ALTER TABLE operations ADD COLUMN hospital_id INTEGER REFERENCES hospitals(id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='operations' AND column_name='notes') THEN
    ALTER TABLE operations ADD COLUMN notes TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='operations' AND column_name='amount') THEN
    ALTER TABLE operations ADD COLUMN amount TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='operations' AND column_name='payment_required') THEN
    ALTER TABLE operations ADD COLUMN payment_required TEXT DEFAULT 'false';
  END IF;
END $$;

-- ============================================
-- 2. PAYMENT TABLES
-- ============================================

-- Create payments table if not exists
CREATE TABLE IF NOT EXISTS payments (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),  -- Nullable for standalone package purchases
  hospital_id INTEGER REFERENCES hospitals(id),  -- Nullable for standalone package purchases
  amount DECIMAL(10, 2) NOT NULL,
  currency VARCHAR(3) DEFAULT 'INR',
  status VARCHAR(50) NOT NULL DEFAULT 'INITIATED',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alter payments table to add all columns
DO $$ 
BEGIN
  -- Make user_id and hospital_id nullable to support standalone package purchases
  -- Check if column is NOT NULL before altering
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name='payments' 
    AND column_name='user_id' 
    AND is_nullable='NO'
  ) THEN
    ALTER TABLE payments ALTER COLUMN user_id DROP NOT NULL;
  END IF;
  
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name='payments' 
    AND column_name='hospital_id' 
    AND is_nullable='NO'
  ) THEN
    ALTER TABLE payments ALTER COLUMN hospital_id DROP NOT NULL;
  END IF;
  
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='appointment_id') THEN
    ALTER TABLE payments ADD COLUMN appointment_id INTEGER REFERENCES appointments(id) ON DELETE SET NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='operation_id') THEN
    ALTER TABLE payments ADD COLUMN operation_id INTEGER REFERENCES operations(id) ON DELETE SET NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='payment_method') THEN
    ALTER TABLE payments ADD COLUMN payment_method VARCHAR(50);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='razorpay_order_id') THEN
    ALTER TABLE payments ADD COLUMN razorpay_order_id VARCHAR(255);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='razorpay_payment_id') THEN
    ALTER TABLE payments ADD COLUMN razorpay_payment_id VARCHAR(255);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='razorpay_signature') THEN
    ALTER TABLE payments ADD COLUMN razorpay_signature TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='internal_transaction_id') THEN
    ALTER TABLE payments ADD COLUMN internal_transaction_id VARCHAR(255);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='gateway_transaction_id') THEN
    ALTER TABLE payments ADD COLUMN gateway_transaction_id VARCHAR(255);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='transaction_id') THEN
    ALTER TABLE payments ADD COLUMN transaction_id TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='upi_transaction_id') THEN
    ALTER TABLE payments ADD COLUMN upi_transaction_id TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='initiated_at') THEN
    ALTER TABLE payments ADD COLUMN initiated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='completed_at') THEN
    ALTER TABLE payments ADD COLUMN completed_at TIMESTAMP;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='failed_at') THEN
    ALTER TABLE payments ADD COLUMN failed_at TIMESTAMP;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='refunded_at') THEN
    ALTER TABLE payments ADD COLUMN refunded_at TIMESTAMP;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='payment_date') THEN
    ALTER TABLE payments ADD COLUMN payment_date TIMESTAMP;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='failure_reason') THEN
    ALTER TABLE payments ADD COLUMN failure_reason TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='failure_code') THEN
    ALTER TABLE payments ADD COLUMN failure_code VARCHAR(50);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='metadata') THEN
    ALTER TABLE payments ADD COLUMN metadata JSONB;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='notes') THEN
    ALTER TABLE payments ADD COLUMN notes TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='payments' AND column_name='updated_at') THEN
    ALTER TABLE payments ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
  END IF;
  
  -- Drop existing chk_payment_target constraint if it exists (allows standalone package purchases)
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints 
    WHERE table_name='payments' 
    AND constraint_name='chk_payment_target'
  ) THEN
    ALTER TABLE payments DROP CONSTRAINT chk_payment_target;
  END IF;
  
  -- Add new constraint that allows:
  -- 1. appointment_id OR operation_id (for appointment/operation payments)
  -- 2. metadata.type = 'package_purchase' or 'hospital_registration' (for standalone purchases)
  -- 3. Or no constraint if it's a standalone purchase (metadata will be set)
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints 
    WHERE table_name='payments' 
    AND constraint_name='chk_payment_target'
  ) THEN
    ALTER TABLE payments ADD CONSTRAINT chk_payment_target CHECK (
      (appointment_id IS NOT NULL) OR 
      (operation_id IS NOT NULL) OR 
      (metadata IS NOT NULL AND metadata->>'type' IN ('package_purchase', 'hospital_registration'))
    );
  END IF;
END $$;

-- Create payment_webhooks table
CREATE TABLE IF NOT EXISTS payment_webhooks (
    id SERIAL PRIMARY KEY,
    webhook_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payment_id INTEGER REFERENCES payments(id) ON DELETE CASCADE,
    razorpay_payment_id VARCHAR(255),
    razorpay_order_id VARCHAR(255),
    webhook_payload JSONB NOT NULL,
    signature_verified BOOLEAN DEFAULT FALSE,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP,
    processing_error TEXT,
    retry_count INTEGER DEFAULT 0,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create payment_refunds table
CREATE TABLE IF NOT EXISTS payment_refunds (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER REFERENCES payments(id) NOT NULL,
    razorpay_refund_id VARCHAR(255) UNIQUE,
    razorpay_payment_id VARCHAR(255),
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    status VARCHAR(50) NOT NULL,
    reason TEXT,
    refund_type VARCHAR(50),
    initiated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    notes TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create payment_retry_queue table
CREATE TABLE IF NOT EXISTS payment_retry_queue (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER REFERENCES payments(id) ON DELETE CASCADE,
    webhook_id INTEGER REFERENCES payment_webhooks(id) ON DELETE CASCADE,
    retry_type VARCHAR(50) NOT NULL,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 5,
    next_retry_at TIMESTAMP NOT NULL,
    last_attempt_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create payment_manual_review table
CREATE TABLE IF NOT EXISTS payment_manual_review (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER REFERENCES payments(id) NOT NULL,
    reason TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'pending',
    resolved_by INTEGER REFERENCES users(id),
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 3. AUDIT & LOGGING TABLES
-- ============================================

-- Create audit_logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    user_role VARCHAR(50),
    action TEXT NOT NULL,
    resource_type VARCHAR(100),
    resource_id INTEGER,
    details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create whatsapp_logs table
CREATE TABLE IF NOT EXISTS whatsapp_logs (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER REFERENCES hospitals(id),
    mobile TEXT NOT NULL,
    message TEXT NOT NULL,
    message_type VARCHAR(50),
    status VARCHAR(50) DEFAULT 'sent',
    error_message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 4. INDEXES FOR PERFORMANCE
-- ============================================

-- Hospitals indexes
CREATE INDEX IF NOT EXISTS idx_hospitals_status ON hospitals(status);
CREATE INDEX IF NOT EXISTS idx_hospitals_email ON hospitals(email);
CREATE INDEX IF NOT EXISTS idx_hospitals_is_active ON hospitals(is_active);

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_hospital_id ON users(hospital_id);
CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- Appointments indexes
CREATE INDEX IF NOT EXISTS idx_appointments_hospital_id ON appointments(hospital_id);
CREATE INDEX IF NOT EXISTS idx_appointments_user_id ON appointments(user_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor_id ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(date);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);
CREATE INDEX IF NOT EXISTS idx_appointments_followup_date ON appointments(followup_date);
CREATE INDEX IF NOT EXISTS idx_appointments_visit_date ON appointments(visit_date);
CREATE INDEX IF NOT EXISTS idx_appointments_status_date ON appointments(status, date);

-- Operations indexes
CREATE INDEX IF NOT EXISTS idx_operations_hospital_id ON operations(hospital_id);
CREATE INDEX IF NOT EXISTS idx_operations_patient_id ON operations(patient_id);
CREATE INDEX IF NOT EXISTS idx_operations_doctor_id ON operations(doctor_id);
CREATE INDEX IF NOT EXISTS idx_operations_operation_date ON operations(operation_date);
CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_specialty ON operations(specialty);

-- Payments indexes
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_appointment_id ON payments(appointment_id);
CREATE INDEX IF NOT EXISTS idx_payments_operation_id ON payments(operation_id);
CREATE INDEX IF NOT EXISTS idx_payments_hospital_id ON payments(hospital_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_transaction_id ON payments(transaction_id);
CREATE INDEX IF NOT EXISTS idx_payments_razorpay_order_id ON payments(razorpay_order_id) WHERE razorpay_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payments_razorpay_payment_id ON payments(razorpay_payment_id) WHERE razorpay_payment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payments_internal_transaction_id ON payments(internal_transaction_id) WHERE internal_transaction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payments_currency ON payments(currency);
CREATE INDEX IF NOT EXISTS idx_payments_initiated_at ON payments(initiated_at);
CREATE INDEX IF NOT EXISTS idx_payments_completed_at ON payments(completed_at);
CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at);

-- Payment webhooks indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_webhooks_webhook_id ON payment_webhooks(webhook_id);
CREATE INDEX IF NOT EXISTS idx_payment_webhooks_payment_id ON payment_webhooks(payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_webhooks_razorpay_payment_id ON payment_webhooks(razorpay_payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_webhooks_processed ON payment_webhooks(processed);
CREATE INDEX IF NOT EXISTS idx_payment_webhooks_received_at ON payment_webhooks(received_at);
CREATE INDEX IF NOT EXISTS idx_payment_webhooks_event_type ON payment_webhooks(event_type);

-- Payment refunds indexes
CREATE INDEX IF NOT EXISTS idx_payment_refunds_payment_id ON payment_refunds(payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_refunds_razorpay_refund_id ON payment_refunds(razorpay_refund_id);
CREATE INDEX IF NOT EXISTS idx_payment_refunds_status ON payment_refunds(status);

-- Payment retry queue indexes
CREATE INDEX IF NOT EXISTS idx_payment_retry_queue_next_retry_at ON payment_retry_queue(next_retry_at);
CREATE INDEX IF NOT EXISTS idx_payment_retry_queue_status ON payment_retry_queue(status);
CREATE INDEX IF NOT EXISTS idx_payment_retry_queue_payment_id ON payment_retry_queue(payment_id);

-- Payment manual review indexes
CREATE INDEX IF NOT EXISTS idx_payment_manual_review_payment_id ON payment_manual_review(payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_manual_review_status ON payment_manual_review(status);
CREATE INDEX IF NOT EXISTS idx_payment_manual_review_priority ON payment_manual_review(priority);

-- Audit logs indexes
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status);

-- WhatsApp logs indexes
CREATE INDEX IF NOT EXISTS idx_whatsapp_logs_hospital_id ON whatsapp_logs(hospital_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_logs_mobile ON whatsapp_logs(mobile);
CREATE INDEX IF NOT EXISTS idx_whatsapp_logs_status ON whatsapp_logs(status);
CREATE INDEX IF NOT EXISTS idx_whatsapp_logs_sent_at ON whatsapp_logs(sent_at);

-- ============================================
-- 5. ROW LEVEL SECURITY - DISABLED
-- ============================================
-- RLS is disabled to avoid infinite recursion issues
-- If you need RLS, implement it at the application level or use service role keys

-- Disable RLS on all tables to prevent recursion issues
ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY;
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE hospitals DISABLE ROW LEVEL SECURITY;
ALTER TABLE appointments DISABLE ROW LEVEL SECURITY;
ALTER TABLE operations DISABLE ROW LEVEL SECURITY;
ALTER TABLE payments DISABLE ROW LEVEL SECURITY;

-- Drop any existing problematic policies
DROP POLICY IF EXISTS "Admins can view audit logs" ON audit_logs;

-- ============================================
-- 6. TABLE COMMENTS FOR DOCUMENTATION
-- ============================================

COMMENT ON TABLE hospitals IS 'Hospital registration and management with UPI, WhatsApp, and SMTP settings';
COMMENT ON TABLE users IS 'Users: patients, pharma professionals, and doctors';
COMMENT ON TABLE appointments IS 'Patient appointments with doctors';
COMMENT ON TABLE operations IS 'Scheduled operations';
COMMENT ON TABLE payments IS 'Payment records for appointments and operations with Razorpay integration';
COMMENT ON TABLE payment_webhooks IS 'Razorpay webhook events for idempotency and audit trail';
COMMENT ON TABLE payment_refunds IS 'Payment refund records';
COMMENT ON TABLE payment_retry_queue IS 'Queue for retrying failed payment operations';
COMMENT ON TABLE payment_manual_review IS 'Payments requiring manual review';
COMMENT ON TABLE audit_logs IS 'Audit trail for all system events';
COMMENT ON TABLE whatsapp_logs IS 'WhatsApp message delivery logs';

COMMENT ON COLUMN hospitals.upi_id IS 'Default/Universal UPI ID for payments';
COMMENT ON COLUMN hospitals.gpay_upi_id IS 'Google Pay specific UPI ID';
COMMENT ON COLUMN hospitals.phonepay_upi_id IS 'PhonePe specific UPI ID';
COMMENT ON COLUMN hospitals.paytm_upi_id IS 'Paytm specific UPI ID';
COMMENT ON COLUMN hospitals.bhim_upi_id IS 'BHIM UPI specific UPI ID';
COMMENT ON COLUMN hospitals.whatsapp_enabled IS 'Whether WhatsApp notifications are enabled';
COMMENT ON COLUMN hospitals.smtp_host IS 'SMTP server hostname (e.g., smtp.gmail.com)';
COMMENT ON COLUMN hospitals.smtp_port IS 'SMTP server port (587 for TLS, 465 for SSL)';
COMMENT ON COLUMN hospitals.smtp_username IS 'SMTP username/email';
COMMENT ON COLUMN hospitals.smtp_password IS 'SMTP password (should be encrypted in production)';
COMMENT ON COLUMN hospitals.smtp_from_email IS 'Email address to send from';
COMMENT ON COLUMN hospitals.smtp_enabled IS 'Whether to use hospital-specific SMTP (false = use global)';
COMMENT ON COLUMN hospitals.smtp_use_ssl IS 'Use SSL (port 465) instead of TLS (port 587)';

COMMENT ON COLUMN payments.status IS 'Payment status: INITIATED, PENDING, COMPLETED, FAILED, CANCELLED, REFUNDED, PARTIALLY_REFUNDED';
COMMENT ON COLUMN payments.razorpay_order_id IS 'Razorpay order ID (unique)';
COMMENT ON COLUMN payments.razorpay_payment_id IS 'Razorpay payment ID (unique)';
COMMENT ON COLUMN payments.internal_transaction_id IS 'Internal idempotency key (unique)';

-- ============================================
-- SCHEMA UPDATE COMPLETE
-- ============================================
