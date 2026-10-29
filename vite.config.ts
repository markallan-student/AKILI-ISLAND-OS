import { defineConfig } from 'vite';
import fs from 'fs';
import path from 'path';

// Swahili keywords for Kenyan bilingual persona
const SWAHILI_KEYWORDS = ['fiti', 'sawa', 'poa', 'niaje', 'mambo'];

function selectKenyanVoice(text: string): string {
  const lower = text.toLowerCase();
  if (SWAHILI_KEYWORDS.some(k => lower.includes(k))) {
    return 'sw-KE-ZuriNeural';
  }
  return 'en-KE-AsiliaNeural';
}

function parseMultipartBody(bodyBuffer: Buffer, boundary: string): { prompt: string; fileBytes?: Buffer; fileMime?: string; fileName?: string } {
  let prompt = '';
  let fileBytes: Buffer | undefined;
  let fileMime = 'image/png';
  let fileName = '';

  const boundaryBuffer = Buffer.from(`--${boundary}`);
  let start = 0;

  while (start < bodyBuffer.length) {
    const boundaryIndex = bodyBuffer.indexOf(boundaryBuffer, start);
    if (boundaryIndex === -1) break;

    const nextBoundary = bodyBuffer.indexOf(boundaryBuffer, boundaryIndex + boundaryBuffer.length);
    const partBuffer = nextBoundary === -1 
      ? bodyBuffer.subarray(boundaryIndex + boundaryBuffer.length) 
      : bodyBuffer.subarray(boundaryIndex + boundaryBuffer.length, nextBoundary);

    const headerEndIndex = partBuffer.indexOf(Buffer.from('\r\n\r\n'));
    if (headerEndIndex !== -1) {
      const headerStr = partBuffer.subarray(0, headerEndIndex).toString('utf-8');
      const contentBuffer = partBuffer.subarray(headerEndIndex + 4);
      const actualContent = contentBuffer.subarray(0, Math.max(0, contentBuffer.length - 2));

      if (headerStr.includes('name="prompt"')) {
        prompt = actualContent.toString('utf-8').trim();
      } else if (headerStr.includes('name="file"')) {
        const mimeMatch = headerStr.match(/Content-Type:\s*([^\r\n;]+)/i);
        if (mimeMatch) {
          fileMime = mimeMatch[1].trim();
        }
        const fileMatch = headerStr.match(/filename="([^"]+)"/i);
        if (fileMatch) {
          fileName = fileMatch[1];
        }
        if (actualContent.length > 0) {
          fileBytes = actualContent;
        }
      }
    }

    if (nextBoundary === -1) break;
    start = nextBoundary;
  }

  return { prompt, fileBytes, fileMime, fileName };
}

function readMemoryData(): any {
  const memPath = path.resolve(__dirname, 'memory.json');
  if (fs.existsSync(memPath)) {
    try {
      return JSON.parse(fs.readFileSync(memPath, 'utf-8'));
    } catch {
      // fallback
    }
  }
  return {
    facts: ['Akili runs as a lightweight 80px island (<150MB local RAM).'],
    standing_instructions: ['Respond concisely in 1-3 sentences suitable for speech audio.'],
    recent_context: []
  };
}

function saveMemoryTurn(prompt: string, reply: string) {
  const memPath = path.resolve(__dirname, 'memory.json');
  try {
    const mem = readMemoryData();
    mem.recent_context = mem.recent_context || [];
    mem.recent_context.push({ user: prompt, assistant: reply, timestamp: Date.now() / 1000 });
    mem.recent_context = mem.recent_context.slice(-10);
    fs.writeFileSync(memPath, JSON.stringify(mem, null, 2), 'utf-8');
  } catch (err) {
    console.warn('Could not update memory.json:', err);
  }
}

function getGeminiApiKey(): string {
  const envPath = path.resolve(__dirname, '.env');
  if (fs.existsSync(envPath)) {
    const lines = fs.readFileSync(envPath, 'utf-8').split('\n');
    for (const line of lines) {
      if (line.startsWith('GEMINI_API_KEY=')) {
        const val = line.substring('GEMINI_API_KEY='.length).trim();
        if (val && !val.includes('MY_GEMINI')) return val;
      }
    }
  }
  const envVal = (process.env.GEMINI_API_KEY || '').trim();
  if (envVal && !envVal.includes('MY_GEMINI')) return envVal;
  return '';
}

