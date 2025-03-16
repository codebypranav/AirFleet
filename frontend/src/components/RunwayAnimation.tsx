'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';

const RunwayAnimation = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create scene, camera, and renderer
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);
    scene.fog = new THREE.FogExp2(0x000000, 0.0025);

    const camera = new THREE.PerspectiveCamera(
      60, // Field of view
      window.innerWidth / window.innerHeight, // Aspect ratio
      0.1, // Near clipping plane
      5000 // Far clipping plane
    );
    camera.position.set(0, 20, 0); // Position slightly above the ground
    camera.lookAt(0, 0, -1000); // Look down the runway

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    
    // Apply a subtle blur to the renderer
    renderer.domElement.style.filter = 'blur(0.5px)';
    renderer.domElement.style.opacity = '0.75';
    
    containerRef.current.appendChild(renderer.domElement);

    // Create the runway
    const runwayGeometry = new THREE.PlaneGeometry(300, 3000);
    const runwayMaterial = new THREE.MeshBasicMaterial({ 
      color: 0x141414,
      side: THREE.DoubleSide 
    });
    const runway = new THREE.Mesh(runwayGeometry, runwayMaterial);
    runway.rotation.x = Math.PI / 2; // Rotate to be horizontal
    runway.position.z = -1500; // Position in front of the camera
    scene.add(runway);

    // Create runway edge lines
    const createLine = (x: number) => {
      const lineGeometry = new THREE.BufferGeometry();
      const linePoints = [
        new THREE.Vector3(x, 0, 0),
        new THREE.Vector3(x, 0, -3000)
      ];
      lineGeometry.setFromPoints(linePoints);
      const lineMaterial = new THREE.LineBasicMaterial({ 
        color: 0xffffff,
        opacity: 0.3,
        transparent: true
      });
      const line = new THREE.Line(lineGeometry, lineMaterial);
      scene.add(line);
    };

    // Add runway edge lines
    createLine(-150);
    createLine(150);

    // Create centerline markers (dashed line)
    const centerLinePoints = [];
    for (let z = 0; z > -3000; z -= 30) {
      centerLinePoints.push(new THREE.Vector3(0, 0, z));
      centerLinePoints.push(new THREE.Vector3(0, 0, z - 15));
    }
    
    const centerLineGeometry = new THREE.BufferGeometry().setFromPoints(centerLinePoints);
    const centerLineMaterial = new THREE.LineBasicMaterial({ 
      color: 0xffffff,
      opacity: 0.4,
      transparent: true 
    });
    const centerLine = new THREE.LineSegments(centerLineGeometry, centerLineMaterial);
    scene.add(centerLine);

    // Create approach lights
    const createLight = (x: number, z: number, size: number = 1, intensity: number = 1) => {
      const pointLight = new THREE.PointLight(0xffffff, intensity, 50);
      pointLight.position.set(x, 0, z);
      scene.add(pointLight);
      
      // Add a small sphere to represent the light
      const sphereGeometry = new THREE.SphereGeometry(size, 16, 16);
      const sphereMaterial = new THREE.MeshBasicMaterial({ 
        color: 0xffffff,
        transparent: true,
        opacity: 1.0 
      });
      const sphere = new THREE.Mesh(sphereGeometry, sphereMaterial);
      sphere.position.set(x, 0, z);
      scene.add(sphere);
      
      return { light: pointLight, sphere };
    };

    // Define types for our light objects
    type LightObject = {
      light: THREE.PointLight;
      sphere: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
    };
    
    type RabbitLight = {
      light: LightObject;
      lastFlashTime: number;
    };

    // ALSF-2 Approach Lighting System
    const lights: LightObject[] = [];
    
    // Centerline lights
    for (let i = 1; i <= 30; i++) {
      const z = -(i * 50);
      lights.push(createLight(0, z, 0.5, 0.7));
    }
    
    // Crossbar lights (5 bars)
    for (let i = 1; i <= 5; i++) {
      const z = -(i * 200);
      for (let j = -6; j <= 6; j++) {
        if (j !== 0) { // Skip center position
          lights.push(createLight(j * 20, z, 0.7, 0.8));
        }
      }
    }
    
    // Side row lights
    for (let i = 0; i < 20; i++) {
      const z = -(i * 75);
      lights.push(createLight(-100, z, 0.5, 0.7));
      lights.push(createLight(100, z, 0.5, 0.7));
    }
    
    // Rabbit lights (sequentially flashing)
    const rabbitLights: RabbitLight[] = [];
    for (let i = 1; i <= 5; i++) {
      const z = -(i * 200);
      rabbitLights.push({
        light: createLight(0, z - 100, 1, 2),
        lastFlashTime: i * 400
      });
    }

    // Handle window resize
    const handleResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', handleResize);

    // Animation loop
    const animate = (time: number) => {
      requestAnimationFrame(animate);
      
      // Animate the runway lights
      lights.forEach(lightObj => {
        if (Math.random() > 0.99) {
          lightObj.sphere.material.opacity = Math.random() * 0.5 + 0.5;
        }
      });
      
      // Animate sequentially flashing rabbit lights with improved visibility
      const flashCycle = time % 2000;
      rabbitLights.forEach((rabbitLight, index) => {
        const flashDuration = 200;
        const flashStart = index * 300; // Reduced time between flashes for better visibility
        const flashEnd = flashStart + flashDuration;
        
        if (flashCycle >= flashStart && flashCycle < flashEnd) {
          rabbitLight.light.light.intensity = 10; // Increased intensity
          rabbitLight.light.sphere.scale.set(3, 3, 3); // Larger flash
          rabbitLight.light.sphere.material.opacity = 1.0;
        } else {
          rabbitLight.light.light.intensity = 0.1;
          rabbitLight.light.sphere.scale.set(1, 1, 1);
          rabbitLight.light.sphere.material.opacity = 0.3;
        }
      });
      
      renderer.render(scene, camera);
    };
    
    animate(0);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      containerRef.current?.removeChild(renderer.domElement);
      
      // Dispose of geometries and materials
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose();
          if (object.material instanceof THREE.Material) {
            object.material.dispose();
          } else if (Array.isArray(object.material)) {
            object.material.forEach(material => material.dispose());
          }
        }
      });
    };
  }, []);

  return <div ref={containerRef} className="fixed inset-0 z-0" />;
};

export default RunwayAnimation;