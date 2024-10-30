// Wrap the entire component in an IIFE (Immediately Invoked Function Expression)
window.ElementsGame = (() => {
    // Component definition
    const ElementsGame = () => {
        const [hasPermission, setHasPermission] = React.useState(false);
        const [isPlaying, setIsPlaying] = React.useState(false);
        const [showAlert, setShowAlert] = React.useState(false);
        const [debugInfo, setDebugInfo] = React.useState('');
        const [gameState, setGameState] = React.useState({
            goldAchieved: false,
            currentElement: null,
            activeEffects: new Set()
        });
        
        const isMounted = React.useRef(true);
        
        const videoRef = React.useRef(null);
        const canvasRef = React.useRef(null);
        const streamRef = React.useRef(null);
        const gameLoopRef = React.useRef(null);
        const [sounds, setSounds] = React.useState({});

        const addDebugInfo = (info) => {
            // Only log important events, not every frame
            if (!info.includes('Frame processed')) {
                console.log(info);
                setDebugInfo(prev => `${new Date().toISOString()}: ${info}\n${prev}`);
            }
        };

        // Initialize sounds
        React.useEffect(() => {
            setSounds(initializeSounds());
            addDebugInfo('Sounds initialized');
        }, []);

        const initializeSounds = () => {
            const soundFiles = {
                'fireplace-6160.wav': new Audio('/static/sounds/fireplace-6160.wav'),
                'water.wav': new Audio('/static/sounds/Water.wav'),
                'air.wav': new Audio('/static/sounds/Air.wav'),
                'earth.wav': new Audio('/static/sounds/Earth.wav'),
                'Eureka.wav': new Audio('/static/sounds/Eureka.wav')
            };

            // Preload all sounds
            Object.values(soundFiles).forEach(audio => {
                audio.load();
            });

            return soundFiles;
        };

        const handleSoundEvents = (soundEvents) => {
            addDebugInfo(`Handling sound events: ${soundEvents}`);
            soundEvents.forEach(soundEvent => {
                if (sounds[soundEvent]) {
                    addDebugInfo(`Attempting to play sound: ${soundEvent}`);
                    // Stop the current instance and reset it
                    sounds[soundEvent].pause();
                    sounds[soundEvent].currentTime = 0;
                    // Play the sound
                    sounds[soundEvent].play().catch(e => {
                        console.error('Error playing sound:', e);
                    });
                }
            });
        };

        // Add reset functionality
        const handleReset = async () => {
            try {
                const response = await fetch('/reset_game', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });
                
                if (response.ok) {
                    addDebugInfo('Game reset successfully');
                    // Stop all sounds
                    Object.values(sounds).forEach(audio => {
                        audio.pause();
                        audio.currentTime = 0;
                    });
                } else {
                    addDebugInfo('Failed to reset game');
                }
            } catch (err) {
                addDebugInfo(`Reset error: ${err.message}`);
                console.error('Reset error:', err);
            }
        };

        const startCamera = async () => {
            try {
                setIsPlaying(true);
                addDebugInfo('Requesting camera access');
                
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { 
                        width: 640,
                        height: 480,
                        facingMode: 'user'
                    } 
                });
                
                if (videoRef.current && isMounted.current) {
                    videoRef.current.srcObject = stream;
                    streamRef.current = stream;
                    
                    // Wait for video to be ready
                    await new Promise((resolve) => {
                        videoRef.current.onloadedmetadata = () => {
                            videoRef.current.play().then(resolve);
                        };
                    });
                    
                    // Initialize canvas
                    if (canvasRef.current) {
                        canvasRef.current.width = videoRef.current.videoWidth;
                        canvasRef.current.height = videoRef.current.videoHeight;
                    }
                    
                    setHasPermission(true);
                    addDebugInfo('Camera started successfully');
                    startGameLoop();
                }
            } catch (err) {
                addDebugInfo(`Camera access error: ${err.message}`);
                console.error('Error accessing camera:', err);
                setShowAlert(true);
                setIsPlaying(false);
            }
        };

        const startGameLoop = React.useCallback(() => {
            if (!videoRef.current || !canvasRef.current) {
                addDebugInfo('Video or canvas ref not ready');
                return;
            }

            addDebugInfo('Starting game loop');
            let frameCount = 0;
            
            const processFrame = async () => {
                if (!isMounted.current) return;

                try {
                    if (!videoRef.current || !canvasRef.current) {
                        addDebugInfo('Missing refs');
                        return;
                    }

                    const canvas = canvasRef.current;
                    const context = canvas.getContext('2d');
                    
                    // Send unmirrored frame to backend
                    const tempCanvas = document.createElement('canvas');
                    tempCanvas.width = canvas.width;
                    tempCanvas.height = canvas.height;
                    const tempContext = tempCanvas.getContext('2d');
                    
                    // Draw unmirrored video frame
                    tempContext.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
                    const frameData = tempCanvas.toDataURL('image/jpeg', 0.8);

                    const response = await fetch('/process_frame', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ frame: frameData }),
                    });

                    if (response.ok) {
                        const data = await response.json();
                        if (data.success) {
                            // Draw the processed image
                            const img = new Image();
                            img.onload = () => {
                                if (canvasRef.current) {
                                    const ctx = canvasRef.current.getContext('2d');
                                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                                    
                                    // Mirror the final output
                                    ctx.save();
                                    ctx.scale(-1, 1);
                                    ctx.drawImage(img, -canvas.width, 0, canvas.width, canvas.height);
                                    ctx.restore();
                                }
                            };
                            img.src = data.image;

                            handleSoundEvents(data.sound_events);
                        } else {
                            addDebugInfo(`Server processing error: ${data.error}`);
                        }
                    }

                    gameLoopRef.current = requestAnimationFrame(processFrame);
                } catch (err) {
                    addDebugInfo(`Frame processing error: ${err.message}`);
                    console.error('Frame processing error:', err);
                    gameLoopRef.current = requestAnimationFrame(processFrame);
                }
            };

            gameLoopRef.current = requestAnimationFrame(processFrame);
        }, [handleSoundEvents]);

        // Add a start button component
        const StartButton = React.createElement('button', {
            key: 'start-button',
            className: "mt-4 bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded",
            onClick: startCamera,
            disabled: isPlaying
        }, "Start Camera");

        // Add reset button to your render method
        return React.createElement('div', { 
            className: "flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4" 
        }, [
            React.createElement('div', {
                key: 'main-container',
                className: "bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl"
            }, [
                React.createElement('div', {
                    key: 'game-container',
                    className: "relative aspect-video bg-gray-900 rounded-lg overflow-hidden"
                }, [
                    // Video element with display: none
                    React.createElement('video', {
                        key: 'video',
                        ref: videoRef,
                        style: { display: 'none' },  // Use display: none instead of className: "hidden"
                        autoPlay: true,
                        playsInline: true,
                        muted: true
                    }),
                    // Canvas element (no transform style needed anymore)
                    React.createElement('canvas', {
                        key: 'canvas',
                        ref: canvasRef,
                        width: 640,
                        height: 480,
                        className: "w-full h-full"
                    }),
                    // Show loading spinner when camera is starting
                    isPlaying && !hasPermission && React.createElement('div', {
                        key: 'loading-spinner',
                        className: "absolute inset-0 flex items-center justify-center"
                    }, React.createElement('div', {
                        className: "loading"
                    })),
                    // Show start button when not playing
                    !isPlaying && StartButton,
                    React.createElement('button', {
                        key: 'reset-button',
                        onClick: handleReset,
                        className: "mt-4 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
                    }, "Reset Game")
                ])
            ])
        ]);
    };

    return ElementsGame;
})();

// Add this at the very end of the file
console.log('ElementsGame component loaded successfully');