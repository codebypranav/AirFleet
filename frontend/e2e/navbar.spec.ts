import { expect, test } from '@playwright/test';
import { register } from './helpers';

test('the navbar groups pages into menus and keeps the account under the avatar', async ({ page }) => {
    await register(page, `nav${Date.now()}`);

    const logbook = page.getByRole('button', { name: 'Logbook' });
    await expect(logbook).toHaveAttribute('aria-expanded', 'false');
    await logbook.click();
    await expect(logbook).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByRole('link', { name: 'Fleet', exact: true })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('link', { name: 'Fleet', exact: true })).toHaveCount(0);
    await expect(logbook).toBeFocused();
    await logbook.click();
    await page.getByRole('button', { name: 'Community' }).focus();
    await expect(page.getByRole('link', { name: 'Fleet', exact: true })).toHaveCount(0);

    await page.getByRole('button', { name: 'Community' }).click();
    await page.locator('main').click();
    await expect(page.getByRole('link', { name: 'Rankings' })).toHaveCount(0);

    await page.getByRole('button', { name: 'Community' }).click();
    await page.getByRole('link', { name: 'Rankings' }).click();
    await expect(page).toHaveURL(/\/rankings$/);
    await expect(page.getByRole('button', { name: 'Community' })).toHaveAttribute('aria-current', 'page');

    await page.getByRole('button', { name: 'Account', exact: true }).click();
    await page.getByRole('link', { name: 'Settings' }).click();
    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.getByRole('heading', { name: 'Password' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Delete account' })).toBeVisible();

    await page.getByRole('button', { name: 'Account', exact: true }).click();
    await page.getByRole('link', { name: 'Edit profile' }).click();
    await expect(page).toHaveURL(/\/profile$/);
    await expect(page.getByRole('heading', { name: 'Profile picture' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Delete account' })).toHaveCount(0);

    await page.getByRole('button', { name: 'Account', exact: true }).click();
    await page.getByRole('button', { name: 'Log out' }).click();
    await expect(page).toHaveURL(/\/login$/);
});

test('the navbar fits a phone without sideways scrolling', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await register(page, `narrow${Date.now()}`);
    await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeInViewport({ ratio: 1 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
});
