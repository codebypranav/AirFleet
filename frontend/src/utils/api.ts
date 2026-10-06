import Cookies from 'js-cookie';
import type {
    Achievement, Aircraft, Airport, Currency, Endorsement, EndorsementKind, Flight, FlightPlanDraft, ImportResult,
    InstructorLink, Paginated, Profile, PublicFlight, PublicPilot, QuickLogDraft, RouteMapData, Signature, Stats, StudentFlight,
} from '@/types/flight';

const ORIGIN = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '').replace(/\/api$/, '');
export const API_ORIGIN = ORIGIN;
export const API_BASE = `${ORIGIN}/api`;

const COOKIE_OPTIONS = { secure: true, sameSite: 'strict' } as const;

export function saveTokens(tokens: { access: string; refresh: string }) {
    Cookies.set('accessToken', tokens.access, COOKIE_OPTIONS);
    Cookies.set('refreshToken', tokens.refresh, COOKIE_OPTIONS);
}

export function clearTokens() {
    Cookies.remove('accessToken');
    Cookies.remove('refreshToken');
}

export const isLoggedIn = () => Boolean(Cookies.get('accessToken'));

/** Turns DRF's error shapes ({error}, {detail}, {errors: {field: [..]}}, {field: [..]}) into one sentence. */
export function errorMessage(data: unknown, fallback = 'Something went wrong. Please try again.'): string {
    if (!data) return fallback;
    if (typeof data === 'string') return data;
    if (Array.isArray(data)) return data.length ? errorMessage(data[0], fallback) : fallback;
    if (typeof data === 'object') {
        const record = data as Record<string, unknown>;
        if (typeof record.error === 'string') return record.error;
        if (typeof record.detail === 'string') return record.detail;
        if (record.errors) return errorMessage(record.errors, fallback);
        const [field, value] = Object.entries(record).find(([key]) => key !== 'status' && key !== 'message') ?? [];
        if (field) {
            const message = errorMessage(value, fallback);
            return field === 'non_field_errors' ? message : `${field.replace(/_/g, ' ')}: ${message}`;
        }
    }
    return fallback;
}

export class ApiError extends Error {
    constructor(public status: number, public data: unknown) {
        super(errorMessage(data, `Request failed (${status})`));
    }
}

