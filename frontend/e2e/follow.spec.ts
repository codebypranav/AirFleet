import { expect, test } from '@playwright/test';
import { logFlight, register } from './helpers';

test('a follower sees a public pilot fly and log, and a private pilot approves a request', async ({ browser }) => {
    const stamp = Date.now();
    const amy = await (await browser.newContext()).newPage();
    const fan = await (await browser.newContext()).newPage();
    const sam = await (await browser.newContext()).newPage();
    await register(amy, `amy${stamp}`);
    await register(fan, `fan${stamp}`);
    await register(sam, `sam${stamp}`);

    await amy.goto('/profile');
    await amy.getByLabel('Public profile').check();
    await amy.getByRole('button', { name: 'Save profile' }).click();
    await logFlight(amy, { from: 'KPAO', to: 'KSQL', reg: 'N172SP', day: '2026-01-05' });

    await fan.goto(`/pilots/amy${stamp}`);
    await fan.getByRole('button', { name: 'Follow' }).click();
    await expect(fan.getByRole('button', { name: 'Unfollow' })).toBeVisible();
    await expect(fan.getByText('1 follower')).toBeVisible();

    await amy.goto('/flights/start');
    await amy.getByLabel('From').fill('KSQL');
    await amy.getByLabel('To', { exact: true }).fill('KPAO');
    await amy.getByLabel('Aircraft registration').fill('N172SP');
    await amy.getByLabel('Estimated time en route').fill('0:30');
    await amy.getByRole('button', { name: 'Start flight' }).click();
    await expect(amy.getByText('You are flying KSQL → KPAO')).toBeVisible();

    await fan.goto('/following');
    await expect(fan.getByText(`amy${stamp} is flying KSQL → KPAO`)).toBeVisible();
    await expect(fan.getByRole('link', { name: new RegExp(`amy${stamp}.*KPAO.*KSQL`) })).toBeVisible();

    await fan.getByLabel('Username').fill(`sam${stamp}`);
    await fan.getByRole('button', { name: 'Follow', exact: true }).click();
    await expect(fan.getByText(`Request sent to sam${stamp}.`)).toBeVisible();

    await sam.goto('/profile');
    await sam.getByRole('button', { name: 'Approve' }).click();
    await expect(sam.getByText('Followers · 1 follower')).toBeVisible();
});
