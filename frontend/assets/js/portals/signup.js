export const BUSINESS_TYPES = Object.freeze(['SOLE_PROPRIETOR','COMPANY','PARTNERSHIP','NONPROFIT','OTHER']);
export const COUNTRIES = Object.freeze(['IN','US','GB','CA','AU','OTHER']);
// Mirrors public registration constraints; Java independently validates every field.
export function validateSignup(input) {
  const errors = {};
  for (const [key, label, limit] of [['firstName','First name',80],['lastName','Last name',80],['businessName','Business name',160]]) {
    if (typeof input[key] !== 'string' || !input[key].trim() || input[key].length > limit) errors[key] = `${label} is required and must fit within ${limit} characters.`;
  }
  if (typeof input.email !== 'string' || input.email.trim().length > 254 || !/^[a-z0-9][a-z0-9._+\-]*@[a-z0-9][a-z0-9.\-]*\.[a-z]{2,}$/i.test(input.email.trim())) errors.email = 'Enter a valid business email.';
  if (typeof input.mobile !== 'string' || !/^\+?[0-9]{7,15}$/.test(input.mobile)) errors.mobile = 'Use 7–15 digits with an optional leading +.';
  if (!BUSINESS_TYPES.includes(input.businessType)) errors.businessType = 'Choose a business type.';
  if (!COUNTRIES.includes(input.country)) errors.country = 'Choose a country.';
  if (typeof input.password !== 'string' || [...input.password].length < 12 || new TextEncoder().encode(input.password).length > 72 || /[\u0000\uD800-\uDFFF]/u.test(input.password)) errors.password = 'Use at least 12 characters and at most 72 UTF-8 bytes.';
  if (!input.confirmPassword || input.password !== input.confirmPassword) errors.confirmPassword = 'Passwords must match.';
  if (input.terms !== true) errors.terms = 'Acknowledge the demo terms and privacy notice.';
  return errors;
}