let refreshing: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
    const refresh = Cookies.get('refreshToken');
    if (!refresh) return false;
    refreshing ??= fetch(`${API_BASE}/token/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
    })
        .then(async (res) => {
            if (!res.ok) return false;
            const data = await res.json();
            saveTokens({ access: data.access, refresh: data.refresh ?? refresh });
            return true;
        })
        .catch(() => false)
        .finally(() => {
            refreshing = null;
        });
    return refreshing;
}

function sendToLogin() {
    clearTokens();
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        // Plain module code, so no router here; a full load also drops any stale client state.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign('/login');
    }
}

type Options = RequestInit & { auth?: boolean; json?: unknown };

/** fetch against the API. Authenticated by default; retries once after refreshing an expired token. */
export async function apiFetch(endpoint: string, { auth = true, json, ...options }: Options = {}, retried = false): Promise<Response> {
    const headers = new Headers(options.headers);
    if (json !== undefined) headers.set('Content-Type', 'application/json');
    if (auth) {
        const token = Cookies.get('accessToken');
        if (!token && !(await refreshAccessToken())) {
            sendToLogin();
            throw new ApiError(401, { error: 'Please log in again.' });
        }
        headers.set('Authorization', `Bearer ${Cookies.get('accessToken')}`);
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
        body: json !== undefined ? JSON.stringify(json) : options.body,
    });

    if (response.status === 401 && auth) {
        if (!retried && (await refreshAccessToken())) {
            return apiFetch(endpoint, { auth, json, ...options }, true);
        }
        sendToLogin();
    }
    if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new ApiError(response.status, data);
    }
    return response;
}

export async function apiJson<T>(endpoint: string, options?: Options): Promise<T> {
    const response = await apiFetch(endpoint, options);
    return response.status === 204 ? (undefined as T) : response.json();
}

const query = (params: Record<string, string | number | undefined>) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== '') search.set(key, String(value));
    });
    const text = search.toString();
    return text ? `?${text}` : '';
};

export type FlightFilters = { from?: string; to?: string; airport?: string; aircraft?: string; q?: string; simulator?: string; draft?: string };

export const getFlights = (params: FlightFilters & { page?: number; page_size?: number } = {}) =>
    apiJson<Paginated<Flight>>(`/flights/${query(params)}`);
export const getFlight = (id: number | string) => apiJson<Flight>(`/flights/${id}/`);
export const addFlight = (data: FormData) => apiJson<Flight>('/flights/', { method: 'POST', body: data });
export const updateFlight = (id: number | string, data: FormData) => apiJson<Flight>(`/flights/${id}/`, { method: 'PATCH', body: data });
export const deleteFlight = (id: number | string) => apiJson<void>(`/flights/${id}/`, { method: 'DELETE' });

export async function downloadExport(filters: FlightFilters = {}) {
    const response = await apiFetch(`/flights/export/${query(filters)}`);
    const blob = await response.blob();
    const name = response.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] ?? 'airfleet-logbook.csv';
    const url = URL.createObjectURL(blob);
    const link = Object.assign(document.createElement('a'), { href: url, download: name });
    link.click();
    URL.revokeObjectURL(url);
}

export const importFlights = (file: File) => {
    const body = new FormData();
    body.append('file', file);
    return apiJson<ImportResult>('/flights/import/', { method: 'POST', body });
};

/** Reads a flight plan PDF (SimBrief OFP or ICAO flight plan) into a draft flight. The server doesn't keep the file. */
export const readFlightPlan = (file: File) => {
    const body = new FormData();
    body.append('file', file);
    return apiJson<FlightPlanDraft>('/flights/from-plan/', { method: 'POST', body });
};

/** Whether quick log has an AI provider configured; the form hides it when not. */
export const getQuickLogStatus = () => apiJson<{ enabled: boolean }>('/flights/quick-log/');

/** Reads a plain-text description of a flight into form fields. `now` is the pilot's local time, for "today" and "this morning". */
export const readQuickLog = (text: string, now: string) =>
    apiJson<QuickLogDraft>('/flights/quick-log/', { method: 'POST', json: { text, now } });

export const getStats = (filters: FlightFilters = {}) => apiJson<Stats>(`/stats/${query(filters)}`);
export const getRoutes = () => apiJson<RouteMapData>('/stats/routes/');
export const getCurrency = () => apiJson<Currency[]>('/currency/');
export const getAchievements = () => apiJson<Achievement[]>('/achievements/');

export const getFleet = () => apiJson<Aircraft[]>('/aircraft/');
export const getAircraft = (id: number | string) => apiJson<Aircraft>(`/aircraft/${id}/`);
export const addAircraft = (data: Partial<Aircraft>) => apiJson<Aircraft>('/aircraft/', { method: 'POST', json: data });
export const updateAircraft = (id: number | string, data: Partial<Aircraft>) =>
    apiJson<Aircraft>(`/aircraft/${id}/`, { method: 'PATCH', json: data });
export const deleteAircraft = (id: number | string) => apiJson<void>(`/aircraft/${id}/`, { method: 'DELETE' });
export const logMaintenance = (id: number | string, data: { performed_at?: string; annual_due?: string }) =>
    apiJson<Aircraft>(`/aircraft/${id}/maintenance/`, { method: 'POST', json: data });

export const searchAirports = (q: string) => apiJson<Airport[]>(`/airports/${query({ q, limit: 8 })}`, { auth: false });
export const getAirport = (code: string) => apiJson<Airport>(`/airports/${encodeURIComponent(code)}/`, { auth: false });
export const getMetar = (airport: string, time?: string) =>
    apiJson<{ airport: string; raw: string; observed_at: string | null; flight_category: string | null }>(`/weather/${query({ airport, time })}`);
export const getSimbrief = (username: string) => apiJson<Partial<Flight> & { aircraft_type?: string }>(`/simbrief/${query({ username })}`);

export const getProfile = () => apiJson<Profile>('/me/');
export const updateProfile = (data: Partial<Profile>) => apiJson<Profile>('/me/', { method: 'PATCH', json: data });
export const changePassword = (current_password: string, new_password: string) =>
    apiJson<{ access: string; refresh: string }>('/me/password/', { method: 'POST', json: { current_password, new_password } });
export const deleteAccount = (confirm: string, password: string) =>
    apiJson<void>('/me/', { method: 'DELETE', json: { confirm, password } });
export const requestPasswordReset = (email: string) =>
    apiJson<{ detail: string }>('/password-reset/', { method: 'POST', json: { email }, auth: false });
export const confirmPasswordReset = (uid: string, token: string, password: string) =>
    apiJson<{ detail: string }>('/password-reset/confirm/', { method: 'POST', json: { uid, token, password }, auth: false });

export const getInstructorLinks = () => apiJson<InstructorLink[]>('/instruction/links/');
export const inviteToLink = (invitee: string, invitee_role: 'instructor' | 'student') =>
    apiJson<InstructorLink>('/instruction/links/', { method: 'POST', json: { invitee, invitee_role } });
export const acceptLink = (id: number) => apiJson<InstructorLink>(`/instruction/links/${id}/accept/`, { method: 'POST' });
export const endLink = (id: number) => apiJson<void>(`/instruction/links/${id}/`, { method: 'DELETE' });
export const getStudentFlights = (linkId: number | string, params: { unsigned?: string; page?: number; page_size?: number } = {}) =>
    apiJson<Paginated<StudentFlight>>(`/instruction/links/${linkId}/flights/${query(params)}`);
export const signFlight = (flightId: number, data: { remarks: string; agree: boolean; password: string }) =>
    apiJson<Signature>(`/instruction/flights/${flightId}/sign/`, { method: 'POST', json: data });
export const withdrawSignature = (id: number, data: { reason: string; password: string }) =>
    apiJson<Signature>(`/instruction/signatures/${id}/withdraw/`, { method: 'POST', json: data });

export const getEndorsementKinds = () => apiJson<EndorsementKind[]>('/instruction/endorsements/kinds/');
export const getMyEndorsements = () => apiJson<Endorsement[]>('/instruction/endorsements/');
export const getStudentEndorsements = (linkId: number | string) => apiJson<Endorsement[]>(`/instruction/links/${linkId}/endorsements/`);
export type EndorsementInput = {
    kind: string; title: string; text: string; aircraft: string; given_on: string; agree: boolean; password: string;
};
export const giveEndorsement = (linkId: number | string, data: EndorsementInput) =>
    apiJson<Endorsement>(`/instruction/links/${linkId}/endorsements/`, { method: 'POST', json: data });
export const withdrawEndorsement = (id: number, data: { reason: string; password: string }) =>
    apiJson<Endorsement>(`/instruction/endorsements/${id}/withdraw/`, { method: 'POST', json: data });

export const getPublicPilot = (username: string) => apiJson<PublicPilot>(`/pilots/${encodeURIComponent(username)}/`, { auth: false });
export const getPublicFlight = (id: number | string) => apiJson<PublicFlight>(`/public/flights/${id}/`, { auth: false });
