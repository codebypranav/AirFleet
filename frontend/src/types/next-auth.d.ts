import "next-auth";
import "next-auth/jwt";

type AirfleetTokens = { access: string; refresh: string };

declare module "next-auth" {
    interface Session {
        airfleet: AirfleetTokens | null;
        airfleetError: string | null;
    }
}

declare module "next-auth/jwt" {
    interface JWT {
        airfleet?: AirfleetTokens;
        airfleetError?: string;
    }
}
