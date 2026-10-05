import { expect, type Page } from '@playwright/test';

export const PASSWORD = 'Sup3r-secret-pw';

export async function register(page: Page, username: string) {
    await page.goto('/register');
    await page.getByLabel('Username').fill(username);
    await page.getByLabel('Email').fill(`${username}@example.com`);
    await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
    await page.getByLabel('Confirm password').fill(PASSWORD);
    await page.getByRole('button', { name: 'Register' }).click();
    await expect(page).toHaveURL(/\/flights$/);
}

export async function logFlight(
    page: Page,
    { from, to, reg, day, dual }: { from: string; to: string; reg: string; day: string; dual?: string },
) {
    await page.goto('/flights/add');
    await page.getByLabel('Departure (your local time)').fill(`${day}T10:00`);
    await page.getByLabel('Arrival (your local time)').fill(`${day}T11:30`);
    await page.getByLabel('From', { exact: true }).fill(from);
    await page.getByLabel('To', { exact: true }).fill(to);
    await expect(page.getByText(/Great circle: \d+ nm/)).toBeVisible();
    await page.getByLabel('Registration').fill(reg);
    await page.getByRole('button', { name: 'All PIC' }).click();
    if (dual) await page.getByLabel('Dual received').fill(dual);
    await page.getByRole('button', { name: 'Save to logbook' }).click();
    await expect(page).toHaveURL(/\/flights\/\d+$/);
}
