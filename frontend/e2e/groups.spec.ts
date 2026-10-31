import { expect, test } from '@playwright/test';
import { register } from './helpers';

test.afterEach(async ({ browser }) => {
    await Promise.all(browser.contexts().map((context) => context.close()));
});

test('a pilot starts a group, another joins and wears the badge', async ({ browser }) => {
    const stamp = Date.now();
    const owner = await (await browser.newContext()).newPage();
    const pilot = await (await browser.newContext()).newPage();
    const name = `Ridge Soarers ${stamp}`;

    await register(owner, `owner${stamp}`);
    await owner.getByRole('button', { name: 'Community' }).click();
    await owner.getByRole('link', { name: 'Groups' }).click();
    await owner.getByLabel('Group name').fill(name);
    await owner.getByRole('button', { name: 'Create group' }).click();
    await expect(owner.getByRole('heading', { name })).toBeVisible();
    await expect(owner.getByText('Community · Community group')).toBeVisible();

    await register(pilot, `pilot${stamp}`);
    await pilot.goto('/groups');
    await pilot.getByLabel('Search groups').fill(`Soarers ${stamp}`);
    await pilot.getByRole('button', { name: 'Search' }).click();
    await pilot.getByRole('link', { name: new RegExp(name) }).click();
    await pilot.getByRole('button', { name: 'Join group' }).click();
    await expect(pilot.getByRole('button', { name: 'Leave group' })).toBeVisible();
    await expect(pilot.getByText('Members · 2')).toBeVisible();

    await pilot.goto('/profile');
    await expect(pilot.getByRole('link', { name })).toBeVisible();
});
