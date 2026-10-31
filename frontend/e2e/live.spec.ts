import { expect, test } from '@playwright/test';
import { register } from './helpers';

test.afterEach(async ({ browser }) => {
    await Promise.all(browser.contexts().map((context) => context.close()));
});

test('a captain starts a flight, the first officer sees it live, and the captain lands it', async ({ browser }) => {
    const stamp = Date.now();
    const captain = await (await browser.newContext()).newPage();
    const fo = await (await browser.newContext()).newPage();
    await register(fo, `fo${stamp}`);
    await register(captain, `cpt${stamp}`);

    await captain.goto('/flights');
    await captain.getByRole('link', { name: 'Start flight' }).click();
    await captain.getByLabel('From').fill('KPAO');
    await captain.getByLabel('To', { exact: true }).fill('KSQL');
    await captain.getByLabel('Aircraft registration').fill('N172SP');
    await captain.getByLabel('Estimated time en route').fill('0:45');
    await captain.getByRole('button', { name: 'Add crewmate' }).click();
    await captain.getByLabel("Crewmate's username").fill(`fo${stamp}`);
    await captain.getByRole('button', { name: 'Start flight' }).click();
    await expect(captain.getByText('You are flying KPAO → KSQL')).toBeVisible();

    await fo.goto('/stats');
    await expect(fo.getByText(`cpt${stamp} is flying KPAO → KSQL`)).toBeVisible();

    await captain.getByRole('button', { name: 'Land', exact: true }).click();
    await expect(captain).toHaveURL(/\/flights\/\d+\/edit$/);
    await expect(captain.getByText('You are flying')).toBeHidden();

    await fo.reload();
    await expect(fo.getByText(`cpt${stamp} is flying`)).toBeHidden();
});
