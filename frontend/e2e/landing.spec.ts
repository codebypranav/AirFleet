import { expect, test } from '@playwright/test';

const FEATURES = [
    'Logbook and stats',
    'Quick log and flight plans',
    'Plan review and patterns',
    'Live flights and crew',
    'Following, comments and likes',
    'Instructor sign-off',
];

test('the landing page shows each feature with its screenshot', async ({ page }) => {
    await page.goto('/');

    for (const name of FEATURES) {
        const feature = page.getByRole('region', { name });
        await feature.scrollIntoViewIfNeeded();
        await expect(feature.getByRole('heading', { name })).toBeVisible();
        const shot = feature.getByRole('img');
        await expect(shot).toBeVisible();
        await expect.poll(() => shot.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth)).toBeGreaterThan(0);
    }
});
