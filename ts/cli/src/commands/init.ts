// src/commands/init.ts
import { Command } from "commander";
import inquirer from "inquirer";
import axios from "axios";
import FormData from "form-data";
import fs from "fs";
import { exec } from "child_process";
import { promisify } from "util";
import { saveConfig, loadConfig, UserConfig } from "../utils/config";
import { packDirectory } from "../utils/tar";
import detectLanguage from "../utils/detectLanguage";
import { API_BASE } from "../config/api";

const execAsync = promisify(exec);
const prompt = inquirer.createPromptModule();

// ────────────────────────────────────────────────────────────
// GitHub OAuth helper
// ────────────────────────────────────────────────────────────
interface GitHubUser {
  login: string;
  email: string | null;
  avatar_url: string;
}
interface GitHubEmail {
  email: string;
  primary: boolean;
  verified: boolean;
}
interface ProjectResponse {
  id: string;
  name: string;
}

const performGitHubLogin = async (): Promise<UserConfig> => {
  const CLIENT_ID = "Ov23li4Gh7uA8XLb0wry";
  const state = Math.random().toString(36).substring(7);
  const authUrl =
    `https://github.com/login/oauth/authorize?client_id=${CLIENT_ID}` +
    `&redirect_uri=http://localhost:8000/callback&scope=user:email&state=${state}`;

  console.log("\n🔐 GitHub Authentication Required");
  console.log("Open the following URL in your browser:\n");
  console.log(authUrl, "\n");

  try {
    if (process.platform === "darwin") await execAsync(`open "${authUrl}"`);
    else if (process.platform === "win32")
      await execAsync(`start "${authUrl}"`);
    else await execAsync(`xdg-open "${authUrl}"`);
  } catch {
    /* ignore */
  }

  const { token } = await prompt<{ token: string }>([
    {
      type: "input",
      name: "token",
      message: "Paste the token from your browser:"
    }
  ]);
  if (!token) {
    console.error("❌ Token is required.");
    process.exit(1);
  }

  try {
    const user = await axios.get<GitHubUser>("https://api.github.com/user", {
      headers: { Authorization: `token ${token}` }
    });
    const emails = await axios.get<GitHubEmail[]>(
      "https://api.github.com/user/emails",
      {
        headers: { Authorization: `token ${token}` }
      }
    );
    const primary = emails.data.find((e) => e.primary && e.verified)?.email;
    if (!primary) {
      console.error("❌ No verified primary email found on GitHub.");
      process.exit(1);
    }

    const cfg = {
      token,
      email: primary,
      username: user.data.login,
      avatar_url: user.data.avatar_url
    };
    saveConfig(cfg);
    console.log(`\n✅ Authentication successful! Welcome, ${cfg.username}.`);
    return cfg;
  } catch {
    console.error("\n❌ Authentication failed. Invalid or expired token.");
    process.exit(1);
  }
};

// ────────────────────────────────────────────────────────────
// CLI command
// ────────────────────────────────────────────────────────────
const init = new Command("init")
  .description("Initialize a project and upload its files")
  .action(async () => {
    // 1) Load or create user config
    let userConfig: UserConfig;
    try {
      userConfig = loadConfig();
      console.log(
        `\n✅ Welcome back, ${userConfig.username || userConfig.email}.`
      );
    } catch {
      userConfig = await performGitHubLogin();
    }

    // 2) Create or select project
    console.log("\n📁 Project Selection");
    const { action } = await prompt<{ action: string }>([
      {
        type: "list",
        name: "action",
        message: "What would you like to do?",
        choices: [
          { name: "Create a new project", value: "create" },
          { name: "Select an existing project", value: "select" }
        ]
      }
    ]);

    let projectId = "";
    let projectName = ""; // we’ll need this later for tarball name

    if (action === "create") {
      const { name } = await prompt<{ name: string }>([
        { type: "input", name: "name", message: "Project name:" }
      ]);
      const res = await axios.post<ProjectResponse>(
        `${API_BASE}/projects/`,
        { name },
        { headers: { Authorization: `Bearer ${userConfig.token}` } }
      );
      projectId = res.data.id;
      projectName = res.data.name;
      console.log(`\n✅ Created project “${projectName}” (ID: ${projectId})`);
    } else {
      const res = await axios.get<ProjectResponse[]>(`${API_BASE}/projects/`, {
        headers: { Authorization: `Bearer ${userConfig.token}` }
      });
      if (res.data.length === 0) {
        console.log("No projects found. Please create one first.");
        process.exit(0);
      }
      const { id } = await prompt<{ id: string }>([
        {
          type: "list",
          name: "id",
          message: "Select a project:",
          choices: res.data.map((p) => ({ name: p.name, value: p.id }))
        }
      ]);
      projectId = id;
      projectName = res.data.find((p) => p.id === id)!.name;
      console.log(`\n✅ Selected project “${projectName}” (ID: ${projectId})`);
    }

    // 3) Auto‑detect metadata (no interactive questions)
    const current_path = ".";
    const language = detectLanguage();
    const has_dockerfile = fs.existsSync("Dockerfile");

    if (!has_dockerfile) {
      console.warn(
        "\n⚠️  No Dockerfile found. Add one if the runtime requires it."
      );
    }

    // 4) Gather environment variables (interactive)
    console.log("\n🔧 Environment Variables");
    const { env_keys } = await prompt<{ env_keys: string }>([
      {
        type: "input",
        name: "env_keys",
        message: "Env var keys (comma‑separated):",
        default: ""
      }
    ]);

    const envVars: Record<string, string> = {};
    const keys = env_keys
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);

    for (const key of keys) {
      // ← await each prompt
      const { value } = await prompt<{ value: string }>([
        { type: "input", name: "value", message: `Value for ${key}:` }
        // use `type: "password"` if you want the input hidden
      ]);
      envVars[key] = value;
    }

    // 5) Package & upload
    const tarPath = packDirectory(projectName); // projectName.tar
    const form = new FormData();
    form.append("file", fs.createReadStream(tarPath));
    form.append("current_path", current_path);
    form.append("language", language);
    form.append("has_dockerfile", String(has_dockerfile));
    form.append("env_vars", JSON.stringify(envVars));

    await axios.post(`${API_BASE}/projects/${projectId}/upload`, form, {
      headers: {
        Authorization: `Bearer ${userConfig.token}`,
        ...form.getHeaders()
      }
    });

    console.log("\n✅ Upload successful!");
    fs.unlinkSync(tarPath); // cleanup
    console.log("\n💡 To log out, run: `bernitespace logout`");
  });

export default init;
