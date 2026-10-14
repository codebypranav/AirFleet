import { expect, test } from '@playwright/test';
import { logFlight, register } from './helpers';

const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64');

test('a captain adds a first officer, who accepts the flight into their logbook', async ({ browser }) => {
    const stamp = Date.now();
    const captain = await (await browser.newContext()).newPage();
    const fo = await (await browser.newContext()).newPage();

    await register(fo, `fo${stamp}`);
    await fo.goto('/profile');
    await fo.getByLabel('Upload').setInputFiles({ name: 'me.png', mimeType: 'image/png', buffer: PNG });
    await expect(fo.getByRole('button', { name: 'Remove' })).toBeVisible();

    await register(captain, `cpt${stamp}`);
    await logFlight(captain, { from: 'KPAO', to: 'KSQL', reg: 'N172SP', day: '2026-02-03' });
    await captain.getByLabel('Add a pilot who flew with you').fill(`fo${stamp}`);
    await captain.getByLabel('As', { exact: true }).selectOption('SIC');
    await captain.getByRole('button', { name: 'Invite' }).click();
    await expect(captain.getByText('First officer (SIC) · Invited')).toBeVisible();

    await fo.goto('/flights');
    await expect(fo.getByText(`cpt${stamp} added you as First officer (SIC)`)).toBeVisible();
    await fo.getByRole('button', { name: 'Add to my logbook' }).click();
    await expect(fo.getByText('Crew invites')).toBeHidden();
    await fo.getByRole('link', { name: /KPAO.*KSQL/ }).first().click();
    await expect(fo.getByText('First officer (SIC) · In their logbook')).toBeVisible();
    await expect(fo.getByText('Captain (PIC) · Logged it')).toBeVisible();

    await captain.reload();
    await expect(captain.getByText('First officer (SIC) · In their logbook')).toBeVisible();
    await expect(captain.getByRole('img', { name: `fo${stamp}` })).toBeVisible();
});
