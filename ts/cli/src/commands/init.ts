// src/commands/init.ts
import { Command } from "commander";
import inquirer from "inquirer";
import axios from "axios";
import FormData from "form-data";
import fs from "fs";
import path from "path";
import { exec } from "child_process";
import { promisify } from "util";
import { saveConfig, loadConfig, UserConfig } from "../utils/config";
import { packDirectory } from "../utils/tar";
import detectLanguage from "../utils/detectLanguage";
import { API_BASE } from "../config/api";

const execAsync = promisify(exec);
const prompt = inquirer.createPromptModule();
// Interfaces
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

interface MetadataAnswers {
  current_path: string;
  language: string;
  has_dockerfile: boolean;
}

// Helper function to perform the GitHub OAuth Flow
const performGitHubLogin = async (): Promise<UserConfig> => {
  const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID;
  if (!GITHUB_CLIENT_ID) {
    console.error("❌ GITHUB_CLIENT_ID not found in .env file.");
    process.exit(1);
  }

  const state = Math.random().toString(36).substring(7);
  const authUrl = `https://github.com/login/oauth/authorize?client_id=${GITHUB_CLIENT_ID}&redirect_uri=http://localhost:8000/callback&scope=user:email&state=${state}`;

  console.log("\n🔐 GitHub Authentication Required");
  console.log("Please open this URL in your browser to authenticate:\n");
  console.log(authUrl);

  try {
    if (process.platform === 'darwin') await execAsync(`open "${authUrl}"`);
    else if (process.platform === 'win32') await execAsync(`start "${authUrl}"`);
    else await execAsync(`xdg-open "${authUrl}"`);
  } catch {
    // Silently fail if browser can't be opened, user has the URL.
  }

  const { token } = await prompt<{ token: string }>([
    {
      type: "input",
      name: "token",
      message: "Paste the token from your browser here:"
    }
  ]);

  if (!token) {
    console.error("❌ Token is required.");
    process.exit(1);
  }

  try {
    const userResponse = await axios.get<GitHubUser>("https://api.github.com/user", {
      headers: { Authorization: `token ${token}` }
    });

    const emailResponse = await axios.get<GitHubEmail[]>("https://api.github.com/user/emails", {
      headers: { Authorization: `token ${token}` }
    });

    const primaryEmail = emailResponse.data.find(e => e.primary && e.verified)?.email;

    if (!primaryEmail) {
      console.error("❌ Could not find a primary, verified email on your GitHub account.");
      process.exit(1);
    }

    const userConfig = {
      token,
      email: primaryEmail,
      username: userResponse.data.login,
      avatar_url: userResponse.data.avatar_url,
    };

    saveConfig(userConfig);
    console.log(`\n✅ Authentication successful! Welcome, ${userConfig.username}.`);
    return userConfig;

  } catch (error) {
    console.error("\n❌ Authentication failed. The token might be invalid or expired.");
    process.exit(1);
  }
};


const init = new Command("init")
  .description("Initialize a project and upload its files")
  .action(async () => {
    let userConfig: UserConfig;
    // 1) Check for config, or trigger login flow
    try {
      userConfig = loadConfig();
      console.log(`\n✅ Welcome back, ${userConfig.username || userConfig.email}.`);
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
              {name: "Create a new project", value: "1"},
              {name: "Select an existing project", value: "2"}
          ]
        }
      ]);

    let projectId: string;
    if (action === "1") {
      // create
      const { name } = await prompt<{ name: string }>([
        { type: "input", name: "name", message: "Project name:" }
      ]);
      const res = await axios.post<ProjectResponse>(
        `${API_BASE}/projects/`,
        { name },
        { headers: { Authorization: `Bearer ${userConfig.token}` } }
      );
      projectId = res.data.id;
      console.log(`\n✅ Created project "${res.data.name}" (ID: ${projectId})`);
    } else {
      // select
      const res = await axios.get<ProjectResponse[]>(`${API_BASE}/projects/`, {
        headers: { Authorization: `Bearer ${userConfig.token}` }
      });
      const projects = res.data;
      if (projects.length === 0) {
        console.log("No projects found. Please create one first.");
        process.exit(0);
      }
      
      const { id } = await prompt<{id: string}>([
          {
              type: "list",
              name: "id",
              message: "Select a project:",
              choices: projects.map(p => ({name: p.name, value: p.id}))
          }
      ]);
      projectId = id;
      const selectedProject = projects.find(p => p.id === projectId);
      console.log(`\n✅ Selected project "${selectedProject?.name}" (ID: ${projectId})`);
    }
    
    // 3) Gather core metadata
    console.log("\n⚙️  Project Configuration");
    const defaults = {
      current_path: ".",
      language: detectLanguage(),
      has_dockerfile: fs.existsSync("Dockerfile")
    };
    const core = await prompt<MetadataAnswers>([
      {
        type: "input",
        name: "current_path",
        message: "Current path:",
        default: defaults.current_path
      },
      {
        type: "input",
        name: "language",
        message: "Language:",
        default: defaults.language
      },
      {
        type: "confirm",
        name: "has_dockerfile",
        message: "Has Dockerfile?",
        default: defaults.has_dockerfile
      }
    ]);

    // 4) Gather env vars by key
    console.log("\n🔧 Environment Variables");
    const { env_keys } = await prompt<{ env_keys: string }>([
      {
        type: "input",
        name: "env_keys",
        message: "Env var keys (comma separated, e.g. KEY1,KEY2):",
        default: ""
      }
    ]);
    const envVars: Record<string, string> = {};
    const keys = env_keys
      .split(",")
      .map((k) => k.trim())
      .filter((k) => k);
    for (const key of keys) {
      const { value } = await prompt<{ value: string }>([
        {
          type: "input",
          name: "value",
          message: `Value for ${key}:`
        }
      ]);
      envVars[key] = value;
    }

    // 5) Package & upload
    const tarName = packDirectory();
    const form = new FormData();
    form.append("file", fs.createReadStream(tarName));
    form.append("current_path", core.current_path);
    form.append("language", core.language);
    form.append("has_dockerfile", String(core.has_dockerfile));
    form.append("env_vars", JSON.stringify(envVars));

    const up = await axios.post(
      `${API_BASE}/projects/${projectId}/upload`,
      form,
      { headers: { Authorization: `Bearer ${userConfig.token}`, ...form.getHeaders() } }
    );
    console.log("\n✅ Upload successful!");
    console.table(up.data);

    // cleanup
    fs.unlinkSync(tarName);

    console.log(
      "\n💡 To log out, run: `bernitespace logout`"
    );
  });

export default init;