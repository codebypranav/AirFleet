import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { PASSWORD, logFlight, register } from './helpers';

test('a pilot logs, edits, shares, exports and deletes flights', async ({ page, browser }) => {
    const username = `e2e${Date.now()}`;
    await register(page, username);
    await expect(page.getByText('A blank first page')).toBeVisible();

    // Add: distance and block time are worked out, airport names come from the bundled data.
    await logFlight(page, { from: 'KJFK', to: 'KBOS', reg: 'n172sp', day: '2026-01-05' });
    await expect(page.getByRole('heading', { name: 'KJFK → KBOS' })).toBeVisible();
    await expect(page.getByText('John F. Kennedy International Airport to Boston Logan International Airport')).toBeVisible();
    await expect(page.getByText(/^16\d nm$/)).toBeVisible();
    await expect(page.getByText('1h 30m').first()).toBeVisible();

    // Edit
    await page.getByRole('link', { name: 'Edit' }).click();
    await page.getByLabel('Notes').fill('Gusty crosswind on 4R');
    await page.getByLabel('Night', { exact: true }).fill('0:45');
    await page.getByRole('button', { name: 'Save changes' }).click();
    await expect(page.getByText('Gusty crosswind on 4R')).toBeVisible();
    await expect(page.getByText('45m').first()).toBeVisible();

    await logFlight(page, { from: 'KBOS', to: 'KJFK', reg: 'N172SP', day: '2026-01-06' });

    // Logbook: totals, filters
    await page.goto('/flights');
    await expect(page.getByText('3 h', { exact: true })).toBeVisible();
    await page.getByText('Filter flights').click();
    await page.getByLabel('Search notes & stories').fill('crosswind');
    await page.getByRole('button', { name: 'Apply filters' }).click();
    await expect(page.getByText('1 match')).toBeVisible();
    await expect(page.locator('ol > li')).toHaveCount(1);

    // Fleet: one aircraft from both flights
    await page.goto('/aircraft');
    await expect(page.getByText('N172SP')).toBeVisible();
    await page.getByText('N172SP').click();
    await expect(page.getByText('3 / 100 h')).toBeVisible();
    await page.getByRole('button', { name: 'Log maintenance' }).click();
    await expect(page.getByText('0 / 100 h')).toBeVisible();

    // Stats and achievements
    await page.goto('/stats');
    await expect(page.getByText('Passengers (day)')).toBeVisible();
    await expect(page.getByText('First page')).toBeVisible();
    await expect(page.getByRole('img', { name: /Map of 2 routes between 2 airports/ })).toBeVisible();

    // Export a CSV and import it into a second account
    await page.goto('/flights');
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export CSV' }).click();
    const download = await downloadPromise;
    const csv = readFileSync((await download.path())!, 'utf8');
    expect(csv.split('\n')[0]).toContain('departure_airport');

    // Profile: make it public, then view it signed out
    await page.goto('/profile');
    await page.getByLabel('About you').fill('Weekend flyer');
    await page.getByLabel('Public profile').check();
    await page.getByRole('button', { name: 'Save profile' }).click();
    await expect(page.getByText('Profile saved.')).toBeVisible();

    const guest = await browser.newPage();
    await guest.goto(`/pilots/${username}`);
    await expect(guest.getByRole('heading', { name: username })).toBeVisible();
    await expect(guest.getByText('Weekend flyer')).toBeVisible();
    await guest.getByRole('link', { name: /KJFK/ }).first().click();
    await expect(guest.getByRole('link', { name: `Flown by ${username}` })).toBeVisible();
    await expect(guest.getByText('Gusty crosswind')).toHaveCount(0);
    await guest.close();

    // Import into a fresh account
    await page.getByRole('button', { name: 'Log out' }).click();
    await register(page, `${username}b`);
    await page.goto('/flights/import');
    await page.locator('input[type=file]').setInputFiles({ name: 'logbook.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
    await page.getByRole('button', { name: 'Import flights' }).click();
    await expect(page.getByText('Imported 2 flights from an AirFleet CSV.')).toBeVisible();

    // Delete
    await page.goto('/flights');
    await page.locator('ol > li a').first().click();
    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: 'Delete' }).click();
    await expect(page).toHaveURL(/\/flights$/);
    await expect(page.locator('ol > li')).toHaveCount(1);
});

test('a pilot starts a draft from a flight plan PDF and logs it after the flight', async ({ page }) => {
    await register(page, `e2eplan${Date.now()}`);
    await page.goto('/flights/add');
    await page.locator('#flight_plan_pdf').setInputFiles('e2e/fixtures/simbrief-ofp.pdf');
    await expect(page.getByText(/Loaded CGXLR, LFBO → CYUL/)).toBeVisible();
    await expect(page.getByLabel('Registration')).toHaveValue('C-GXLR');
    await expect(page.getByLabel('Distance (nm)')).toHaveValue('3312');
    await expect(page.getByText('8h 30m')).toBeVisible();
    await page.getByRole('button', { name: 'Save draft' }).click();

    await expect(page).toHaveURL(/\/flights\/\d+$/);
    await expect(page.getByRole('link', { name: /Draft · add the actual times/ })).toBeVisible();
    await page.goto('/flights');
    await expect(page.getByText(/· Draft/)).toBeVisible();
    await expect(page.getByText('0 h', { exact: true })).toBeVisible();

    // After the flight: untick Draft to put it in the logbook.
    await page.locator('ol > li a').first().click();
    await page.getByRole('link', { name: 'Edit' }).click();
    await page.getByLabel(/^Draft/).uncheck();
    await page.getByRole('button', { name: 'Save to logbook' }).click();
    await expect(page.getByRole('link', { name: /Draft · add the actual times/ })).toHaveCount(0);
    await page.goto('/flights');
    await expect(page.getByText('8.5 h', { exact: true })).toBeVisible();
});

test('signed-out visitors are sent to log in, and rankings stay public', async ({ page }) => {
    await page.goto('/flights');
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('link', { name: 'Forgot it?' })).toBeVisible();
    await page.goto('/forgot-password');
    await page.getByLabel('Email').fill('nobody@example.com');
    await page.getByRole('button', { name: 'Send reset link' }).click();
    await expect(page.getByText(/If that email has an account/)).toBeVisible();
});

test('a pilot deletes their account', async ({ page }) => {
    const username = `gone${Date.now()}`;
    await register(page, username);
    await logFlight(page, { from: 'KJFK', to: 'KBOS', reg: 'n172sp', day: '2026-01-05' });

    await page.goto('/profile');
    const button = page.getByRole('button', { name: 'Delete account' });
    await expect(button).toBeDisabled();
    await page.getByLabel(`Type ${username} to confirm`).fill(username);
    await page.getByLabel('Password', { exact: true }).fill('wrong-password');
    page.once('dialog', (dialog) => dialog.accept());
    await button.click();
    await expect(page.getByText('Your password is incorrect.')).toBeVisible();

    await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
    page.once('dialog', (dialog) => dialog.accept());
    await button.click();
    await expect(page).not.toHaveURL(/\/profile$/);

    await page.goto('/login');
    await page.getByLabel('Username').fill(username);
    await page.getByLabel('Password').fill(PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.locator('p.alert-error')).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
});

test('the privacy notice is public', async ({ page }) => {
    await page.goto('/privacy');
    await expect(page.getByRole('heading', { name: 'Your data in AirFleet' })).toBeVisible();
    await expect(page.getByText(/only when you ask for a story/)).toBeVisible();
});
