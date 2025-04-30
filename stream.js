const puppeteer = require('puppeteer');

async function zoomWebRTCWithTTS() {
  const browser = await puppeteer.launch({
    headless: false,
    defaultViewport: null, // Full viewport
    args: [
      '--use-fake-ui-for-media-stream', // Auto-accept permissions
      '--window-size=1280,720'
    ]
  });
  
  const page = await browser.newPage();
  
  // Inject our custom WebRTC TTS code
  function injectResponsiveVoiceTTS() {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const destination = audioCtx.createMediaStreamDestination();
  
    function injectScript() {
      const script = document.createElement('script');
      script.src = 'https://code.responsivevoice.org/responsivevoice.js?key=1Pg3pJoj';
      script.onload = () => {
        console.log('[Injected] ResponsiveVoice loaded');
  
        window.speakToMic = (text) => {
          console.log(`[Injected] speakToMic called: "${text}"`);
          responsiveVoice.speak(text, "UK English Female", {
            onstart: () => {
              const interval = setInterval(() => {
                const internalAudio = document.querySelector("audio[src*='responsivevoice']");
                if (internalAudio) {
                  clearInterval(interval);
                  try {
                    const source = audioCtx.createMediaElementSource(internalAudio);
                    source.connect(destination);
                    console.log("[Injected] Connected ResponsiveVoice to mic stream");
                  } catch (err) {
                    console.warn("Already connected or error:", err);
                  }
                }
              }, 100);
            }
          });
        };
      };
      document.head.appendChild(script);
    }
  
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', injectScript);
    } else {
      injectScript();
    }
  
    const originalGetUserMedia = navigator.mediaDevices.getUserMedia;
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      if (constraints && constraints.audio) {
        console.log('[Injected] Intercepted audio getUserMedia request');
        return destination.stream;
      }
      return originalGetUserMedia.call(navigator.mediaDevices, constraints);
    };
  }

  await page.evaluateOnNewDocument(injectResponsiveVoiceTTS);

  page.on('framenavigated', async () => {
    console.log('[DEBUG] Page navigated, reinjecting speakToMic...');
    await page.evaluate(injectResponsiveVoiceTTS);
  });
  
  page.on('console', msg => console.log('[PAGE]', msg.text()));
  
  // Navigate to Zoom
  console.log('Navigating to Zoom meeting...');
  await page.goto('https://ethz.zoom.us/j/67045275542');
  
  // Wait for and click "Join from your browser"
  // J: does nto work
  /*console.log('Looking for "Join from your browser" button...');
  try {
    // Wait for button to be visible and click it
    await page.waitForSelector('a:contains("Join from your browser")', { timeout: 30000 });
    await page.evaluate(() => {
      const joinButton = Array.from(document.querySelectorAll('a')).find(el => 
        el.textContent.includes('Join from your browser'));
      if (joinButton) joinButton.click();
    });
    console.log('Clicked "Join from your browser"');
  } catch (error) {
    console.error('Error finding "Join from your browser" button:', error);
    // Try alternative selectors if the button isn't found
    try {
      await page.waitForSelector('#joinBtn', { timeout: 5000 });
      await page.click('#joinBtn');
      console.log('Clicked alternative join button');
    } catch (altError) {
      console.error('Failed to find any join button. Current URL:', await page.url());
      // Take a screenshot to see what's on the page
      await page.screenshot({ path: 'zoom-page.png' });
    }
  }*/
  
  // Handle the name input screen if it appears
  try {
    console.log('Looking for name input...');
    await page.waitForSelector('#inputname', { timeout: 10000 });
    await page.type('#inputname', 'TTS Bot');
    
    // Click Join button
    await page.waitForSelector('#joinBtn', { timeout: 5000 });
    await page.click('#joinBtn');
    console.log('Entered name and joined meeting');
  } catch (error) {
    console.log('Name input not found or already passed this step');
  }
  
  // Wait for the meeting to load
  console.log('Waiting for meeting to initialize...');
  await page.waitForTimeout(5000);
  
  // Now we can speak to the meeting
  console.log('Attempting to speak in the meeting...');
  await page.evaluate(() => {
    if (typeof window.speakToMic === 'function') {
      window.speakToMic("Hello, this is a test message from the TTS system. I am speaking through the virtual microphone in Zoom.");
    } else {
      console.error('speakToMic function not found');
    }
  });
  
  // Keep the browser open for interaction
  console.log('TTS message sent. Browser will remain open.');
  
  // Add function to speak text on demand
  page.exposeFunction('speak', async (text) => {
    await page.evaluate((textToSpeak) => {
      if (typeof window.speakToMic === 'function') {
        window.speakToMic(textToSpeak);
        return true;
      } else {
        console.error('speakToMic function not found');
        return false;
      }
    }, text);
  });
  
  return { browser, page, speak: (text) => page.exposeFunction('speak', text) };
}

// Run the example
(async () => {
  try {
    const { browser, page, speak } = await zoomWebRTCWithTTS();
    
    // Example of speaking again after 10 seconds
    setInterval(async () => {
      try {
        await page.evaluate(() => {
          console.log("Inside evaluate");
          if (typeof window.speakToMic === 'function') {
            window.speakToMic("Follow-up message after 10 seconds.");
          } else {
            console.log("speakToMic is not defined.");
          }
        });
      } catch (err) {
        console.error("Interval error:", err);
      }
    }, 10000);    
    
    // The browser will stay open so you can observe the meeting
    // To close, uncomment: await browser.close();
    
    console.log('Script is running. Browser will stay open to maintain the Zoom session.');
  } catch (error) {
    console.error('Error in main execution:', error);
  }
})();
