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

