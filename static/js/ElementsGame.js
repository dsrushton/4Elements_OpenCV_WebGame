// static/js/ElementsGame.js

const ElementsGame = () => {
  const [hasPermission, setHasPermission] = React.useState(false);
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [showAlert, setShowAlert] = React.useState(false);
  const videoRef = React.useRef(null);
  const canvasRef = React.useRef(null);
  const streamRef = React.useRef(null);
  
  React.useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { 
          width: 640,
          height: 480,
          facingMode: 'user'
        } 
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        streamRef.current = stream;
        setHasPermission(true);
        setIsPlaying(true);
        startGameLoop();
      }
    } catch (err) {
      console.error('Error accessing camera:', err);
      setShowAlert(true);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      setIsPlaying(false);
    }
  };

  const startGameLoop = () => {
    if (!videoRef.current || !canvasRef.current) return;

    const processFrame = async () => {
      const canvas = canvasRef.current;
      const context = canvas.getContext('2d');
      
      // Draw the video frame to canvas
      context.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
      
      // Get the frame data
      const frameData = canvas.toDataURL('image/jpeg', 0.8);

      try {
        const response = await fetch('/process_frame', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ frame: frameData }),
        });

        if (response.ok) {
          const data = await response.json();
          
          // Draw the processed image
          const img = new Image();
          img.onload = () => {
            context.clearRect(0, 0, canvas.width, canvas.height);
            context.drawImage(img, 0, 0);
          };
          img.src = data.image;
        }
      } catch (err) {
        console.error('Error processing frame:', err);
      }

      if (isPlaying) {
        requestAnimationFrame(processFrame);
      }
    };

    requestAnimationFrame(processFrame);
  };

  const resetGame = async () => {
    try {
      await fetch('/reset_game', {
        method: 'POST',
      });
      showToast('Game Reset Successfully!');
    } catch (err) {
      console.error('Error resetting game:', err);
    }
  };

  return React.createElement('div', { 
    className: "flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4" 
  }, [
    showAlert && React.createElement('div', {
      key: 'alert',
      className: "bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4",
      role: "alert"
    }, [
      React.createElement('strong', { className: "font-bold" }, "Camera Access Required"),
      React.createElement('span', { className: "block sm:inline" }, 
        " Please allow camera access to play the Elements Game.")
    ]),
    
    React.createElement('div', {
      key: 'main-container',
      className: "bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl"
    }, [
      React.createElement('div', {
        key: 'header',
        className: "flex justify-between items-center mb-4"
      }, [
        React.createElement('h1', { className: "text-2xl font-bold" }, "Elements Game"),
        React.createElement('div', { className: "space-x-2" }, [
          React.createElement('button', {
            key: 'camera-button',
            className: `px-4 py-2 rounded ${isPlaying ? "bg-red-500" : "bg-blue-500"} text-white`,
            onClick: isPlaying ? stopCamera : startCamera
          }, isPlaying ? "Stop Camera" : "Start Camera"),
          React.createElement('button', {
            key: 'reset-button',
            className: "px-4 py-2 rounded bg-gray-500 text-white",
            onClick: resetGame
          }, "Reset Game")
        ])
      ]),

      React.createElement('div', {
        key: 'video-container',
        className: "relative aspect-video bg-gray-900 rounded-lg overflow-hidden"
      }, [
        React.createElement('video', {
          key: 'video',
          ref: videoRef,
          className: "absolute inset-0 w-full h-full object-cover",
          autoPlay: true,
          playsInline: true,
          muted: true
        }),
        React.createElement('canvas', {
          key: 'canvas',
          ref: canvasRef,
          width: 640,
          height: 480,
          className: "absolute inset-0 w-full h-full"
        }),
        !hasPermission && !isPlaying && React.createElement('div', {
          key: 'permission-message',
          className: "absolute inset-0 flex items-center justify-center bg-gray-900/80 text-white"
        }, React.createElement('p', {}, "Click \"Start Camera\" to begin playing"))
      ]),

      React.createElement('div', {
        key: 'instructions',
        className: "mt-4 text-sm text-gray-600"
      }, [
        React.createElement('p', {}, "Instructions:"),
        React.createElement('ul', { className: "list-disc list-inside" }, [
          React.createElement('li', {}, "Use your index finger to interact with the elements"),
          React.createElement('li', {}, "Close your thumb and index finger to grab an element"),
          React.createElement('li', {}, "Drag elements to the golden box to activate them"),
          React.createElement('li', {}, "Combine all elements to win!")
        ])
      ])
    ])
  ]);
};