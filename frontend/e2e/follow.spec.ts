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

test('a follower likes and comments, the pilot is notified and replies', async ({ browser }) => {
    const stamp = Date.now();
    const amy = await (await browser.newContext()).newPage();
    const fan = await (await browser.newContext()).newPage();
    await register(amy, `amy${stamp}`);
    await register(fan, `fan${stamp}`);

    await amy.goto('/profile');
    await amy.getByLabel('Public profile').check();
    await amy.getByRole('button', { name: 'Save profile' }).click();
    await logFlight(amy, { from: 'KPAO', to: 'KSQL', reg: 'N172SP', day: '2026-01-05' });

    await fan.goto(`/pilots/amy${stamp}`);
    await fan.getByRole('button', { name: 'Follow' }).click();
    await expect(fan.getByRole('button', { name: 'Unfollow' })).toBeVisible();
    await fan.goto('/following');
    await fan.getByRole('button', { name: 'Like' }).click();
    await expect(fan.getByRole('button', { name: 'Unlike' })).toHaveAttribute('aria-pressed', 'true');
    await fan.getByRole('button', { name: 'Comment', exact: true }).click();
    await fan.getByLabel('Add a comment').fill('Nice approach');
    await fan.getByRole('button', { name: 'Send' }).click();
    await expect(fan.getByText('Nice approach')).toBeVisible();

    await amy.goto('/flights');
    await expect(amy.getByRole('link', { name: 'Notifications, 3 unread' })).toBeVisible();
    await amy.getByRole('link', { name: 'Notifications, 3 unread' }).click();
    await expect(amy.getByText('liked your flight KPAO → KSQL')).toBeVisible();
    await amy.getByRole('link', { name: /commented on your flight/ }).click();
    await expect(amy).toHaveURL(/\/flights\/\d+$/);
    await amy.getByRole('button', { name: 'Reply' }).click();
    await amy.getByLabel('Write a reply').fill('Thanks');
    await amy.getByRole('button', { name: 'Send' }).first().click();
    await expect(amy.getByText(`amy${stamp}Thanks`)).toBeVisible();

    await fan.goto('/notifications');
    await expect(fan.getByText(/replied to your comment on a flight KPAO → KSQL/)).toBeVisible();
    await fan.getByRole('link', { name: /replied to your comment/ }).click();
    await expect(fan).toHaveURL(/\/following\?flight=\d+$/);
    await expect(fan.getByText(`amy${stamp}Thanks`)).toBeVisible();
});
