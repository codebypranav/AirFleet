import { expect, test } from '@playwright/test';
import { register } from './helpers';

test('the navbar links the logbook pages, menus the community ones and keeps the account under the avatar', async ({ page }) => {
    await register(page, `nav${Date.now()}`);

    const nav = page.getByRole('navigation');
    for (const [name, path] of [['Fleet', 'aircraft'], ['Stats', 'stats'], ['Instruction', 'instruction'], ['Flights', 'flights']]) {
        const tab = nav.getByRole('link', { name, exact: true });
        await tab.click();
        await expect(page).toHaveURL(new RegExp(`/${path}$`));
        await expect(tab).toHaveAttribute('aria-current', 'page');
    }

    const community = page.getByRole('button', { name: 'Community' });
    const rankings = page.getByRole('link', { name: 'Rankings' });
    await expect(community).toHaveAttribute('aria-expanded', 'false');
    await community.click();
    await expect(community).toHaveAttribute('aria-expanded', 'true');
    await expect(rankings).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(rankings).toHaveCount(0);
    await expect(community).toBeFocused();
    await community.click();
    await page.getByRole('button', { name: 'Account', exact: true }).focus();
    await expect(rankings).toHaveCount(0);

    await community.click();
    await page.locator('main').click();
    await expect(rankings).toHaveCount(0);

    await community.click();
    await rankings.click();
    await expect(page).toHaveURL(/\/rankings$/);
    await expect(community).toHaveAttribute('aria-current', 'page');

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
    await page.setViewportSize({ width: 320, height: 640 });
    await register(page, `narrow${Date.now()}`);
    await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeInViewport({ ratio: 1 });
    const community = page.getByRole('button', { name: 'Community' });
    await expect(community).toBeInViewport({ ratio: 1 });
    const flights = await page.getByRole('navigation').getByRole('link', { name: 'Flights', exact: true }).boundingBox();
    expect((await community.boundingBox())!.y).toBe(flights!.y);
    await community.click();
    await expect(page.getByRole('link', { name: 'Rankings' })).toBeInViewport({ ratio: 1 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
});
