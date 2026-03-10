const fs = require("fs");
const path = require("path");

function readApiKey() {
  if (process.env.RESEND_API_KEY) {
    return process.env.RESEND_API_KEY;
  }

  try {
    const configPath = path.join(process.cwd(), "config.yaml");
    const file = fs.readFileSync(configPath, "utf8");
    const match = file.match(/api_key:\s*["']?([^"'\n]+)["']?/);
    return match ? match[1].trim() : "";
  } catch {
    return "";
  }
}

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method not allowed." });
  }

  const { name, email, project, details } = req.body || {};

  if (!name || !email || !details) {
    return res.status(400).json({ error: "Name, email, and project details are required." });
  }

  const apiKey = readApiKey();
  if (!apiKey) {
    return res.status(500).json({ error: "Missing Resend API key." });
  }

  try {
    const response = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: "Website Builder Service <onboarding@resend.dev>",
        to: ["asierdevteam@gmail.com"],
        reply_to: email,
        subject: `New website consult request from ${name}`,
        text: [
          `Name: ${name}`,
          `Email: ${email}`,
          `Project: ${project || "Not provided"}`,
          "",
          "Project details:",
          details,
        ].join("\n"),
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        error: data.message || "Failed to send consult request.",
      });
    }

    return res.status(200).json({ success: true, id: data.id });
  } catch {
    return res.status(500).json({ error: "Unexpected error while sending email." });
  }
};
