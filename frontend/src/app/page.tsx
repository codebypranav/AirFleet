'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';

// Use dynamic import for Three.js components to avoid SSR issues
const RunwayAnimation = dynamic(() => import('@/components/RunwayAnimation'), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-black" />
});

export default function Home() {
  const [carouselIndex, setCarouselIndex] = useState(0);
  const useCases = [
    { title: 'Flight Tracking', description: 'Detailed logs of your flights with route visualization and stats.' },
    { title: 'Performance Analysis', description: 'Track your performance metrics across flights to identify improvement areas.' },
    { title: 'Logbook Management', description: 'Digital logbook that meets FAA requirements with automatic calculations.' },
    { title: 'Aviation Community', description: 'Connect with other pilots and share your flying experiences.' }
  ];

  // Rotate carousel every 15 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setCarouselIndex((prevIndex) => (prevIndex + 1) % useCases.length);
    }, 15000);
    
    return () => clearInterval(interval);
  }, [useCases.length]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-between relative overflow-hidden">
      {/* Runway Approach Lighting System Animation */}
      <div className="absolute inset-0 z-0">
        <RunwayAnimation />
      </div>
      
      {/* Main Content */}
      <div className="container mx-auto px-4 py-16 z-10 relative">
        {/* Header Section */}
        <div className="text-center mb-20">
          <h1 className="text-5xl font-bold mb-4">Welcome to AirFleet</h1>
          <p className="text-xl mb-8">Elevate Your Flight Experience</p>
          
          <div className="max-w-3xl mx-auto text-center">
            <p className="text-gray-300 mb-8">
              AirFleet is your modern pilot&apos;s logbook, transforming traditional flight recording with intuitive 
              digital tools, AI-driven analytics, and seamless collaboration. Easily track flights, securely store 
              memorable flight photos, and gain insightful analytics to enhance your piloting skills and 
              experience.
            </p>
            
            <div className="flex justify-center space-x-4">
              <Link href="/get-started">
                <button className="bg-white text-black py-2 px-6 rounded-md hover:bg-gray-200 transition">
                  Get Started
                </button>
              </Link>
              <Link href="/features">
                <button className="border border-white text-white py-2 px-6 rounded-md hover:bg-white hover:bg-opacity-10 transition">
                  Explore Features
                </button>
              </Link>
            </div>
          </div>
        </div>
        
        {/* Why I Love It Section */}
        <div className="bg-gray-900 bg-opacity-30 backdrop-blur-sm rounded-lg p-8 mb-20">
          <h2 className="text-3xl font-bold mb-6">Why I Love It</h2>
          
          <div className="flex flex-col md:flex-row items-center">
            <div className="md:w-1/4 mb-6 md:mb-0">
              <div className="rounded-full overflow-hidden w-32 h-32 mx-auto bg-gray-600 border-2 border-gray-400 flex items-center justify-center">
                <div className="text-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 text-gray-300 mx-auto mb-1" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-300 text-xs">Pranav Shukla</span>
                </div>
              </div>
            </div>
            <div className="md:w-3/4 md:pl-8">
              <p className="text-gray-300 mb-4">
                As a passionate flight simmer, I&apos;ve always wanted a comprehensive tool to merge my passion for 
                aviation with detailed analytics and modern design. AirFleet brings my enthusiasm for aviation 
                simulation into real-world practicality, making it easy and enjoyable to document my virtual flight 
                experiences and gain insights into my flying habits.
              </p>
              <p className="font-medium">— Pranav Shukla, Aviation Enthusiast & Simmer</p>
            </div>
          </div>
        </div>
        
        {/* Why Pilots Love AirFleet Section */}
        <div className="bg-gray-900 bg-opacity-30 backdrop-blur-sm rounded-lg p-8 mb-20">
          <h2 className="text-3xl font-bold mb-10">Why Pilots Love AirFleet</h2>
          
          <div className="flex flex-col md:flex-row items-center">
            <div className="md:w-1/4 mb-6 md:mb-0 order-1 md:order-2">
              <div className="rounded-full overflow-hidden w-32 h-32 mx-auto bg-gray-600 border-2 border-gray-400 flex items-center justify-center">
                <div className="text-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 text-gray-300 mx-auto mb-1" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-300 text-xs">Capt. John Smith</span>
                </div>
              </div>
            </div>
            <div className="md:w-3/4 md:pr-8 order-2 md:order-1">
              <p className="text-gray-300 mb-4">
                &quot;AirFleet has completely transformed how I maintain my logbook. The ability to analyze trends in my 
                flying hours and visualize routes has given me insights I never had before. The photo organization 
                feature is a game-changer for documenting memorable flights.&quot;
              </p>
              <p className="font-medium">— Captain John Smith, Commercial Pilot with 5,000+ hours</p>
            </div>
          </div>
        </div>
        
        {/* Use Cases Carousel */}
        <div className="bg-gray-900 bg-opacity-30 backdrop-blur-sm rounded-lg p-8 mb-20">
          <h2 className="text-3xl font-bold mb-10">How Pilots Use AirFleet</h2>
          
          <div className="flex flex-col items-center">
            <div className="w-full max-w-2xl transition-all duration-500">
              <h3 className="text-2xl font-medium mb-4">{useCases[carouselIndex].title}</h3>
              <p className="text-gray-300 mb-6">{useCases[carouselIndex].description}</p>
              
              <div className="flex justify-center space-x-2 mt-6">
                {useCases.map((_, index) => (
                  <button 
                    key={index}
                    className={`w-3 h-3 rounded-full ${index === carouselIndex ? 'bg-white' : 'bg-gray-600'}`}
                    onClick={() => setCarouselIndex(index)}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
        
        {/* Modern Logbooks Section */}
        <div className="bg-gray-900 bg-opacity-30 backdrop-blur-sm rounded-lg p-8 mb-20">
          <h2 className="text-3xl font-bold mb-6">Modern Logbooks for Modern Pilots</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-gray-800 bg-opacity-50 p-6 rounded-lg">
              <h3 className="text-xl font-medium mb-4">Digital First</h3>
              <p className="text-gray-300">
                Designed for the modern cockpit, AirFleet works online and offline, syncing across all your devices.
              </p>
            </div>
            
            <div className="bg-gray-800 bg-opacity-50 p-6 rounded-lg">
              <h3 className="text-xl font-medium mb-4">AI-Powered Analytics</h3>
              <p className="text-gray-300">
                Get insights into your flying patterns and receive personalized recommendations to enhance your skills.
              </p>
            </div>
            
            <div className="bg-gray-800 bg-opacity-50 p-6 rounded-lg">
              <h3 className="text-xl font-medium mb-4">FAA Compliant</h3>
              <p className="text-gray-300">
                Maintains all required logbook details while adding the modern features traditional logbooks lack.
              </p>
            </div>
          </div>
        </div>
        
        {/* Coming Soon Section */}
        <div className="bg-gray-900 bg-opacity-30 backdrop-blur-sm rounded-lg p-8 mb-20">
          <h2 className="text-3xl font-bold mb-6">Collaborate with Fellow Pilots</h2>
          
          <p className="text-gray-300 mb-8 text-center max-w-3xl mx-auto">
            Coming soon: Share routes, exchange tips, and build a community of like-minded aviation enthusiasts. 
            Stay tuned for our collaboration features launching this summer.
          </p>
          
          <div className="text-center">
            <Link href="/updates">
              <button className="border border-white text-white py-2 px-6 rounded-md hover:bg-white hover:bg-opacity-10 transition">
                Get Notified
              </button>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}