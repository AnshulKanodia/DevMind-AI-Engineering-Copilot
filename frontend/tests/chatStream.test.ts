import test from "node:test";
import assert from "node:assert/strict";
import { streamAgentChat, type AgentThought } from "../src/lib/chatStream.ts";

test("ChatStream - streams tokens, thoughts, and citations for general query", async () => {
  let fullText = "";
  const thoughts: AgentThought[] = [];
  let citationsList: Array<{ file: string; lines: string; type: string }> = [];
  let isDone = false;

  await streamAgentChat(
    "How does the AST parser work?",
    "devmind-test-repo",
    {
      onToken: (tok) => {
        fullText += tok;
      },
      onThought: (t) => {
        thoughts.push(t);
      },
      onCitations: (c) => {
        citationsList = c;
      },
      onDone: () => {
        isDone = true;
      },
      onError: (err) => {
        assert.fail(`Stream returned error: ${err}`);
      },
    }
  );

  assert.ok(isDone, "Stream should mark as done");
  assert.ok(fullText.length > 50, "Full response should have meaningful content");
  assert.ok(thoughts.length >= 3, "Multi-agent chain should emit thoughts");
  assert.ok(citationsList.length > 0, "Citations should be emitted");

  const thoughtNodes = thoughts.map((t) => t.node);
  assert.ok(thoughtNodes.includes("router"));
  assert.ok(thoughtNodes.includes("retriever"));
  assert.ok(thoughtNodes.includes("synthesizer"));
});

test("ChatStream - supports AbortController cancellation", async () => {
  const controller = new AbortController();
  let tokenCount = 0;

  // Abort immediately
  controller.abort();

  await streamAgentChat(
    "Cancel this request",
    "devmind-test-repo",
    {
      onToken: () => {
        tokenCount++;
      },
      onThought: () => {},
      onCitations: () => {},
      onDone: () => {},
      onError: () => {},
    },
    controller.signal
  );

  assert.equal(tokenCount, 0, "No tokens should be streamed when pre-aborted");
});

test("ChatStream - resolves environment variables and .env citations for Personal-Finance-Management", async () => {
  let fullText = "";
  let citationsList: Array<{ file: string; lines: string; type: string }> = [];
  let isDone = false;

  await streamAgentChat(
    "what env do i need",
    "https://github.com/AnshulKanodia/Personal-Finance-Management",
    {
      onToken: (tok) => {
        fullText += tok;
      },
      onThought: () => {},
      onCitations: (c) => {
        citationsList = c;
      },
      onDone: () => {
        isDone = true;
      },
      onError: (err) => {
        assert.fail(`Stream error: ${err}`);
      },
    }
  );

  assert.ok(isDone);
  assert.ok(fullText.includes("MONGODB_URI"), "Response should dynamically extract MONGODB_URI");
  assert.ok(fullText.includes("APP_PIN"), "Response should dynamically extract APP_PIN");
  assert.ok(fullText.includes("SESSION_SECRET"), "Response should dynamically extract SESSION_SECRET");
  assert.ok(
    citationsList.some((c) => c.file === ".env.example"),
    "Citations must reference .env.example"
  );
});

test("ChatStream - dynamically discovers database packages for connected repo", async () => {
  let fullText = "";
  let citationsList: Array<{ file: string; lines: string; type: string }> = [];

  await streamAgentChat(
    "explain the database configuration and models",
    "AnshulKanodia/Personal-Finance-Management",
    {
      onToken: (tok) => {
        fullText += tok;
      },
      onThought: () => {},
      onCitations: (c) => {
        citationsList = c;
      },
      onDone: () => {},
      onError: () => {},
    }
  );

  assert.ok(fullText.toLowerCase().includes("mongoose"), "Response should dynamically discover mongoose from package.json");
  assert.ok(
    citationsList.some((c) => c.file === "package.json"),
    "Citations must reference package.json"
  );
});