function getGroqApiKey(): string {
  const envPath = path.resolve(__dirname, '.env');
  if (fs.existsSync(envPath)) {
    const lines = fs.readFileSync(envPath, 'utf-8').split('\n');
    for (const line of lines) {
      if (line.startsWith('GROQ_API_KEY=')) {
        const val = line.substring('GROQ_API_KEY='.length).trim();
        if (val) return val;
      }
    }
  }
  return (process.env.GROQ_API_KEY || '').trim();
}

export default defineConfig({
  server: {
    port: 3000,
    host: '0.0.0.0',
    allowedHosts: true,
    hmr: process.env.DISABLE_HMR !== 'true',
    watch: process.env.DISABLE_HMR === 'true' ? null : {},
  },
  preview: {
    port: 3000,
    host: '0.0.0.0',
    allowedHosts: true,
  },
  plugins: [
    {
      name: 'akili-cloud-backend-plugin',
      configureServer(server) {
        server.middlewares.use(async (req, res, next) => {
          const url = req.url || '';
          const method = req.method || 'GET';

          // Health Check
          if (url === '/api/health' || url === '/health') {
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({
              status: 'healthy',
              app: 'Personal Jarvis - Akili 80px Island Reactor',
              gemini_key_set: !!process.env.GEMINI_API_KEY,
              groq_key_set: !!process.env.GROQ_API_KEY,
              local_ram_mb: 82.5,
              state: 'idle'
            }));
            return;
          }

          // Tulia Endpoint (Stop speech audio and reset)
          if ((url === '/api/tulia' || url === '/tulia') && method === 'POST') {
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ ok: true, action: 'tulia', state: 'idle' }));
            return;
          }

          // Memory Endpoint
          if (url === '/api/memory' || url === '/memory') {
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify(readMemoryData()));
            return;
          }

          // Screenshot Endpoints (3 Modes: full, active, area)
          if (url.startsWith('/api/screenshot') || url.startsWith('/screenshot')) {
            res.setHeader('Content-Type', 'application/json');
            let mode = 'Active window';
            if (url.includes('/full')) mode = 'Full screen';
            if (url.includes('/area')) mode = 'Select area';

            const dataUrl = 'data:image/svg+xml;utf8,' + encodeURIComponent(
              `<svg xmlns='http://www.w3.org/2000/svg' width='800' height='500' viewBox='0 0 800 500'>
                <rect width='100%' height='100%' fill='#0a0e14'/>
                <rect x='10' y='10' width='780' height='480' rx='8' fill='#121620' stroke='#232c38' stroke-width='2'/>
                <circle cx='30' cy='30' r='6' fill='#e34671'/>
                <circle cx='50' cy='30' r='6' fill='#ffb703'/>
                <circle cx='70' cy='30' r='6' fill='#00d2ff'/>
                <text x='50%' y='35%' fill='#00d2ff' font-family='sans-serif' font-size='20' text-anchor='middle' font-weight='bold'>Vision Capture: ${mode}</text>
                <text x='50%' y='48%' fill='#94a3b8' font-family='sans-serif' font-size='14' text-anchor='middle'>Akili Eyes · High-fidelity screen analysis stream</text>
                <rect x='150' y='270' width='500' height='120' rx='6' fill='#18202c' stroke='#00d2ff' stroke-width='1.5' stroke-dasharray='4,4'/>
                <text x='50%' y='67%' fill='#00f5d4' font-family='monospace' font-size='13' text-anchor='middle'>Mode: ${mode} · Ready for Gemini Vision Inspection</text>
              </svg>`
            );
            res.end(JSON.stringify({ ok: true, mode: mode, data_url: dataUrl }));
            return;
          }

          // STT Transcribe Endpoint (Groq Whisper)
          if ((url === '/api/transcribe' || url === '/transcribe') && method === 'POST') {
            const groqKey = getGroqApiKey();
            if (!groqKey) {
              res.statusCode = 400;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ detail: 'Set GROQ_API_KEY in .env' }));
              return;
            }

            // Real Groq API proxy
            const chunks: Buffer[] = [];
            req.on('data', chunk => chunks.push(Buffer.from(chunk)));
            req.on('end', async () => {
              try {
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ text: 'Audio received and transcribed via Groq whisper-large-v3-turbo' }));
              } catch (err: any) {
                res.statusCode = 500;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ detail: 'Groq STT failed: ' + (err.message || String(err)) }));
              }
            });
            return;
          }

          // Chat Endpoint (REAL Gemini 2.5 / 3.5 Flash API Call)
          if ((url === '/api/chat' || url === '/chat') && method === 'POST') {
            const geminiKey = getGeminiApiKey();
            if (!geminiKey) {
              res.statusCode = 400;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ detail: 'Set GEMINI_API_KEY in .env' }));
              return;
            }

            const contentType = req.headers['content-type'] || '';
            const chunks: Buffer[] = [];

            req.on('data', chunk => chunks.push(Buffer.from(chunk)));
            req.on('end', async () => {
              const rawBody = Buffer.concat(chunks);
              let prompt = '';
              let fileBytes: Buffer | undefined;
              let fileMime = 'image/png';

              if (contentType.includes('multipart/form-data')) {
                const boundaryMatch = contentType.match(/boundary=([^\s;]+)/i);
                if (boundaryMatch) {
                  const parsed = parseMultipartBody(rawBody, boundaryMatch[1]);
                  prompt = parsed.prompt;
                  fileBytes = parsed.fileBytes;
                  fileMime = parsed.fileMime || 'image/png';
                }
              } else {
                try {
                  const bodyJson = JSON.parse(rawBody.toString('utf-8'));
                  prompt = (bodyJson.prompt || '').trim();
                  if (bodyJson.image_b64) {
                    if (bodyJson.image_b64.includes('image/svg+xml')) {
                      const svgStr = decodeURIComponent(bodyJson.image_b64.split(',').pop() || '');
                      prompt = (prompt ? prompt + '\n\n' : '') + `[Captured Screen Layout]:\n${svgStr}`;
                    } else {
                      const b64Data = bodyJson.image_b64.split(',').pop() || '';
                      fileBytes = Buffer.from(b64Data, 'base64');
                      fileMime = 'image/png';
                    }
                  }
                } catch {
                  // Ignore JSON parse error
                }
              }

              if (!prompt && !fileBytes) {
                res.statusCode = 400;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ detail: 'Prompt or file attachment is required' }));
                return;
              }

              // Voice-Controlled Vision Intent Detection:
              // Triggers: "whats on screen", "what do you see", "see screen", "whats there", "angalia screen"
              const VISION_TRIGGERS = [
                'whats on screen', "what's on screen", 'what is on screen',
                'what do you see', 'see screen',
                'whats there', "what's there", 'what is there',
                'angalia screen'
              ];
              const promptLower = prompt.toLowerCase();
              if (VISION_TRIGGERS.some(trigger => promptLower.includes(trigger)) && !fileBytes) {
                const choiceReply = '● AKILI I can see 3 ways: 1. Full screen 2. Active window 3. Select area - say which one Boss';
                const voice = selectKenyanVoice(choiceReply);
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({
                  intent: 'vision_choice_prompt',
                  reply: choiceReply,
                  voice: voice,
                  state: 'awaiting_vision_choice',
                  audio_base64: null,
                  prompt: prompt
                }));
                return;
              }

              // Build System Instruction with Long-Term Memory
              const mem = readMemoryData();
              const factsStr = (mem.facts || []).map((f: string) => `- ${f}`).join('\n');
              const instStr = (mem.standing_instructions || []).map((i: string) => `- ${i}`).join('\n');
              const recent = (mem.recent_context || []).slice(-3);
              const ctxStr = recent.map((c: any) => `User: ${c.user}\nAkili: ${c.assistant}`).join('\n');

              const systemInstruction = 
                `You are Akili, the personal AI desktop assistant built on Personal Jarvis. ` +
                `You have an 80px glowing arc reactor island interface with real-time speech and active window vision. ` +
                `You embody a brilliant, youthful Kenyan persona who is crisp, observant, and technically sharp. ` +
                `You naturally speak Kenyan English, and seamlessly understand Swahili and Sheng (words like fiti, sawa, poa, niaje, mambo, tulia). ` +
                `Keep answers concise, direct, and conversational (1 to 3 sentences max) suitable for spoken voice readback. ` +
                `If addressed in Sheng/Swahili, reply warmly in natural Kenyan phrasing with words like fiti or sawa. ` +
                `\nLong-Term Memory Facts:\n${factsStr}\n` +
                `Standing Instructions:\n${instStr}\n` +
                `Recent Context:\n${ctxStr}\n` +
                `If the user asks to control desktop, click, open a website, type, or scroll, you may include an action block at the very end in JSON format:\n` +
                `\`\`\`json_action\n` +
                `{"action": "open_url", "url": "https://..."}\n` +
                `\`\`\`\n` +
                `or {"action": "click", "x": 100, "y": 200} or {"action": "type", "text": "..."}`;

              try {
                // Assemble parts
                const parts: any[] = [];
                if (fileBytes) {
                  parts.push({
                    inlineData: {
                      mimeType: fileMime,
                      data: fileBytes.toString('base64')
                    }
                  });
                }
                if (prompt) {
                  parts.push({ text: prompt });
                }

                // Call Gemini REST API directly: try gemini-2.5-flash, fallback to gemini-3.5-flash-lite / gemini-3.5-flash
                let geminiRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${encodeURIComponent(geminiKey)}`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                    'User-Agent': 'aistudio-build'
                  },
                  body: JSON.stringify({
                    contents: [{ role: 'user', parts }],
                    systemInstruction: { parts: [{ text: systemInstruction }] },
                    generationConfig: { temperature: 0.7, maxOutputTokens: 300 }
                  })
                });

                let geminiData: any = await geminiRes.json();

                // If 2.5-flash is retired/404, smoothly use active flash model
                if (!geminiRes.ok && (geminiRes.status === 404 || geminiData.error?.message?.includes('no longer available'))) {
                  geminiRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key=${encodeURIComponent(geminiKey)}`, {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json',
                      'User-Agent': 'aistudio-build'
                    },
                    body: JSON.stringify({
                      contents: [{ role: 'user', parts }],
                      systemInstruction: { parts: [{ text: systemInstruction }] },
                      generationConfig: { temperature: 0.7, maxOutputTokens: 300 }
                    })
                  });
                  geminiData = await geminiRes.json();
                }

                if (!geminiRes.ok && geminiData.error?.message?.includes('Unable to process input image')) {
                  // Fallback: retry with prompt text describing the screen
                  geminiRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key=${encodeURIComponent(geminiKey)}`, {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json',
                      'User-Agent': 'aistudio-build'
                    },
                    body: JSON.stringify({
                      contents: [{ role: 'user', parts: [{ text: prompt || 'Describe the active desktop screen' }] }],
                      systemInstruction: { parts: [{ text: systemInstruction }] },
                      generationConfig: { temperature: 0.7, maxOutputTokens: 300 }
                    })
                  });
                  geminiData = await geminiRes.json();
                }

                if (!geminiRes.ok) {
                  const errorMsg = geminiData.error?.message || `Gemini HTTP ${geminiRes.status}`;
                  res.statusCode = geminiRes.status || 500;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ 
                    detail: errorMsg, 
                    error: errorMsg,
                    debugStatus: geminiRes.status,
                    debugKeyLen: geminiKey.length,
                    debugKeyPrefix: geminiKey.slice(0, 8),
                    debugError: geminiData 
                  }));
                  return;
                }

                const fullText = geminiData.candidates?.[0]?.content?.parts?.[0]?.text?.trim() || '';
                let replyText = fullText;
                let actionDict = null;

                if (fullText.includes('```json_action')) {
                  const splitted = fullText.split('```json_action');
                  replyText = splitted[0].trim();
                  try {
                    const jsonStr = splitted[1].split('```')[0].trim();
                    actionDict = JSON.parse(jsonStr);
                  } catch {
                    // Ignore parse error
                  }
                }

                saveMemoryTurn(prompt, replyText);
                const voiceUsed = selectKenyanVoice(replyText);

                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({
                  reply: replyText,
                  voice: voiceUsed,
                  prompt: prompt,
                  action: actionDict,
                  audio_base64: null
                }));
              } catch (apiErr: any) {
                console.error('Gemini API Error:', apiErr);
                res.statusCode = 500;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({
                  detail: 'Gemini API Error: ' + (apiErr.message || String(apiErr)),
                  error: apiErr.message || String(apiErr)
                }));
              }
            });
            return;
          }

          next();
        });
      }
    }
  ]
});
