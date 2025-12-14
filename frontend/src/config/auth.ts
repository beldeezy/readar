/**
 * TEMP: AUTH_DISABLED = true means we bypass real auth and always use a test user
 * until Firebase/Vercel integration is ready.
 * 
 * To re-enable auth:
 * 1. Set AUTH_DISABLED = false
 * 2. Reinstating the original sign-up/login flows and guards
 */
export const AUTH_DISABLED = true;

/**
 * Test user ID used when AUTH_DISABLED is true.
 * This should match any test user ID used in the backend if applicable.
 * 
 * @deprecated Use DEV_TEST_USER_ID from '../api/constants' instead
 */
import { DEV_TEST_USER_ID } from '../api/constants';
export const TEST_USER_ID = DEV_TEST_USER_ID;

/**
 * Test user object used when AUTH_DISABLED is true.
 */
export const TEST_USER = {
  id: TEST_USER_ID,
  email: 'test@readar.com',
  subscription_status: 'free' as const,
  created_at: new Date().toISOString(),
};

