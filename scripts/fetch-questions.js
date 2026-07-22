const { GoogleGenerativeAI } = require("@google/generative-ai");
const fs = require("fs");
const path = require("path");

if (!process.env.GEMINI_API_KEY) {
    console.error("Missing GEMINI_API_KEY environment variable. Exiting.");
    process.exit(1);
}

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

const prompt = `
You are an expert on the Indian Parliament. Generate 2 real, factual, recently asked questions (from the Lok Sabha or Rajya Sabha) and their official minister answers.
Return ONLY a valid JSON array of objects representing these questions. Do not include markdown code block formatting like \`\`\`json or backticks. Just the raw array.

Use EXACTLY this schema for each object:
{
  "question": "The question text",
  "answer": "A short summary of the answer",
  "answerFull": "The full detailed answer",
  "askedBy": "Name of MP",
  "constituency": "Constituency, State (or just State for Rajya Sabha)",
  "party": "Party abbreviation (e.g., BJP, INC)",
  "house": "Lok Sabha or Rajya Sabha",
  "session": "e.g., Budget Session 2024",
  "sessionType": "Budget / Monsoon / Winter",
  "date": "YYYY-MM-DD",
  "questionType": "Starred or Unstarred",
  "questionNumber": "e.g., Q.No. 123",
  "ministry": "Name of the Ministry",
  "answeredBy": "Name of Minister",
  "answeredByRole": "Minister's Role",
  "tags": ["tag1", "tag2"],
  "source": "loksabha.nic.in or rajyasabha.nic.in"
}`;

async function fetchQuestions() {
    try {
        const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });
        const result = await model.generateContent(prompt);
        let rawText = result.response.text();
        // Clean up any potential markdown formatting
        rawText = rawText.replace(/```json/g, "").replace(/```/g, "").trim();

        const newQuestions = JSON.parse(rawText);
        if (!Array.isArray(newQuestions) || newQuestions.length === 0) {
            throw new Error("Invalid output format from Gemini");
        }

        const indexPath = path.join(__dirname, "..", "index.html");
        let htmlContent = fs.readFileSync(indexPath, "utf8");

        // Read the existing max ID (simple string search works safely enough for sequential IDs)
        const idMatches = [...htmlContent.matchAll(/id:\s*(\d+)/g)];
        let maxId = 0;
        for (const match of idMatches) {
            let num = parseInt(match[1], 10);
            if (num > maxId) maxId = num;
        }

        // Attach new incremented IDs
        const formattedQuestions = newQuestions.map((q) => {
            maxId++;
            return `        {
            id: ${maxId},
            question: ${JSON.stringify(q.question)},
            answer: ${JSON.stringify(q.answer)},
            answerFull: ${JSON.stringify(q.answerFull)},
            askedBy: ${JSON.stringify(q.askedBy)},
            constituency: ${JSON.stringify(q.constituency)},
            party: ${JSON.stringify(q.party)},
            house: ${JSON.stringify(q.house)},
            session: ${JSON.stringify(q.session)},
            sessionType: ${JSON.stringify(q.sessionType)},
            date: ${JSON.stringify(q.date)},
            questionType: ${JSON.stringify(q.questionType)},
            questionNumber: ${JSON.stringify(q.questionNumber)},
            ministry: ${JSON.stringify(q.ministry)},
            answeredBy: ${JSON.stringify(q.answeredBy)},
            answeredByRole: ${JSON.stringify(q.answeredByRole)},
            tags: ${JSON.stringify(q.tags)},
            source: ${JSON.stringify(q.source)}
        }`;
        });

        const injectionString = "const questionsData = [\n" + formattedQuestions.join(",\n") + ",";

        // Replaces the exact start of the array to inject the new ones at the top.
        const replacedHtml = htmlContent.replace("const questionsData = [", injectionString);

        if (replacedHtml !== htmlContent) {
            fs.writeFileSync(indexPath, replacedHtml, "utf8");
            console.log(`Successfully added ${newQuestions.length} new parliament questions to index.html!`);
        } else {
            console.error("Failed to find 'const questionsData = [' inside index.html");
        }

    } catch (error) {
        console.error("Error fetching or updating data:", error);
        process.exit(1);
    }
}

fetchQuestions();