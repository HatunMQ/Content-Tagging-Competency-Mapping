// Calls Model D (Qwen3.5-4B) to translate content into Arabic.
//
// This goes through Vite's own dev-server proxy (see vite.config.js's
// server.proxy["/absproxy/5173/model-api"]) instead of hitting the model's
// port directly from the browser -- avoids both a squatted-port issue and
// a code-server /absproxy/ tunnel conflict that were diagnosed earlier.
// Vite forwards the request server-side to whichever local port is
// currently registered for Model D in switch_model.sh's MODEL_REGISTRY
// (keep vite.config.js's proxy target in sync with that registry, same as
// every other model-port reference in this project).
const LOCAL_MODEL_NAME = "Qwen3.5-4B";

// Long files (a full lecture .md, a dense notebook) can easily run past
// what a single model completion can safely return, which is what caused
// real translations to get cut off mid-file. Splitting the source into
// fixed-size line chunks and translating each one separately means no
// file is ever too long to translate in full -- only how many requests it
// takes changes, never whether it completes. Most real content chunks in
// this app are far under this size, so this only kicks in for genuinely
// long files like a full markdown lecture.
const LINES_PER_CHUNK = 40;
const MAX_TOKENS_PER_CHUNK = 3000;

const SYSTEM_PROMPT =
  "You are a translation assistant. Translate the user's educational content into Arabic. Preserve the exact line structure of the input: if the input has multiple lines, output the same number of lines in the same order, each translated on its own line. Do not merge lines into a single paragraph. Only leave a line untouched if it is actual executable code or SQL syntax -- keywords, identifiers, table/column names, punctuation, function calls. If a line is a comment or heading written in natural human language -- including SQL comments starting with '--', Python/shell comments starting with '#', markdown headings, or example/exercise descriptions -- you MUST translate it into Arabic like any other prose, even when it sits right next to or inside a code block. Never skip translating a line just because it is near code. A short section heading or title on its own line (for example 'Window - Partitioning' or 'Window - ORDER BY') is prose describing the section, not an actual SQL statement, even when it contains a word that is also an SQL keyword elsewhere (such as 'ORDER BY' or 'PARTITION'). Translate such headings in full, exactly like any other heading. Only leave a line completely untouched when the line itself is a real, executable SQL statement or fragment (for example one that starts with SELECT, FROM, WHERE, CREATE, INSERT, JOIN, or GROUP BY), never merely because it contains a word that happens to also be an SQL keyword. Return only the Arabic translation, nothing else.";

function modelApiUrl(path) {
  const base = import.meta.env.BASE_URL || "/";
  return `${window.location.origin}${base}model-api/${path}`;
}

async function translateChunk(text) {
  const endpoint = modelApiUrl("v1/chat/completions");
  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: LOCAL_MODEL_NAME,
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: text },
      ],
      temperature: 0,
      max_tokens: MAX_TOKENS_PER_CHUNK,
      chat_template_kwargs: { enable_thinking: false },
    }),
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status} from ${endpoint}`);
  }
  const body = await res.json();
  const choice = body?.choices?.[0];
  let translated = choice?.message?.content?.trim();
  if (translated) {
    translated = translated.replace(/<think>[\s\S]*?<\/think>/gi, "").trim();
  }
  if (!translated) {
    throw new Error("Model returned an empty translation");
  }
  if (choice?.finish_reason === "length") {
    // With MAX_TOKENS_PER_CHUNK this should be rare, but a real cutoff
    // must still be surfaced honestly rather than silently returned as if
    // it were the complete translation.
    throw new Error("A section of this file was too long to translate in one pass");
  }
  return translated;
}

// onProgress(current, total) is called before each chunk request, so the
// UI can show real progress ("Translating (2/5)...") on longer files
// instead of a single indefinite spinner.
export async function translateToArabic(text, onProgress) {
  const lines = text.split("\n");
  const chunks = [];
  for (let i = 0; i < lines.length; i += LINES_PER_CHUNK) {
    chunks.push(lines.slice(i, i + LINES_PER_CHUNK).join("\n"));
  }
  if (chunks.length === 0) chunks.push(text);

  const translated = [];
  for (let i = 0; i < chunks.length; i++) {
    if (onProgress) onProgress(i + 1, chunks.length);
    translated.push(await translateChunk(chunks[i]));
  }
  return translated.join("\n");
}
