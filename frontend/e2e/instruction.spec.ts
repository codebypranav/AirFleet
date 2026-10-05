import { expect, test } from '@playwright/test';
import { PASSWORD, logFlight, register } from './helpers';

test('an instructor signs a lesson, and editing it invalidates the signature', async ({ browser }) => {
    const stamp = Date.now();
    const cfi = await (await browser.newContext()).newPage();
    const student = await (await browser.newContext()).newPage();

    // Any pilot can instruct once they add a certificate to their profile.
    await register(cfi, `cfi${stamp}`);
    await cfi.goto('/profile');
    await cfi.getByLabel('First name').fill('Carol');
    await cfi.getByLabel('Last name').fill('Fly');
    await cfi.getByLabel('Certificate number').fill('1234567cfi');
    await cfi.getByRole('button', { name: 'Save profile' }).click();
    await expect(cfi.getByText('Profile saved.')).toBeVisible();

    await register(student, `student${stamp}`);
    await logFlight(student, { from: 'KPAO', to: 'KSQL', reg: 'N172SP', day: '2026-02-03', dual: '1:30' });
    const lessonUrl = student.url();
    await expect(student.getByText('Not signed yet.')).toBeVisible();

    await student.goto('/instruction');
    await student.getByLabel('Username or email').fill(`cfi${stamp}@example.com`);
    await student.getByRole('button', { name: 'Send invitation' }).click();
    await expect(student.getByText(`Invitation sent to cfi${stamp}`)).toBeVisible();

    await cfi.goto('/instruction');
    await expect(cfi.getByText('Invitations for you')).toBeVisible();
    await cfi.getByRole('button', { name: 'Accept' }).click();
    await cfi.getByRole('link', { name: '1 to sign' }).click();
    await expect(cfi.getByText('KPAO → KSQL')).toBeVisible();
    await cfi.getByText(/I, Carol Fly, certificate 1234567CFI, gave student\d+ 1:30 of flight instruction/).click();
    await cfi.getByLabel('Your password').fill(PASSWORD);
    await cfi.getByRole('button', { name: 'Sign lesson' }).click();
    await expect(cfi.getByText('Instructor-verified')).toBeVisible();

    await student.goto(lessonUrl);
    await expect(student.getByText('Instructor-verified')).toBeVisible();
    await student.getByRole('link', { name: 'Edit' }).click();
    await expect(student.getByText('Carol Fly signed this entry.')).toBeVisible();
    await student.getByLabel('Dual received').fill('1:00');
    await student.getByRole('button', { name: 'Save changes' }).click();
    await expect(student.getByText('Signature invalidated').first()).toBeVisible();
    await expect(student.getByText('Changed since signing: Dual received.')).toBeVisible();

    // The instructor sees it waiting again.
    await cfi.goto('/instruction');
    await expect(cfi.getByRole('link', { name: '1 to sign' })).toBeVisible();
});