test("ChatStream - responds conversationally to greetings rather than dumping architecture", async () => {
  let fullText = "";

  await streamAgentChat(
    "hey",
    "AnshulKanodia/Personal-Finance-Management",
    {
      onToken: (tok) => {
        fullText += tok;
      },
      onThought: () => {},
      onCitations: () => {},
      onDone: () => {},
      onError: () => {},
    }
  );

  assert.ok(fullText.includes("Hello!"), "Response should greet the user politely");
  assert.ok(
    !fullText.includes("### 💡 Grounded Repository Analysis"),
    "Greeting should not dump full architecture overview"
  );
});

test("ChatStream - resolves complete, non-empty setup instructions for Personal-Finance-Management", async () => {
  let fullText = "";
  let citationsList: Array<{ file: string; lines: string; type: string }> = [];

  await streamAgentChat(
    "how do i run",
    "https://github.com/AnshulKanodia/Personal-Finance-Management",
    {
      onToken: (tok) => {
        fullText += tok;
      },
      onThought: () => {},
      onCitations: (c) => {
        citationsList = c;
      },
      onDone: () => {},
      onError: () => {},
    }
  );

  assert.ok(fullText.length > 200, "Setup output must contain substantive instructions, not blank lines");
  assert.ok(fullText.includes("Setup & Execution Guide"), "Header must declare setup guide");
  assert.ok(
    fullText.includes("git clone") || fullText.includes("npm run dev") || fullText.includes("npm install"),
    "Setup output must contain concrete commands"
  );
  assert.ok(citationsList.some((c) => c.file === "README.md"), "Must cite README.md");
});

test("ChatStream - returns clean overview without raw shields.io badge links", async () => {
  let fullText = "";

  await streamAgentChat(
    "what is this about ?",
    "AnshulKanodia/Personal-Finance-Management",
    {
      onToken: (tok) => {
        fullText += tok;
      },
      onThought: () => {},
      onCitations: () => {},
      onDone: () => {},
      onError: () => {},
    }
  );

  assert.ok(fullText.includes("About RupeePulse"), "Header should state project title");
  assert.ok(fullText.includes("RupeePulse") && fullText.includes("personal finance management"), "Overview must contain genuine descriptive prose");
  assert.ok(!fullText.includes("[![Next.js]"), "Must NOT render raw unparsed markdown badge links");
  assert.ok(!fullText.includes("img.shields.io"), "Must NOT dump shields.io image links in overview prose");
});

test("ChatStream - identifies live hosting URL and platform for Anshul-Kanodia-Portfolio", async () => {
  let fullText = "";
  let citationsList: Array<{ file: string; lines: string; type: string }> = [];

  await streamAgentChat(
    "where it is hosted ?",
    "https://github.com/AnshulKanodia/Anshul-Kanodia-Portfolio",
    {
      onToken: (tok) => {
        fullText += tok;
      },
      onThought: () => {},
      onCitations: (c) => {
        citationsList = c;
      },
      onDone: () => {},
      onError: () => {},
    }
  );

  assert.ok(fullText.includes("anshulkanodia.me"), "Response must identify the live domain anshulkanodia.me");
  assert.ok(fullText.includes("Vercel"), "Response must identify Vercel hosting platform");
  assert.ok(citationsList.some((c) => c.file === "README.md"), "Must cite README.md");
});

test("ChatStream - provides dual aesthetic overview and launch guide for 'run it and show how it look'", async () => {
  let fullText = "";
  let citationsList: Array<{ file: string; lines: string; type: string }> = [];

  await streamAgentChat(
    "run it and show how it look",
    "https://github.com/AnshulKanodia/Anshul-Kanodia-Portfolio",
    {
      onToken: (tok) => {
        fullText += tok;
      },
      onThought: () => {},
      onCitations: (c) => {
        citationsList = c;
      },
      onDone: () => {},
      onError: () => {},
    }
  );

  assert.ok(fullText.length > 200, "Must provide substantial response");
  assert.ok(fullText.includes("Visual Design") || fullText.includes("UI"), "Must explain UI aesthetics");
  assert.ok(
    fullText.includes("How to Run") || fullText.includes("Setup") || fullText.includes("Local"),
    "Must explain how to run"
  );
  assert.ok(citationsList.some((c) => c.file === "README.md"), "Must cite README.md");
});



