import Cookies from 'js-cookie';

// Use environment variable with fallback
const BASE_URL = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api`;

export async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
    const accessToken = Cookies.get('accessToken');
    
    if (!accessToken) {
        console.error('No access token found in cookies. User may need to log in again.');
        throw new Error('No access token found');
    }

    console.log(`Making API request to: ${BASE_URL}${endpoint}`);
    
    const headers = {
        ...options.headers,
        'Authorization': `Bearer ${accessToken}`,
    };

    console.log('Request headers:', headers);
    console.log('Request options:', { 
        method: options.method || 'GET',
        credentials: 'include',
        body: options.body ? '(Request has body)' : undefined
    });

    try {
        const response = await fetch(`${BASE_URL}${endpoint}`, {
            ...options,
            headers,
            credentials: 'include',
        });

        console.log('Response status:', response.status);
        console.log('Response headers:', response.headers);

        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
                console.error('Error response data:', errorData);
            } catch (parseError) {
                console.error('Could not parse error response as JSON:', parseError);
                errorData = { message: 'Unknown error occurred, could not parse response' };
            }
            throw new Error(JSON.stringify(errorData));
        }

        return response;
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

export async function getFlights() {
    const response = await fetchWithAuth('/flights/');
    return response.json();
}

export async function addFlight(flightData: FormData) {
    console.log('Sending flight data:', Object.fromEntries(flightData.entries()));
    const response = await fetchWithAuth('/flights/', {
        method: 'POST',
        body: flightData,
        headers: {},
    });
    return response.json();
}