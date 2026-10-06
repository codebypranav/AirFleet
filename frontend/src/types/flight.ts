export interface Airport {
    code: string;
    name: string;
    city: string;
    country: string;
    lat: number;
    lon: number;
    size: string;
}

export interface Flight {
    id: number;
    aircraft: number | null;
    aircraft_type: string;
    departure_time: string;
    arrival_time: string;
    total_time: string;
    departure_airport: string;
    arrival_airport: string;
    departure_info: Airport | null;
    arrival_info: Airport | null;
    departure_gate: string;
    arrival_gate: string;
    registration_number: string;
    aircraft_condition: string;
    distance: number;
    flight_plan: string;
    notes: string;
    photo?: string | null;
    pic_time: string;
    sic_time: string;
    dual_received_time: string;
    night_time: string;
    instrument_time: string;
    simulated_instrument_time: string;
    day_landings: number;
    night_landings: number;
    approaches: number;
    cross_country: boolean;
    is_simulator: boolean;
    /** Started from a flight plan and not flown yet; left out of totals, currency and rankings. */
    is_draft: boolean;
    weather_conditions: string;
    signature: Signature | null;
    created_at: string;
    updated_at: string;
}

/** Fields shared by signatures and endorsements: who gave it, and whether they took it back. */
interface InstructorRecord {
    id: number;
    instructor_name: string;
    certificate_number: string;
    certificate_expires: string | null;
    signed_at: string;
    withdrawn_at: string | null;
    withdrawal_reason: string;
    /** True for the instructor who gave it, until they withdraw it. */
    withdrawable: boolean;
}

/** An instructor's sign-off. "invalidated" once a signed field of the flight is edited. */
export interface Signature extends InstructorRecord {
    statement: string;
    remarks: string;
    status: 'valid' | 'invalidated' | 'withdrawn';
    changed_fields: string[];
}

export interface Endorsement extends InstructorRecord {
    kind: string;
    title: string;
    regulation: string;
    text: string;
    aircraft: string;
    student: string;
    given_on: string;
    expires_on: string | null;
    status: 'current' | 'expired' | 'withdrawn';
}

/** A kind of endorsement with a starting draft; {student} and {aircraft} are blanks to fill. */
export interface EndorsementKind {
    kind: string;
    title: string;
    regulation: string;
    draft: string;
    needs_aircraft: boolean;
    validity: ['days' | 'calendar_months', number] | null;
}

export interface InstructorLink {
    id: number;
    status: 'PENDING' | 'ACTIVE';
    /** The requesting pilot's role in this link. */
    role: 'student' | 'instructor';
    other: { username: string; name: string; certificate_number?: string };
    awaiting_my_response: boolean;
    unsigned_flights: number | null;
    created_at: string;
    accepted_at: string | null;
}

/** A student's dual flight as their instructor sees it: only the fields that get signed. */
export interface StudentFlight extends Pick<Flight,
    'id' | 'departure_airport' | 'arrival_airport' | 'departure_info' | 'arrival_info' | 'departure_time' | 'arrival_time' |
    'total_time' | 'registration_number' | 'aircraft_type' | 'pic_time' | 'sic_time' | 'dual_received_time' | 'night_time' |
    'instrument_time' | 'simulated_instrument_time' | 'day_landings' | 'night_landings' | 'approaches' | 'cross_country' |
    'is_simulator' | 'signature'> {
    statement: string;
}

export interface PublicFlight {
    id: number;
    pilot: string;
    departure_airport: string;
    arrival_airport: string;
    departure_time: string;
    arrival_time: string;
    total_time: string;
    distance: number;
    registration_number: string;
    aircraft_type: string;
    photo?: string | null;
    night_time: string;
    instrument_time: string;
    day_landings: number;
    night_landings: number;
    approaches: number;
    cross_country: boolean;
    is_simulator: boolean;
    departure_info: Airport | null;
    arrival_info: Airport | null;
}

export interface Paginated<T> {
    count: number;
    next: string | null;
    previous: string | null;
    results: T[];
}

export interface Aircraft {
    id: number;
    registration: string;
    type_code: string;
    make_model: string;
    aircraft_class: string;
    notes: string;
    maintenance_interval_hours: number;
    last_maintenance_at: string | null;
    annual_due: string | null;
    grounded: boolean;
    hours_since_maintenance: number;
    maintenance_due: boolean;
    maintenance_forecast: MaintenanceForecast;
    total_flights: number;
    total_time: string | null;
}

/** Hours left until the inspection divided by the recent flying rate; see insights.maintenance_forecast. */
export interface MaintenanceForecast {
    window_days: number;
    hours_per_week: number;
    hours_remaining: number;
    inspection_due_on: string | null;
    next_due: { kind: 'inspection' | 'annual'; date: string } | null;
}

export interface Totals {
    flights: number;
    hours: number;
    distance: number;
    pic_hours: number;
    night_hours: number;
    instrument_hours: number;
    simulated_instrument_hours: number;
    landings: number;
    night_landings: number;
    approaches: number;
    cross_country_flights: number;
    simulator_flights: number;
    airframes: number;
    airports: number;
    countries: number;
}

export interface Stats {
    totals: Totals;
    by_month: { month: string; flights: number; hours: number; distance: number }[];
    top_routes: { from: string; to: string; flights: number; hours: number }[];
    top_aircraft: { registration: string; type_code: string; flights: number; hours: number }[];
}

export interface RouteMapData {
    routes: { from: string; to: string; flights: number; hours: number }[];
    airports: Airport[];
}

export interface Currency {
    key: string;
    label: string;
    rule: string;
    needed: number;
    count_in_window: number;
    expires_on: string | null;
    days_left: number;
    status: 'current' | 'expiring' | 'lapsed';
}

export interface Achievement {
    key: string;
    title: string;
    description: string;
    earned: boolean;
    earned_at?: string;
    flight_id?: number;
}

export interface Profile {
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    bio: string;
    home_airport: string;
    is_public: boolean;
    instructor_certificate_number: string;
    instructor_certificate_expires: string | null;
    date_joined: string;
}

export interface PublicPilot {
    username: string;
    bio: string;
    home_airport: string;
    member_since: string;
    stats: Totals;
    achievements: Achievement[];
    recent_flights: PublicFlight[];
    routes: RouteMapData;
}

export interface ImportResult {
    source: 'airfleet' | 'foreflight';
    created: number;
    duplicates: number;
    skipped: number;
    errors: { row: number; errors: unknown }[];
}

/** A flight plan PDF read into a draft entry; see flights/flight_plans.py. */
export interface FlightPlanDraft {
    source: 'simbrief' | 'icao';
    callsign: string;
    flight: Partial<Flight> & { aircraft_type?: string };
    warnings: string[];
}

/** A plain-text description of a flight read into new-flight form fields; see flights/quick_log.py.
 * Times are local "YYYY-MM-DDTHH:MM" and hours "H:MM", as the form's inputs take them. */
export interface QuickLogDraft {
    flight: Partial<Pick<Flight,
        | 'departure_airport' | 'arrival_airport' | 'departure_time' | 'arrival_time' | 'registration_number'
        | 'pic_time' | 'sic_time' | 'dual_received_time' | 'night_time' | 'instrument_time' | 'simulated_instrument_time'
        | 'day_landings' | 'night_landings' | 'approaches' | 'cross_country' | 'is_simulator' | 'notes'>>;
    warnings: string[];
}
