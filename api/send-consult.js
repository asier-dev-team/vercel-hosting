const fs = require("fs");
const path = require("path");

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function getConfigApiKey() {
  try {
    const configPath = path.join(process.cwd(), "config.yaml");
    const configText = fs.readFileSync(configPath, "utf8");
    const resendKeyMatch = configText.match(/^\s*resend_key:\s*["']?([^"'\n]+)["']?\s*$/m);
    if (resendKeyMatch) {
      return resendKeyMatch[1].trim();
    }

    const legacyMatch = configText.match(/^\s*api_key:\s*["']?([^"'\n]+)["']?\s*$/m);
    return legacyMatch ? legacyMatch[1].trim() : "";
  } catch {
    return "";
  }
}

function getErrorMessage(data, fallback) {
  if (!data) return fallback;
  if (typeof data === "string" && data.trim()) return data.trim();
  if (typeof data.message === "string" && data.message.trim()) return data.message.trim();
  if (typeof data.error === "string" && data.error.trim()) return data.error.trim();
  if (data.error && typeof data.error.message === "string" && data.error.message.trim()) {
    return data.error.message.trim();
  }
  return fallback;
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

  const apiKey = process.env.RESEND_API_KEY || getConfigApiKey();
  if (!apiKey) {
    return res.status(500).json({
      error: "Missing RESEND_API_KEY environment variable or config.yaml resend_key.",
    });
  }

  const safeName = escapeHtml(name);
  const safeEmail = escapeHtml(email);
  const safeProject = escapeHtml(project || "Not provided");
  const safeDetails = escapeHtml(details).replace(/\n/g, "<br>");

  try {
    const response = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        "User-Agent": "vercel-hosting-consult-form/1.0",
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
        html: `
          <div style="font-family: Arial, sans-serif; background:#f4f8fb; padding:24px;">
            <div style="max-width:640px; margin:0 auto; background:white; border-radius:16px; padding:24px; border:1px solid #dbe7f0;">
              <h1 style="margin:0 0 16px; color:#12324a;">New Website Consult Request</h1>
              <p style="margin:0 0 12px; color:#4b6980;">A new lead came in from your website.</p>

              <table style="width:100%; border-collapse:collapse; margin-top:20px;">
                <tr>
                  <td style="padding:10px; font-weight:bold; color:#12324a;">Name</td>
                  <td style="padding:10px; color:#4b6980;">${safeName}</td>
                </tr>
                <tr>
                  <td style="padding:10px; font-weight:bold; color:#12324a;">Email</td>
                  <td style="padding:10px; color:#4b6980;">${safeEmail}</td>
                </tr>
                <tr>
                  <td style="padding:10px; font-weight:bold; color:#12324a;">Project</td>
                  <td style="padding:10px; color:#4b6980;">${safeProject}</td>
                </tr>
                <tr>
                  <td style="padding:10px; font-weight:bold; color:#12324a; vertical-align:top;">Details</td>
                  <td style="padding:10px; color:#4b6980;">${safeDetails}</td>
                </tr>
              </table>
            </div>
          </div>
        `,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        error: getErrorMessage(data, "Failed to send consult request."),
      });
    }

    return res.status(200).json({ success: true, id: data.id });
  } catch (error) {
    return res.status(500).json({ error: "Unexpected error while sending email." });
  }
};
