import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
    variable: "--font-geist-sans",
    subsets: ["latin"],
});

const geistMono = Geist_Mono({
    variable: "--font-geist-mono",
    subsets: ["latin"],
});

const fraunces = Fraunces({
    variable: "--font-fraunces",
    subsets: ["latin"],
    axes: ["SOFT", "opsz"],
});

export const metadata: Metadata = {
    title: "AirFleet",
    description: "Your modern pilot's logbook — AI-driven insights and more.",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        // Font variables live on <html> so the theme tokens in globals.css can resolve them at :root.
        <html lang="en" className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable}`}>
            <body className="antialiased">
                {children}
            </body>
        </html>
    );
}
