import { test, expect, noOverflow } from './fixtures.js';
for (const width of [1440,375]) {
  test(width===375?'MOBILE_KEYBOARD_AND_VALIDATION':'DESKTOP_KEYBOARD_AND_VALIDATION', async ({ page }) => {
    await page.setViewportSize({width,height:900});
    await page.goto('/merchant/login');
    await expect(page.locator('#login-form')).toBeVisible();
    await noOverflow(page);
    await page.locator('#login').focus();
    await page.keyboard.press('Tab');await expect(page.locator('#password')).toBeFocused();
    await page.keyboard.press('Tab');await expect(page.locator('#toggle-password')).toBeFocused();
    await page.keyboard.press('Enter');await expect(page.locator('#password')).toHaveAttribute('type','text');
    await page.keyboard.press('Enter');await expect(page.locator('#password')).toHaveAttribute('type','password');
    await page.locator('#login-submit').click();
    await expect(page.locator('#login')).toBeFocused();
    await page.goto('/merchant/signup');
    await page.locator('#signup-check').click();
    await expect(page.locator('#signup-feedback')).toContainText('Check the highlighted fields');
    await expect(page.locator('#signup-firstName')).toHaveAttribute('aria-invalid','true');
    await noOverflow(page);
    await page.goto('/admin/login');await expect(page.locator('#login-form')).toBeVisible();await noOverflow(page);
  });
}
