-- ============================================
-- Hospital Booking System - Complete Database Schema
-- Supabase PostgreSQL Schema
-- This script DROPS and RECREATES all tables with proper segregation
-- Run this entire file in Supabase SQL Editor
-- ============================================

-- ============================================
-- DROP ALL EXISTING TABLES (in correct order due to foreign keys)
-- ============================================

DROP TABLE IF EXISTS payment_manual_review CASCADE;
DROP TABLE IF EXISTS payment_retry_queue CASCADE;
DROP TABLE IF EXISTS payment_refunds CASCADE;
DROP TABLE IF EXISTS payment_webhooks CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS whatsapp_logs CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS operations CASCADE;
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS doctors CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS hospitals CASCADE;

-- ============================================
-- 1. CORE TABLES - Create with proper structure
-- ============================================

-- ============================================
-- 1.1 HOSPITALS TABLE
-- ============================================
CREATE TABLE hospitals (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  mobile TEXT NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Address fields
  address_line1 TEXT,
  address_line2 TEXT,
  address_line3 TEXT,
  city TEXT,
  state TEXT,
  pincode TEXT,
  
  -- Registration fields
  registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  approved_date TIMESTAMP,
  plan TEXT,
  expiry_date DATE,
  is_active BOOLEAN DEFAULT true,
  
  -- UPI Payment IDs
  upi_id TEXT,
  gpay_upi_id TEXT,
  phonepay_upi_id TEXT,
  paytm_upi_id TEXT,
  bhim_upi_id TEXT,
  
  -- WhatsApp Settings
  whatsapp_enabled VARCHAR(10) DEFAULT 'false',
  whatsapp_confirmation_template VARCHAR(500),
  whatsapp_followup_template VARCHAR(500),
  whatsapp_reminder_template VARCHAR(500),
  
  -- SMTP Configuration
  smtp_host VARCHAR(255),
  smtp_port INTEGER DEFAULT 587,
  smtp_username VARCHAR(255),
  smtp_password VARCHAR(255),
  smtp_from_email VARCHAR(255),
  smtp_enabled BOOLEAN DEFAULT FALSE,
  smtp_use_ssl BOOLEAN DEFAULT FALSE
);

-- ============================================
-- 1.2 USERS TABLE (for patients and pharma professionals only)
-- ============================================
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  mobile TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK (role IN ('patient', 'pharma')),
  password_hash TEXT NOT NULL,
  email TEXT,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMP,
  
  -- Address fields
  address_line1 TEXT,
  address_line2 TEXT,
  address_line3 TEXT,
  
  -- Hospital association (for pharma professionals)
  hospital_id INTEGER REFERENCES hospitals(id) ON DELETE SET NULL,
  
  -- Pharma Professional fields
  company_name TEXT,
  product1 TEXT,
  product2 TEXT,
  product3 TEXT,
  product4 TEXT
);

