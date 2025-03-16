export interface Flight {
    id: number;
    departure_time: string;
    arrival_time: string;
    total_time: string;
    departure_airport: string;
    arrival_airport: string;
    registration_number: string;
    aircraft_condition: string;
    distance: number;
    notes?: string;
    generated_narrative?: string;
    photo?: string;
}