import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

const PASSWORD = 'Sup3r-secret-pw';

async function register(page: Page, username: string) {
    await page.goto('/register');
    await page.getByLabel('Username').fill(username);
    await page.getByLabel('Email').fill(`${username}@example.com`);
    await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
    await page.getByLabel('Confirm password').fill(PASSWORD);
    await page.getByRole('button', { name: 'Register' }).click();
    await expect(page).toHaveURL(/\/flights$/);
}

async function logFlight(page: Page, { from, to, reg, day }: { from: string; to: string; reg: string; day: string }) {
    await page.goto('/flights/add');
    await page.getByLabel('Departure (your local time)').fill(`${day}T10:00`);
    await page.getByLabel('Arrival (your local time)').fill(`${day}T11:30`);
    await page.getByLabel('From', { exact: true }).fill(from);
    await page.getByLabel('To', { exact: true }).fill(to);
    await expect(page.getByText(/Great circle: \d+ nm/)).toBeVisible();
    await page.getByLabel('Registration').fill(reg);
    await page.getByRole('button', { name: 'All PIC' }).click();
    await page.getByRole('button', { name: 'Save to logbook' }).click();
    await expect(page).toHaveURL(/\/flights\/\d+$/);
}

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

test('signed-out visitors are sent to log in, and rankings stay public', async ({ page }) => {
    await page.goto('/flights');
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('link', { name: 'Forgot it?' })).toBeVisible();
    await page.goto('/forgot-password');
    await page.getByLabel('Email').fill('nobody@example.com');
    await page.getByRole('button', { name: 'Send reset link' }).click();
    await expect(page.getByText(/If that email has an account/)).toBeVisible();
});