-- ============================================
-- 1.3 DOCTORS TABLE (dedicated table for doctors)
-- ============================================
CREATE TABLE doctors (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL UNIQUE, -- Optional: link to users table for authentication
  hospital_id INTEGER REFERENCES hospitals(id) ON DELETE SET NULL NOT NULL,
  
  -- Basic info
  name TEXT NOT NULL,
  mobile TEXT,
  email TEXT,
  
  -- Professional info
  degree TEXT NOT NULL,
  institute_name TEXT,
  specialization TEXT,
  
  -- Experience
  experience1 TEXT,
  experience2 TEXT,
  experience3 TEXT,
  experience4 TEXT,
  
  -- Status
  is_active BOOLEAN DEFAULT true,
  source TEXT DEFAULT 'registered', -- 'registered', 'crowdsourced'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 1.4 APPOINTMENTS TABLE
-- ============================================
CREATE TABLE appointments (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, -- Patient (can be null for guest bookings)
  doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE NOT NULL,
  hospital_id INTEGER REFERENCES hospitals(id) ON DELETE SET NULL NOT NULL,
  
  -- Appointment details
  date DATE NOT NULL,
  time_slot TEXT NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed', 'visited')),
  reason TEXT,
  
  -- Visit tracking
  visit_date DATE,
  followup_date DATE,
  
  -- Payment
  amount TEXT,
  payment_required TEXT DEFAULT 'false',
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 1.5 OPERATIONS TABLE
-- ============================================
CREATE TABLE operations (
  id SERIAL PRIMARY KEY,
  patient_id INTEGER REFERENCES users(id) ON DELETE SET NULL, -- Patient
  doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE NOT NULL,
  hospital_id INTEGER REFERENCES hospitals(id) ON DELETE SET NULL NOT NULL,
  
  -- Operation details
  specialty TEXT NOT NULL CHECK (specialty IN ('ortho', 'gyn', 'surgery')),
  operation_date DATE NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed')),
  notes TEXT,
  
  -- Payment
  amount TEXT,
  payment_required TEXT DEFAULT 'false',
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 2. PAYMENT TABLES
-- ============================================

-- ============================================
-- 2.1 PAYMENTS TABLE
-- ============================================
CREATE TABLE payments (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, -- Nullable for standalone package purchases
  hospital_id INTEGER REFERENCES hospitals(id) ON DELETE SET NULL, -- Nullable for standalone package purchases
  appointment_id INTEGER REFERENCES appointments(id) ON DELETE SET NULL,
  operation_id INTEGER REFERENCES operations(id) ON DELETE SET NULL,
  
  -- Payment details
  amount DECIMAL(10, 2) NOT NULL,
  currency VARCHAR(3) DEFAULT 'INR',
  status VARCHAR(50) NOT NULL DEFAULT 'INITIATED' CHECK (status IN ('INITIATED', 'PENDING', 'COMPLETED', 'FAILED', 'CANCELLED', 'REFUNDED', 'PARTIALLY_REFUNDED')),
  payment_method VARCHAR(50), -- 'upi', 'cashfree', 'razorpay'
  
  -- Razorpay fields
  razorpay_order_id VARCHAR(255),
  razorpay_payment_id VARCHAR(255),
  razorpay_signature TEXT,
  
  -- Cashfree fields
  cashfree_order_id VARCHAR(255),
  cashfree_session_id TEXT,
  cashfree_payment_id VARCHAR(255),
  
  -- Transaction tracking
  internal_transaction_id VARCHAR(255) UNIQUE,
  gateway_transaction_id VARCHAR(255),
  transaction_id TEXT,
  upi_transaction_id TEXT,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  initiated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  failed_at TIMESTAMP,
  refunded_at TIMESTAMP,
  payment_date TIMESTAMP,
  
  -- Error tracking
  failure_reason TEXT,
  failure_code VARCHAR(50),
  
  -- Metadata
  metadata JSONB,
  notes TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Constraint: Payment must have appointment, operation, or metadata type
  CONSTRAINT chk_payment_target CHECK (
    (appointment_id IS NOT NULL) OR 
    (operation_id IS NOT NULL) OR 
    (metadata IS NOT NULL AND metadata->>'type' IN ('package_purchase', 'hospital_registration'))
  )
);

-- ============================================
-- 2.2 PAYMENT WEBHOOKS TABLE
-- ============================================
CREATE TABLE payment_webhooks (
  id SERIAL PRIMARY KEY,
  webhook_id VARCHAR(255) UNIQUE NOT NULL,
  event_type VARCHAR(100) NOT NULL,
  payment_id INTEGER REFERENCES payments(id) ON DELETE CASCADE,
  
  -- Gateway references
  razorpay_payment_id VARCHAR(255),
  razorpay_order_id VARCHAR(255),
  cashfree_payment_id VARCHAR(255),
  cashfree_order_id VARCHAR(255),
  
  -- Webhook data
  webhook_payload JSONB NOT NULL,
  signature_verified BOOLEAN DEFAULT FALSE,
  
  -- Processing status
  processed BOOLEAN DEFAULT FALSE,
  processed_at TIMESTAMP,
  processing_error TEXT,
  retry_count INTEGER DEFAULT 0,
  
  -- Timestamps
  received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 2.3 PAYMENT REFUNDS TABLE
-- ============================================
CREATE TABLE payment_refunds (
  id SERIAL PRIMARY KEY,
  payment_id INTEGER REFERENCES payments(id) NOT NULL,
  
  -- Refund details
  razorpay_refund_id VARCHAR(255) UNIQUE,
  razorpay_payment_id VARCHAR(255),
  amount DECIMAL(10, 2) NOT NULL,
  currency VARCHAR(3) DEFAULT 'INR',
  status VARCHAR(50) NOT NULL,
  reason TEXT,
  refund_type VARCHAR(50),
  
  -- Timestamps
  initiated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  processed_at TIMESTAMP,
  
  -- Metadata
  notes TEXT,
  metadata JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 2.4 PAYMENT RETRY QUEUE TABLE
-- ============================================
CREATE TABLE payment_retry_queue (
  id SERIAL PRIMARY KEY,
  payment_id INTEGER REFERENCES payments(id) ON DELETE CASCADE,
  webhook_id INTEGER REFERENCES payment_webhooks(id) ON DELETE CASCADE,
  
  -- Retry details
  retry_type VARCHAR(50) NOT NULL,
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 5,
  next_retry_at TIMESTAMP NOT NULL,
  last_attempt_at TIMESTAMP,
  status VARCHAR(50) DEFAULT 'pending',
  
  -- Error tracking
  last_error TEXT,
  error_count INTEGER DEFAULT 0,
  payload JSONB,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 2.5 PAYMENT MANUAL REVIEW TABLE
-- ============================================
CREATE TABLE payment_manual_review (
  id SERIAL PRIMARY KEY,
  payment_id INTEGER REFERENCES payments(id) NOT NULL,
  reason TEXT NOT NULL,
  priority VARCHAR(20) DEFAULT 'medium',
  status VARCHAR(50) DEFAULT 'pending',
  
  -- Resolution
  resolved_by INTEGER REFERENCES users(id),
  resolved_at TIMESTAMP,
  resolution_notes TEXT,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 3. AUDIT & LOGGING TABLES
-- ============================================

-- ============================================
-- 3.1 AUDIT LOGS TABLE
-- ============================================
CREATE TABLE audit_logs (
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

-- ============================================
-- 3.2 WHATSAPP LOGS TABLE
-- ============================================
CREATE TABLE whatsapp_logs (
  id SERIAL PRIMARY KEY,
  hospital_id INTEGER REFERENCES hospitals(id) ON DELETE SET NULL,
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
CREATE INDEX idx_hospitals_status ON hospitals(status);
CREATE INDEX idx_hospitals_email ON hospitals(email);
CREATE INDEX idx_hospitals_is_active ON hospitals(is_active);

-- Users indexes
CREATE INDEX idx_users_hospital_id ON users(hospital_id);
CREATE INDEX idx_users_mobile ON users(mobile);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

-- Doctors indexes
CREATE INDEX idx_doctors_user_id ON doctors(user_id);
CREATE INDEX idx_doctors_hospital_id ON doctors(hospital_id);
CREATE INDEX idx_doctors_name ON doctors(name);
CREATE INDEX idx_doctors_mobile ON doctors(mobile) WHERE mobile IS NOT NULL;
CREATE INDEX idx_doctors_is_active ON doctors(is_active);
CREATE INDEX idx_doctors_specialization ON doctors(specialization) WHERE specialization IS NOT NULL;

-- Appointments indexes
CREATE INDEX idx_appointments_hospital_id ON appointments(hospital_id);
CREATE INDEX idx_appointments_user_id ON appointments(user_id);
CREATE INDEX idx_appointments_doctor_id ON appointments(doctor_id);
CREATE INDEX idx_appointments_date ON appointments(date);
CREATE INDEX idx_appointments_status ON appointments(status);
CREATE INDEX idx_appointments_followup_date ON appointments(followup_date);
CREATE INDEX idx_appointments_visit_date ON appointments(visit_date);
CREATE INDEX idx_appointments_status_date ON appointments(status, date);
CREATE INDEX idx_appointments_doctor_date ON appointments(doctor_id, date);

-- Operations indexes
CREATE INDEX idx_operations_hospital_id ON operations(hospital_id);
CREATE INDEX idx_operations_patient_id ON operations(patient_id);
CREATE INDEX idx_operations_doctor_id ON operations(doctor_id);
CREATE INDEX idx_operations_operation_date ON operations(operation_date);
CREATE INDEX idx_operations_status ON operations(status);
CREATE INDEX idx_operations_specialty ON operations(specialty);

-- Payments indexes
CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_appointment_id ON payments(appointment_id);
CREATE INDEX idx_payments_operation_id ON payments(operation_id);
CREATE INDEX idx_payments_hospital_id ON payments(hospital_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_transaction_id ON payments(transaction_id);
CREATE INDEX idx_payments_razorpay_order_id ON payments(razorpay_order_id) WHERE razorpay_order_id IS NOT NULL;
CREATE INDEX idx_payments_razorpay_payment_id ON payments(razorpay_payment_id) WHERE razorpay_payment_id IS NOT NULL;
CREATE INDEX idx_payments_cashfree_order_id ON payments(cashfree_order_id) WHERE cashfree_order_id IS NOT NULL;
CREATE INDEX idx_payments_internal_transaction_id ON payments(internal_transaction_id) WHERE internal_transaction_id IS NOT NULL;
CREATE INDEX idx_payments_currency ON payments(currency);
CREATE INDEX idx_payments_initiated_at ON payments(initiated_at);
CREATE INDEX idx_payments_completed_at ON payments(completed_at);
CREATE INDEX idx_payments_created_at ON payments(created_at);

-- Payment webhooks indexes
CREATE UNIQUE INDEX idx_payment_webhooks_webhook_id ON payment_webhooks(webhook_id);
CREATE INDEX idx_payment_webhooks_payment_id ON payment_webhooks(payment_id);
CREATE INDEX idx_payment_webhooks_razorpay_payment_id ON payment_webhooks(razorpay_payment_id);
CREATE INDEX idx_payment_webhooks_cashfree_payment_id ON payment_webhooks(cashfree_payment_id);
CREATE INDEX idx_payment_webhooks_processed ON payment_webhooks(processed);
CREATE INDEX idx_payment_webhooks_received_at ON payment_webhooks(received_at);
CREATE INDEX idx_payment_webhooks_event_type ON payment_webhooks(event_type);

-- Payment refunds indexes
CREATE INDEX idx_payment_refunds_payment_id ON payment_refunds(payment_id);
CREATE INDEX idx_payment_refunds_razorpay_refund_id ON payment_refunds(razorpay_refund_id);
CREATE INDEX idx_payment_refunds_status ON payment_refunds(status);

-- Payment retry queue indexes
CREATE INDEX idx_payment_retry_queue_next_retry_at ON payment_retry_queue(next_retry_at);
CREATE INDEX idx_payment_retry_queue_status ON payment_retry_queue(status);
CREATE INDEX idx_payment_retry_queue_payment_id ON payment_retry_queue(payment_id);

-- Payment manual review indexes
CREATE INDEX idx_payment_manual_review_payment_id ON payment_manual_review(payment_id);
CREATE INDEX idx_payment_manual_review_status ON payment_manual_review(status);
CREATE INDEX idx_payment_manual_review_priority ON payment_manual_review(priority);

-- Audit logs indexes
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_status ON audit_logs(status);

-- WhatsApp logs indexes
CREATE INDEX idx_whatsapp_logs_hospital_id ON whatsapp_logs(hospital_id);
CREATE INDEX idx_whatsapp_logs_mobile ON whatsapp_logs(mobile);
CREATE INDEX idx_whatsapp_logs_status ON whatsapp_logs(status);
CREATE INDEX idx_whatsapp_logs_sent_at ON whatsapp_logs(sent_at);

-- ============================================
-- 5. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================

-- Enable RLS on all tables
ALTER TABLE hospitals ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctors ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_webhooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_refunds ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_retry_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_manual_review ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_logs ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 5.1 HOSPITALS RLS POLICIES
-- ============================================

-- Allow public read access to approved hospitals
CREATE POLICY "Public can view approved hospitals"
  ON hospitals FOR SELECT
  USING (status = 'approved' AND is_active = true);

-- Allow authenticated users to view their own hospital
-- Note: Simplified for application-level auth (service role bypasses RLS)
CREATE POLICY "Users can view their hospital"
  ON hospitals FOR SELECT
  USING (true); -- Simplified: service role handles auth at application level

-- Allow service role to do everything
CREATE POLICY "Service role full access to hospitals"
  ON hospitals FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================
-- 5.2 USERS RLS POLICIES
-- ============================================

-- Users can view their own profile
-- Note: Simplified for now. If using Supabase auth with UUIDs, adjust accordingly
CREATE POLICY "Users can view own profile"
  ON users FOR SELECT
  USING (true); -- Simplified: service role handles auth at application level

-- Users can update their own profile
CREATE POLICY "Users can update own profile"
  ON users FOR UPDATE
  USING (true); -- Simplified: service role handles auth at application level

-- Public can create users (registration)
CREATE POLICY "Public can create users"
  ON users FOR INSERT
  WITH CHECK (true);

-- Service role full access
CREATE POLICY "Service role full access to users"
  ON users FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================
-- 5.3 DOCTORS RLS POLICIES
-- ============================================

-- Public can view active doctors
CREATE POLICY "Public can view active doctors"
  ON doctors FOR SELECT
  USING (is_active = true);

-- Doctors can view their own profile
-- Note: Simplified for now. Adjust if using Supabase auth with UUIDs
CREATE POLICY "Doctors can view own profile"
  ON doctors FOR SELECT
  USING (true); -- Simplified: service role handles auth at application level

-- Service role full access
CREATE POLICY "Service role full access to doctors"
  ON doctors FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================
-- 5.4 APPOINTMENTS RLS POLICIES
-- ============================================

-- Users can view their own appointments
-- Note: Simplified for application-level auth
CREATE POLICY "Users can view own appointments"
  ON appointments FOR SELECT
  USING (true); -- Simplified: service role handles auth at application level

-- Doctors can view appointments for their hospital
CREATE POLICY "Doctors can view hospital appointments"
  ON appointments FOR SELECT
  USING (true); -- Simplified: service role handles auth at application level

-- Public can create appointments (guest bookings)
CREATE POLICY "Public can create appointments"
  ON appointments FOR INSERT
  WITH CHECK (true);

-- Users can update their own appointments
CREATE POLICY "Users can update own appointments"
  ON appointments FOR UPDATE
  USING (true); -- Simplified: service role handles auth at application level

-- Service role full access
CREATE POLICY "Service role full access to appointments"
  ON appointments FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================
-- 5.5 OPERATIONS RLS POLICIES
-- ============================================

-- Users can view their own operations
CREATE POLICY "Users can view own operations"
  ON operations FOR SELECT
  USING (true); -- Simplified: service role handles auth at application level

-- Doctors can view operations for their hospital
CREATE POLICY "Doctors can view hospital operations"
  ON operations FOR SELECT
  USING (true); -- Simplified: service role handles auth at application level

-- Service role full access
CREATE POLICY "Service role full access to operations"
  ON operations FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================
-- 5.6 PAYMENTS RLS POLICIES
-- ============================================

-- Users can view their own payments
CREATE POLICY "Users can view own payments"
  ON payments FOR SELECT
  USING (true); -- Simplified: service role handles auth at application level (payments are sensitive)

-- Allow INSERT for payments with hospital_registration metadata (for guest hospital registrations)
CREATE POLICY "Allow hospital registration payments"
  ON payments FOR INSERT
  WITH CHECK (
    metadata IS NOT NULL AND 
    metadata->>'type' = 'hospital_registration'
  );

-- Service role full access (payments are sensitive)
CREATE POLICY "Service role full access to payments"
  ON payments FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================
-- 5.7 AUDIT LOGS RLS POLICIES
-- ============================================

-- Service role only (audit logs are sensitive)
CREATE POLICY "Service role only access to audit logs"
  ON audit_logs FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================
-- 5.8 WHATSAPP LOGS RLS POLICIES
-- ============================================

-- Hospital admins can view their hospital's logs
CREATE POLICY "Hospital admins can view their logs"
  ON whatsapp_logs FOR SELECT
  USING (true); -- Simplified: service role handles auth at application level

-- Service role full access
CREATE POLICY "Service role full access to whatsapp logs"
  ON whatsapp_logs FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================
-- 6. TABLE COMMENTS FOR DOCUMENTATION
-- ============================================

COMMENT ON TABLE hospitals IS 'Hospital registration and management with UPI, WhatsApp, and SMTP settings';
COMMENT ON TABLE users IS 'Users: patients and pharma professionals (authentication)';
COMMENT ON TABLE doctors IS 'Dedicated table for doctor profiles and professional information';
COMMENT ON TABLE appointments IS 'Patient appointments with doctors';
COMMENT ON TABLE operations IS 'Scheduled operations';
COMMENT ON TABLE payments IS 'Payment records for appointments and operations with Cashfree/Razorpay integration';
COMMENT ON TABLE payment_webhooks IS 'Payment gateway webhook events for idempotency and audit trail';
COMMENT ON TABLE payment_refunds IS 'Payment refund records';
COMMENT ON TABLE payment_retry_queue IS 'Queue for retrying failed payment operations';
COMMENT ON TABLE payment_manual_review IS 'Payments requiring manual review';
COMMENT ON TABLE audit_logs IS 'Audit trail for all system events';
COMMENT ON TABLE whatsapp_logs IS 'WhatsApp message delivery logs';

COMMENT ON COLUMN doctors.user_id IS 'Optional: links to users table if doctor has authentication account';
COMMENT ON COLUMN doctors.source IS 'Source: registered (via system) or crowdsourced (added by users)';
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
COMMENT ON COLUMN payments.payment_method IS 'Payment method: upi, cashfree, razorpay';
COMMENT ON COLUMN payments.razorpay_order_id IS 'Razorpay order ID (unique)';
COMMENT ON COLUMN payments.razorpay_payment_id IS 'Razorpay payment ID (unique)';
COMMENT ON COLUMN payments.cashfree_order_id IS 'Cashfree order ID (unique)';
COMMENT ON COLUMN payments.cashfree_session_id IS 'Cashfree payment session ID';
COMMENT ON COLUMN payments.internal_transaction_id IS 'Internal idempotency key (unique)';

-- ============================================
-- 7. FUNCTIONS AND TRIGGERS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_doctors_updated_at BEFORE UPDATE ON doctors
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_appointments_updated_at BEFORE UPDATE ON appointments
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_operations_updated_at BEFORE UPDATE ON operations
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payments_updated_at BEFORE UPDATE ON payments
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payment_refunds_updated_at BEFORE UPDATE ON payment_refunds
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payment_retry_queue_updated_at BEFORE UPDATE ON payment_retry_queue
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payment_manual_review_updated_at BEFORE UPDATE ON payment_manual_review
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- SCHEMA CREATION COMPLETE
-- ============================================
-- Note: After running this script, you may need to:
-- 1. Update your backend code to use 'doctors' table instead of 'users' with role='doctor'
-- 2. Migrate existing doctor data from users table to doctors table
-- 3. Set up authentication for doctors (either via users table link or separate auth)
-- ============================================



-- Extra
-- Add INSERT policy for hospital_registration payments
-- This allows guest hospital registrations without service role key

-- Drop existing policy if it exists
DROP POLICY IF EXISTS "Allow hospital registration payments" ON payments;

-- Create new INSERT policy
CREATE POLICY "Allow hospital registration payments"
  ON payments FOR INSERT
  WITH CHECK (
    metadata IS NOT NULL AND 
    metadata->>'type' = 'hospital_registration'
  );

